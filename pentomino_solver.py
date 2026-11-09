"""Pentomino packing with sparse Algorithm X / Dancing Links."""

import threading
import time


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
    'Y': [(0, 1), (1, 0), (1, 1), (2, 1), (3, 1)],
    'Z': [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
}


def generate_orientations(piece):
    orientations = set()
    for reflected in (False, True):
        cells = [(r, -c if reflected else c) for r, c in piece]
        for _ in range(4):
            min_r = min(r for r, c in cells)
            min_c = min(c for r, c in cells)
            orientations.add(tuple(sorted((r - min_r, c - min_c) for r, c in cells)))
            cells = [(-c, r) for r, c in cells]
    return orientations


def generate_board_shape():
    return [(r, c) for r in range(6) for c in range(10)]


class Node:
    __slots__ = ('L', 'R', 'U', 'D', 'col', 'row_id')

    def __init__(self, col, row_id=None):
        self.L = self.R = self.U = self.D = self
        self.col = col
        self.row_id = row_id


class Column(Node):
    __slots__ = ('size', 'is_board')

    def __init__(self, is_board=False):
        super().__init__(self)
        self.size = 0
        self.is_board = is_board


def cover(col):
    col.R.L = col.L
    col.L.R = col.R
    row = col.D
    while row is not col:
        node = row.R
        while node is not row:
            node.D.U = node.U
            node.U.D = node.D
            node.col.size -= 1
            node = node.R
        row = row.D


def uncover(col):
    row = col.U
    while row is not col:
        node = row.L
        while node is not row:
            node.col.size += 1
            node.D.U = node
            node.U.D = node
            node = node.L
        row = row.U
    col.R.L = col
    col.L.R = col


