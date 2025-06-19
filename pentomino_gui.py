import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pentomino_solver import PentominoSolver, PENTOMINOES

# --- 1. GUI Configuration ---
EDITOR_ROWS = 20
EDITOR_COLS = 20
CELL_SIZE = 25
GRID_COLOR = "#CCCCCC"
ACTIVE_COLOR = "#E0E0E0" # Color for a selected cell in the editor
INACTIVE_COLOR = "#FFFFFF"
PIECE_COLORS = {
    'F': '#FF6666', 'I': '#66FF66', 'L': '#6666FF', 'P': '#FFFF66',
    'N': '#FF66FF', 'T': '#66FFFF', 'U': '#FFB266', 'V': '#B266FF',
    'W': '#66FFB2', 'X': '#B2B2B2', 'Y': '#FFD700', 'Z': '#8A2BE2'
}


def normalize_board(cells):
    """
    Normalize the board shape so that the top-left of the board is (0,0).
    """
    min_r = min(r for r, c in cells)
    min_c = min(c for r, c in cells)
    return [(r - min_r, c - min_c) for r, c in cells]


class PentominoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pentomino Solver")

        # --- 2. Editor ---
        editor_frame = ttk.Frame(self, padding="10")
        editor_frame.grid(row=0, column=0)

        self.canvas = tk.Canvas(editor_frame,
                                 width=EDITOR_COLS * CELL_SIZE,
                                 height=EDITOR_ROWS * CELL_SIZE,
                                 bg=INACTIVE_COLOR)
        self.canvas.pack()

        self.active_cells = set()
        self.draw_mode = None # For drawing/erasing
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.paint_cell)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)

        count_frame = ttk.Frame(self, padding="10")
        count_frame.grid(row=1, column=0)
        self.count_label = ttk.Label(count_frame, text="Selected Squares: 0 / 60")
        self.count_label.pack()

        # --- 3. Controls ---
        control_frame = ttk.Frame(self, padding="10")
        control_frame.grid(row=0, column=1, rowspan=5, sticky="ns")

        self.limit_solutions_var = tk.BooleanVar()
        limit_chk = ttk.Checkbutton(control_frame,
                                     text="Limit solutions",
                                     variable=self.limit_solutions_var,
                                     command=self.toggle_max_solutions_entry)
        limit_chk.grid(row=0, column=0, sticky="w")

        self.max_solutions_var = tk.StringVar()
        self.max_solutions_entry = ttk.Entry(control_frame,
                                              textvariable=self.max_solutions_var,
                                              state=tk.DISABLED)
        self.max_solutions_entry.grid(row=1, column=0)

        self.solve_button = ttk.Button(control_frame,
                                       text="Solve Custom Board",
                                       command=self.validate_and_solve)
        self.solve_button.grid(row=2, column=0, pady=10, sticky="ew")

        self.clear_button = ttk.Button(control_frame,
                                       text="Clear Pieces",
                                       command=self.clear_pieces,
                                       state=tk.DISABLED)
        self.clear_button.grid(row=3, column=0, pady=5, sticky="ew")

        self.cancel_button = ttk.Button(control_frame,
                                        text="Cancel",
                                        command=self.cancel_solver,
                                        state=tk.DISABLED)
        self.cancel_button.grid(row=4, column=0, pady=5, sticky="ew")

        status_frame = ttk.Frame(control_frame, padding="10")
        status_frame.grid(row=5, column=0, pady=20, sticky="ew")
        
        self.progressbar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progressbar.pack(fill='x', pady=5)
        
        self.solution_label = ttk.Label(status_frame, text="Solution: - / -")
        self.solution_label.pack()
        self.time_label = ttk.Label(status_frame, text="Time: -")
        self.time_label.pack()

        solution_nav_frame = ttk.Frame(control_frame)
        solution_nav_frame.grid(row=6, column=0, pady=10)
        self.prev_button = ttk.Button(solution_nav_frame, text="<", command=self.show_previous_solution, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.next_button = ttk.Button(solution_nav_frame, text=">", command=self.show_next_solution, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, padx=5)

        self.new_puzzle_button = ttk.Button(control_frame, text="New Puzzle", command=self.new_puzzle, state=tk.DISABLED)
        self.new_puzzle_button.grid(row=7, column=0, pady=10, sticky="ew")

        # Bind keyboard events
        self.bind("<Left>", self.key_nav)
        self.bind("<Right>", self.key_nav)

        # --- 4. State ---
        self.solutions = []
        self.current_solution_index = -1
        self.board_shape = []
        self.solver_thread = None
        self.stop_event = None

        self.draw_grid()

    def toggle_max_solutions_entry(self):
        """Enable/disable the max solutions entry based on the checkbox."""
        state = tk.NORMAL if self.limit_solutions_var.get() else tk.DISABLED
        self.max_solutions_entry.config(state=state)

    def start_drag(self, event):
        """Records the drawing mode (add/remove) and paints the first cell."""
        r = event.y // CELL_SIZE
        c = event.x // CELL_SIZE
        if 0 <= r < EDITOR_ROWS and 0 <= c < EDITOR_COLS:
            cell = (r, c)
            if cell in self.active_cells:
                self.draw_mode = 'remove'
            else:
                self.draw_mode = 'add'
            self.paint_cell(event)

    def stop_drag(self, event):
        """Resets the drawing mode when the mouse is released."""
        self.draw_mode = None

    def paint_cell(self, event):
        """Adds or removes cells from the board based on the drawing mode."""
        if self.draw_mode is None:
            return

        r = event.y // CELL_SIZE
        c = event.x // CELL_SIZE
        if 0 <= r < EDITOR_ROWS and 0 <= c < EDITOR_COLS:
            cell = (r, c)
            if self.draw_mode == 'add':
                if cell not in self.active_cells:
                    self.active_cells.add(cell)
                    self.canvas.itemconfig(f"cell_{r}_{c}", fill=ACTIVE_COLOR)
                    self.update_count_label()
            elif self.draw_mode == 'remove':
                if cell in self.active_cells:
                    self.active_cells.remove(cell)
                    self.canvas.itemconfig(f"cell_{r}_{c}", fill=INACTIVE_COLOR)
                    self.update_count_label()

    def update_count_label(self):
        """Updates the label showing the number of selected squares."""
        self.count_label.config(text=f"Selected Squares: {len(self.active_cells)}")

    def validate_and_solve(self):
        num_cells = len(self.active_cells)
        if num_cells < 5:
            messagebox.showerror("Invalid Board Shape",
                                 f"Please select at least 5 squares to place one pentomino.")
            return
        if num_cells > 60:
            messagebox.showinfo("Board Information",
                                f"You have selected {num_cells} squares. Only 12 pentominoes are available, so at most 60 squares will be filled.")

        max_sols = None
        if self.limit_solutions_var.get():
            try:
                max_sols = int(self.max_solutions_var.get())
                if max_sols <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Input", 
                                     "Please enter a positive integer for the maximum number of solutions.")
                return

        # Normalize the board shape and start solving
        board_shape = normalize_board(self.active_cells)
        self.clear_button.config(state=tk.DISABLED)
        self.start_solver_for_board(board_shape, max_solutions=max_sols)

    def start_solver_for_board(self, board_shape, max_solutions=None):
        self.board_shape = board_shape
        self.solutions = []
        self.current_solution_index = -1
        self.max_solutions = max_solutions

        # --- UI State Update ---
        self.set_controls_state(tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.solution_label.config(text="Solving...")
        self.time_label.config(text="Time: -")
        if self.max_solutions:
            self.progressbar.config(mode='determinate', maximum=self.max_solutions, value=0)
        else:
            self.progressbar.config(mode='indeterminate')
            self.progressbar.start()
        self.draw_grid()
        
        # --- Threading Setup ---
        self.stop_event = threading.Event()
        self.solver_thread = threading.Thread(
            target=self.run_solver,
            args=(self.stop_event,),
            daemon=True
        )
        self.solver_thread.start()

    def _update_progress(self, count:int):
        if self.max_solutions:                              # determinate
            self.progressbar["value"] = count               # 0 … max_solutions
            # Optional visual snappiness:
            self.progressbar.update_idletasks()    

    def run_solver(self, stop_event):
        solver = PentominoSolver(self.board_shape, PENTOMINOES)
        # Progress callback to update progress bar
        def progress_callback(count:int):
            self.after(0, self._update_progress, count)
        solutions, time_taken = solver.solve(
            max_solutions=self.max_solutions,
            stop_event=stop_event,
            progress_callback=progress_callback
        )
        # Schedule UI update on the main thread
        self.after(0, self.on_solver_finished, solutions, time_taken, stop_event.is_set())

    def on_solver_finished(self, solutions, time_taken, was_cancelled):
        # --- Finalise the progress bar ---
        if self.max_solutions:                 # determinate mode
            # Fill the bar to either the max requested or the number actually found
            self.progressbar.config(mode='determinate')
            self.progressbar["value"] = min(len(solutions), self.max_solutions)
        else:                                  # indeterminate mode
            self.progressbar.stop()

        # --- UI State Cleanup ---
        self.cancel_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.NORMAL)
        self.new_puzzle_button.config(state=tk.NORMAL)

        # --- Process solutions ---
        self.solutions = solutions
        if solutions:
            self.current_solution_index = 0
            self.draw_solution(solutions[0])
            self.solution_label.config(text=f"Solution: 1 / {len(solutions)}")
            self.set_controls_state(tk.NORMAL)
        else:
            self.solution_label.config(text="Solution: 0 / 0")

        # --- Display final message ---
        if was_cancelled:
            msg = "The search was cancelled."
            if solutions:
                msg += f"\n\nFound {len(solutions)} solution(s) before stopping."
            messagebox.showinfo("Solver Cancelled", msg)
        elif not solutions:
            messagebox.showinfo(
                "Solver Result",
                "No solutions found for this board shape."
            )

        self.time_label.config(text=f"Time: {time_taken:.4f}s")

    def cancel_solver(self):
        if self.solver_thread and self.solver_thread.is_alive() and self.stop_event:
            self.stop_event.set()
            self.cancel_button.config(state=tk.DISABLED)
            self.progressbar.stop()          # freeze the bar immediately
            self.solution_label.config(text="Cancelling…")

    def key_nav(self, event):
        """Handle left/right arrow key navigation."""
        if not self.solutions:
            return
        if event.keysym == "Left":
            self.show_previous_solution()
        elif event.keysym == "Right":
            self.show_next_solution()

    def _reset_board_state(self):
        """Helper to reset all board and solution state."""
        self.active_cells.clear()
        self.board_shape = []
        self.solutions = []
        self.current_solution_index = -1
        self.update_count_label()
        self.draw_grid()
        self.solution_label.config(text="Solution: - / -")
        self.time_label.config(text="Time: -")
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self.solve_button.config(state=tk.NORMAL)
        self.new_puzzle_button.config(state=tk.NORMAL)

    def clear_pieces(self):
        """Clears the solution from the board, but keeps the selected squares."""
        # If there are no solutions, there's nothing to clear.
        if not self.solutions:
            return

        self.solutions = []
        self.current_solution_index = -1

        # Redraw the board to show only the selected shape, not the pieces
        self.draw_grid()

        # Reset labels and buttons to pre-solve state
        self.solution_label.config(text="Solution: - / -")
        self.time_label.config(text="Time: -")
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        self.solve_button.config(state=tk.NORMAL)
        self.clear_button.config(state=tk.NORMAL)

    def new_puzzle(self):
        """Resets the GUI to its initial state to allow for a new puzzle."""
        self._reset_board_state()
        self.limit_solutions_var.set(False)
        self.toggle_max_solutions_entry()

    def draw_grid(self):
        self.canvas.delete("all")
        # Draw the background grid based on max possible size
        for r in range(EDITOR_ROWS):
            for c in range(EDITOR_COLS):
                x1, y1 = c * CELL_SIZE, r * CELL_SIZE
                x2, y2 = x1 + CELL_SIZE, y1 + CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2,
                                             fill=INACTIVE_COLOR,
                                             outline=GRID_COLOR,
                                             tags=f"cell_{r}_{c}")
        # Highlight the actual board shape
        for r, c in self.board_shape:
            self.canvas.itemconfig(f"cell_{r}_{c}", fill=ACTIVE_COLOR)

    def draw_solution(self, solution):
        self.draw_grid()
        for item in solution:
            # A placed piece is a tuple of (piece_name, orientation, start_pos)
            if isinstance(item, tuple) and len(item) == 3:
                piece_name, orientation, (r_start, c_start) = item
                color = PIECE_COLORS.get(piece_name, "#000000")
                for r_offset, c_offset in orientation:
                    r, c = r_start + r_offset, c_start + c_offset
                    self.canvas.itemconfig(f"cell_{r}_{c}", fill=color)

    def show_previous_solution(self):
        if not self.solutions: return
        self.current_solution_index = (self.current_solution_index - 1 + len(self.solutions)) % len(self.solutions)
        self.draw_solution(self.solutions[self.current_solution_index])
        self.solution_label.config(text=f"Solution: {self.current_solution_index + 1} / {len(self.solutions)}")

    def show_next_solution(self):
        if not self.solutions: return
        self.current_solution_index = (self.current_solution_index + 1) % len(self.solutions)
        self.draw_solution(self.solutions[self.current_solution_index])
        self.solution_label.config(text=f"Solution: {self.current_solution_index + 1} / {len(self.solutions)}")

    def set_controls_state(self, state):
        """Enable or disable solver controls."""
        self.prev_button.config(state=state)
        self.next_button.config(state=state)
        self.clear_button.config(state=state)
        self.new_puzzle_button.config(state=state)

# --- 5. Main Execution ---
if __name__ == "__main__":
    app = PentominoGUI()
    app.mainloop()