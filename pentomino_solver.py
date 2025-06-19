import time
import threading
from typing import List, Tuple, Set, Optional, Any, cast

# --- 1. Pentomino and Board Definitions ---

PENTOMINOES = {
    'F': [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)],
    'I': [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)],
    'L': [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1)],
    'P': [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)],
    'N': [(0, 1), (1, 1), (2, 0), (2, 1), (3, 0)],
    'T': [(0, 0), (0, 1), (0, 2), (1, 1), (2, 1)],
    'U': [(0, 0), (0, 2), (1, 0), (1, 1), (1, 2)],
    'V': [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)],
    'W': [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)],
    'X': [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)],
    'Y': [(0, 1), (1, 1), (2, 1), (3, 1), (3, 0)],
    'Z': [(0, 0), (0, 1), (1, 1), (1, 2), (1, 3)]
}

def generate_orientations(piece: List[Tuple[int, int]]) -> Set[Tuple[Tuple[int, int], ...]]:
    def normalize(p):
        min_r = min(r for r, c in p)
        min_c = min(c for r, c in p)
        return tuple(sorted([(r - min_r, c - min_c) for r, c in p]))
    def rotate_90(p):
        return [(-c, r) for r, c in p]
    def flip(p):
        return [(-r, c) for r, c in p]

    orientations: Set[Tuple[Tuple[int, int], ...]] = set()
    p1 = list(piece)
    for _ in range(2):  # two flip states
        p2 = p1[:]
        for _ in range(4):  # four rotations
            orientations.add(normalize(p2))
            p2 = rotate_90(p2)
        p1 = flip(p1)
    return orientations

def generate_board_shape() -> List[Tuple[int, int]]:
    """
    Customize this to your board shape; by default, generates a 6×10 rectangle.
    """
    shape = []
    for r in range(6):
        for c in range(10):
            shape.append((r, c))
    return shape

# --- DLX Node and Column Classes ---

class Node:
    def __init__(self, col: 'Column', row_id: Any = None):
        self.L: 'Node' = self
        self.R: 'Node' = self
        self.U: 'Node' = self
        self.D: 'Node' = self
        self.col: 'Column' = col
        self.row_id: Any = row_id

class Column(Node):
    def __init__(self, name):
        super().__init__(self)
        self.name = name
        self.size = 0  # count of nodes in this column

def cover(col: Column):
    col.R.L = col.L
    col.L.R = col.R
    i = col.D
    while i != col:
        j = i.R
        while j != i:
            j.D.U = j.U
            j.U.D = j.D
            j.col.size -= 1
            j = j.R
        i = i.D

def uncover(col: Column):
    i = col.U
    while i != col:
        j = i.L
        while j != i:
            j.col.size += 1
            j.D.U = j
            j.U.D = j
            j = j.L
        i = i.U
    col.R.L = col
    col.L.R = col

# --- 4. Pentomino Solver Class (with progress and immediate cancel) ---