class PentominoSolver:
    """Use each piece at most once, filling min(piece count, area // 5) pieces.

    Solutions are lists of (piece name, orientation, origin) placements in the
    input board's coordinates. Rotations/reflections preserving the board count
    once. Uncovered cells are allowed only for the area left after that target.
    """

    def __init__(self, board, pentominoes=PENTOMINOES):
        self.board = sorted(board)
        if not self.board or len(set(self.board)) != len(self.board):
            raise ValueError('The board must contain distinct cells and cannot be empty.')
        if not pentominoes or any(len(p) != 5 or len(set(p)) != 5 for p in pentominoes.values()):
            raise ValueError('Each pentomino must contain five distinct cells.')
        for shape in pentominoes.values():
            connected = {shape[0]}
            while True:
                expanded = connected | {
                    cell for cell in shape
                    if any((cell[0] + dr, cell[1] + dc) in connected
                           for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                }
                if expanded == connected:
                    break
                connected = expanded
            if len(connected) != 5:
                raise ValueError('Pentomino cells must be edge-connected.')

        self.board_map = {cell: i for i, cell in enumerate(self.board)}
        self.min_r = min(r for r, c in self.board)
        self.min_c = min(c for r, c in self.board)
        self.board_height = max(r for r, c in self.board) - self.min_r + 1
        self.board_width = max(c for r, c in self.board) - self.min_c + 1
        self.stride = self.board_width + 1  # Empty gutter prevents horizontal wrapping.
        self.cell_bits = {
            (r, c): 1 << ((r - self.min_r) * self.stride + c - self.min_c)
            for r, c in self.board
        }
        self.board_mask = sum(self.cell_bits.values())
        self.pentominoes = pentominoes
        self.num_pieces_to_use = min(len(pentominoes), len(self.board) // 5)
        self.squares_to_leave_blank = len(self.board) - self.num_pieces_to_use * 5
        self.all_piece_orientations = {
            name: sorted(generate_orientations(shape))
            for name, shape in pentominoes.items()
        }
        self.symmetries = self._board_symmetries()

    def _board_symmetries(self):
        permutations = set()
        for reflected in (False, True):
            cells = [(r, -c if reflected else c) for r, c in self.board]
            for _ in range(4):
                min_r = min(r for r, c in cells)
                min_c = min(c for r, c in cells)
                transformed = [(r - min_r + self.min_r, c - min_c + self.min_c)
                               for r, c in cells]
                if set(transformed) == set(self.board):
                    permutations.add(tuple(self.board_map[cell] for cell in transformed))
                cells = [(-c, r) for r, c in cells]
        return sorted(permutations)

    def _build_links(self):
        self.root = Column()
        pieces = {name: Column() for name in sorted(self.pentominoes)}
        cells = {cell: Column(is_board=True) for cell in self.board}
        primary = list(cells.values())
        all_required = self.num_pieces_to_use == len(pieces)
        if all_required:
            primary += list(pieces.values())
        # Optional piece columns remain outside the root ring: at most one use.
        for col in primary:
            col.L, col.R = self.root.L, self.root
            self.root.L.R = col
            self.root.L = col

        self.rows = []

        def add_row(info, mask, columns):
            row_id = len(self.rows)
            self.rows.append((info, mask))
            first = None
            for col in columns:
                node = Node(col, row_id)
                node.U, node.D = col.U, col
                col.U.D = node
                col.U = node
                col.size += 1
                if first is None:
                    first = node
                else:
                    node.L, node.R = first.L, first
                    first.L.R = node
                    first.L = node

        # Fix one required piece to one representative per board-symmetry orbit.
        fixed_piece = min(pieces, key=lambda p: len(self.all_piece_orientations[p])) if all_required else None
        for name, piece_col in pieces.items():
            for orientation in self.all_piece_orientations[name]:
                # Anchor an occupied cell, not the possibly empty bounding-box corner.
                anchor_r, anchor_c = orientation[0]
                for r, c in self.board:
                    if self.stop_event.is_set():
                        return
                    origin = (r - anchor_r, c - anchor_c)
                    positions = [(origin[0] + dr, origin[1] + dc) for dr, dc in orientation]
                    if not all(pos in cells for pos in positions):
                        continue
                    indices = tuple(sorted(self.board_map[pos] for pos in positions))
                    if name == fixed_piece and any(
                        tuple(sorted(sym[i] for i in indices)) < indices for sym in self.symmetries
                    ):
                        continue
                    add_row((name, orientation, origin),
                            sum(self.cell_bits[pos] for pos in positions),
                            [piece_col] + [cells[pos] for pos in positions])

        # One blank row per cell, not factorially many labeled blank/unused slots.
        if self.squares_to_leave_blank:
            for pos, col in cells.items():
                add_row(None, self.cell_bits[pos], [col])

    def _components_fit(self, remaining, blanks):
        """Each disconnected component needs at least area % 5 blank cells."""
        needed = 0
        while remaining:
            component = remaining & -remaining
            while True:
                expanded = component | ((component << 1 | component >> 1 |
                                          component << self.stride | component >> self.stride) & remaining)
                if expanded == component:
                    break
                component = expanded
            needed += component.bit_count() % 5
            if needed > blanks:
                return False
            remaining ^= component
        return True

    def _add_solution(self, placements):
        labels = [''] * len(self.board)
        for name, orientation, (r, c) in placements:
            for dr, dc in orientation:
                labels[self.board_map[r + dr, c + dc]] = name
        forms = []
        for sym in self.symmetries:
            transformed = [''] * len(labels)
            for source, dest in enumerate(sym):
                transformed[dest] = labels[source]
            forms.append(tuple(transformed))
        canonical = min(forms)
        if canonical not in self.canonical_solutions:
            self.canonical_solutions.add(canonical)
            self.solutions.append(list(placements))
            if self.progress_callback:
                self.progress_callback(len(self.solutions))

    def solve(self, max_solutions=None, stop_event=None, progress_callback=None):
        """Return (unique solutions, elapsed seconds); None means no result limit."""
        if max_solutions is not None and (not isinstance(max_solutions, int) or max_solutions < 1):
            raise ValueError('max_solutions must be a positive integer or None.')
        started = time.perf_counter()
        self.solutions = []
        self.canonical_solutions = set()
        self.nodes_searched = 0
        self.max_solutions = max_solutions
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.progress_callback = progress_callback
        if not self.stop_event.is_set() and self._components_fit(self.board_mask, self.squares_to_leave_blank):
            self._build_links()
            if not self.stop_event.is_set():
                self._search([], self.board_mask, self.squares_to_leave_blank)
        return self.solutions, time.perf_counter() - started

    def _search(self, placements, remaining, blanks):
        if self.stop_event.is_set():
            return True
        self.nodes_searched += 1
        if len(placements) == self.num_pieces_to_use:
            self._add_solution(placements)
            return self.max_solutions is not None and len(self.solutions) >= self.max_solutions
        if not self._components_fit(remaining, blanks):
            return False

        col = self.root.R
        best = None
        smallest = float('inf')
        while col is not self.root:
            size = col.size - (col.is_board and not blanks and bool(self.squares_to_leave_blank))
            if size < smallest:
                best, smallest = col, size
                if size <= 1:
                    break
            col = col.R
        if smallest == 0:
            return False

        cover(best)
        row = best.D
        halted = False
        while row is not best:
            info, mask = self.rows[row.row_id]
            if info is not None or blanks:
                if info is not None:
                    placements.append(info)
                node = row.R
                while node is not row:
                    cover(node.col)
                    node = node.R
                halted = self._search(placements, remaining ^ mask, blanks - (info is None))
                node = row.L
                while node is not row:
                    uncover(node.col)
                    node = node.L
                if info is not None:
                    placements.pop()
                if halted:
                    break
            row = row.D
        uncover(best)
        return halted


def main():
    solver = PentominoSolver(generate_board_shape())
    solutions, elapsed = solver.solve(max_solutions=1)
    print(f'{len(solutions)} solution in {elapsed:.3f}s ({solver.nodes_searched:,} search nodes)')
    if solutions:
        grid = [['.' for c in range(10)] for r in range(6)]
        for name, orientation, (r, c) in solutions[0]:
            for dr, dc in orientation:
                grid[r + dr][c + dc] = name
        print('\n'.join(' '.join(row) for row in grid))


if __name__ == '__main__':
    main()