class PentominoSolver:
    def __init__(self, board: List[Tuple[int, int]], pentominoes=PENTOMINOES):
        self.board = board
        self.board_map = {pos: idx for idx, pos in enumerate(board)}
        self.board_height = max(r for r, _ in board) + 1
        self.board_width = max(c for _, c in board) + 1
        self.pentominoes = pentominoes
        # Precompute orientations
        self.all_piece_orientations = {
            name: generate_orientations(shape)
            for name, shape in pentominoes.items()
        }

    def _build_dlx_matrix(self, stop_event: Optional[threading.Event] = None):
        piece_names = sorted(self.pentominoes.keys())
        col_names = piece_names + self.board
        matrix = []
        iteration_count = 0
        for piece_name in piece_names:
            for orientation in self.all_piece_orientations[piece_name]:
                for r_start, c_start in self.board:
                    # Immediate cancellation check
                    if stop_event and stop_event.is_set():
                        return None, None
                    iteration_count += 1

                    new_pos = [(r_start + r, c_start + c) for r, c in orientation]
                    if all(pos in self.board_map for pos in new_pos):
                        row = [0] * len(col_names)
                        row[piece_names.index(piece_name)] = 1
                        for pos in new_pos:
                            row[len(piece_names) + self.board_map[pos]] = 1
                        matrix.append(((piece_name, orientation, (r_start, c_start)), row))
        return col_names, matrix

    def _build_dlx_links(self, col_names, matrix, stop_event: Optional[threading.Event] = None):
        self.root = Column("root")
        columns = [Column(name) for name in col_names]
        # link header <-> columns in a ring
        for i in range(len(columns)):
            columns[i].L = columns[i-1]
            columns[i].R = columns[(i+1) % len(columns)]
        self.root.R = columns[0]
        self.root.L = columns[-1]
        columns[0].L = self.root
        columns[-1].R = self.root

        # create nodes
        for row_idx, (row_info, row_data) in enumerate(matrix):
            # Immediate cancellation check
            if stop_event and stop_event.is_set():
                self.root = None
                return
            last_node = None
            for col_idx, cell in enumerate(row_data):
                if cell:
                    col = columns[col_idx]
                    new_node = Node(col, row_id=row_info)
                    # vertical link
                    new_node.D = col
                    new_node.U = col.U
                    col.U.D = new_node
                    col.U = new_node
                    col.size += 1
                    # horizontal link
                    if last_node:
                        new_node.L = last_node
                        new_node.R = last_node.R
                        last_node.R.L = new_node
                        last_node.R = new_node
                    else:
                        new_node.L = new_node
                        new_node.R = new_node
                    last_node = new_node

    def _solution_to_grid(self, solution):
        grid = [[' ' for _ in range(self.board_width)] for _ in range(self.board_height)]
        for piece_name, orientation, (r_start, c_start) in solution:
            for r_offset, c_offset in orientation:
                r, c = r_start + r_offset, c_start + c_offset
                if 0 <= r < self.board_height and 0 <= c < self.board_width:
                    grid[r][c] = piece_name
        return tuple("".join(row) for row in grid)

    def _get_canonical_solution(self, solution):
        grid = self._solution_to_grid(solution)
        # For a rectangle, the symmetries are identity, horizontal flip,
        # vertical flip, and 180-degree rotation.
        forms = {grid}
        # Horizontal flip
        h_flipped = tuple(row[::-1] for row in grid)
        forms.add(h_flipped)
        # Vertical flip
        v_flipped = tuple(grid[len(grid) - 1 - r] for r in range(len(grid)))
        forms.add(v_flipped)
        # 180-degree rotation (h_flip of v_flip)
        rotated_180 = tuple(row[::-1] for row in v_flipped)
        forms.add(rotated_180)
        return min(forms)

    def _add_solution(self, solution):
        canonical_form = self._get_canonical_solution(solution)
        if canonical_form not in self.canonical_solutions:
            self.canonical_solutions.add(canonical_form)
            self.solutions.append(solution)

    def solve(self,
              max_solutions: Optional[int] = None,
              stop_event: Optional[threading.Event] = None,
              progress_callback=None):
        """
        Initializes DLX and starts the search.
        Returns (solutions, time_taken).
        """
        self.solutions = []
        self.canonical_solutions = set()
        start_time = time.time()

        # Build matrix
        col_names, matrix = self._build_dlx_matrix(stop_event)
        if matrix is None:
            return self.solutions, time.time() - start_time

        # Link nodes
        self._build_dlx_links(col_names, matrix, stop_event)
        # Search
        self._search([], max_solutions, stop_event, progress_callback)

        return self.solutions, time.time() - start_time

    def _search(self,
                partial_solution: List,
                max_solutions: Optional[int],
                stop_event: Optional[threading.Event],
                progress_callback=None):
        # Immediate cancellation check
        if stop_event and stop_event.is_set():
            return
        if self.root is None:
            return
        if max_solutions is not None and len(self.solutions) >= max_solutions:
            return

        # Solution found?
        if self.root.R == self.root:
            self._add_solution(list(partial_solution))
            if progress_callback:
                progress_callback(len(self.solutions))
            return

        # Choose column with fewest nodes using Knuth's Algorithm S heuristic.
        # We use cast because the type checker can't infer that the nodes in the
        # root's circular list are all Column objects.
        c = cast(Column, self.root.R)
        j = cast(Column, c.R)
        while j != self.root:
            if j.size < c.size:
                c = j
            j = cast(Column, j.R)

        # Cover
        cover(c)
        r = c.D
        while r != c:
            partial_solution.append(r.row_id)
            j = r.R
            while j != r:
                cover(j.col)
                j = j.R

            # Recurse
            self._search(partial_solution, max_solutions, stop_event, progress_callback)

            # Backtrack
            j = r.L
            while j != r:
                uncover(j.col)
                j = j.L
            partial_solution.pop()
            r = r.D
        uncover(c)


# --- 5. Main Execution (for standalone testing) ---

def main():
    print("Setting up the puzzle...")
    board = generate_board_shape()
    solver = PentominoSolver(board, PENTOMINOES)

    print("Starting search for solutions...")
    solutions, t = solver.solve(max_solutions=1)
    print(f"Found {len(solutions)} unique solutions in {t:.2f} seconds.")

if __name__ == "__main__":
    main()
