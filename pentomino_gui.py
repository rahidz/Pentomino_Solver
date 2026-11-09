import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from pentomino_solver import PENTOMINOES, PentominoSolver

EDITOR_ROWS = 20
EDITOR_COLS = 20
CELL_SIZE = 27
GRID_COLOR = "#e2e8f0"
ACTIVE_COLOR = "#cbd5e1"
INACTIVE_COLOR = "#f8fafc"
PIECE_COLORS = {
    "F": "#fb7185", "I": "#86efac", "L": "#93c5fd", "P": "#fde047",
    "N": "#e879f9", "T": "#67e8f9", "U": "#fdba74", "V": "#c4b5fd",
    "W": "#5eead4", "X": "#cbd5e1", "Y": "#facc15", "Z": "#a5b4fc",
}
PRESETS = {
    "6 × 10 rectangle": (6, 10),
    "5 × 12 rectangle": (5, 12),
    "4 × 15 rectangle": (4, 15),
    "3 × 20 rectangle": (3, 20),
    "8 × 8 with a 2 × 2 hole": (8, 8),
    "Blank board": (0, 0),
}


class PentominoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pentomino Solver")
        self.resizable(False, False)
        self.configure(background="#f8fafc")
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.active_cells = set()
        self.solutions = []
        self.current_solution_index = -1
        self.solving = False
        self.stop_event = None
        self.draw_mode = None
        self.last_cell = None

        style = ttk.Style(self)
        style.configure("TFrame", background="#f8fafc")
        style.configure("TLabel", background="#f8fafc", foreground="#334155")
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground="#0f172a")
        style.configure("TButton", padding=(10, 6))
        style.configure("TCheckbutton", background="#f8fafc")

        header = ttk.Frame(self, padding=(20, 18, 20, 12))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, text="Pentominoes", style="Title.TLabel").pack(anchor="w")

        editor = ttk.Frame(self, padding=(20, 0, 12, 18))
        editor.grid(row=1, column=0, sticky="n")
        self.canvas = tk.Canvas(
            editor, width=EDITOR_COLS * CELL_SIZE, height=EDITOR_ROWS * CELL_SIZE,
            background=INACTIVE_COLOR, highlightthickness=1,
            highlightbackground="#cbd5e1",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.paint_cell)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.count_label = ttk.Label(editor)
        self.count_label.pack(anchor="w", pady=(10, 3))
        ttk.Label(editor, text="Click and drag to add or erase squares.").pack(anchor="w")

        controls = ttk.Frame(self, padding=(8, 0, 20, 18), width=265)
        controls.grid(row=1, column=1, sticky="nsew")
        controls.columnconfigure(0, weight=1)
        ttk.Label(controls, text="BOARD", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w")
        self.preset_var = tk.StringVar(value=next(iter(PRESETS)))
        self.preset_combo = ttk.Combobox(
            controls, textvariable=self.preset_var, values=list(PRESETS),
            state="readonly", width=27,
        )
        self.preset_combo.grid(row=1, column=0, sticky="ew", pady=(6, 20))
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_preset)

        self.limit_solutions_var = tk.BooleanVar(value=True)
        self.limit_check = ttk.Checkbutton(
            controls, text="Stop after", variable=self.limit_solutions_var,
            command=self.toggle_max_solutions_entry,
        )
        self.limit_check.grid(row=2, column=0, sticky="w")
        limit_row = ttk.Frame(controls)
        limit_row.grid(row=3, column=0, sticky="w", pady=(4, 12))
        self.max_solutions_var = tk.StringVar(value="1")
        self.max_solutions_entry = ttk.Spinbox(
            limit_row, textvariable=self.max_solutions_var, from_=1, to=100000,
            width=8,
        )
        self.max_solutions_entry.pack(side="left")
        ttk.Label(limit_row, text=" unique solutions").pack(side="left")

        self.solve_button = ttk.Button(controls, text="Solve board", command=self.validate_and_solve)
        self.solve_button.grid(row=4, column=0, sticky="ew")
        self.cancel_button = ttk.Button(controls, text="Stop search", command=self.cancel_solver,
                                        state="disabled")
        self.cancel_button.grid(row=5, column=0, sticky="ew", pady=(6, 16))
        self.progressbar = ttk.Progressbar(controls, mode="determinate")
        self.progressbar.grid(row=6, column=0, sticky="ew")
        self.status_label = ttk.Label(controls, text="Ready", wraplength=240)
        self.status_label.grid(row=7, column=0, sticky="w", pady=(9, 3))
        self.time_label = ttk.Label(controls, text="")
        self.time_label.grid(row=8, column=0, sticky="w")

        nav = ttk.Frame(controls)
        nav.grid(row=9, column=0, pady=(16, 6))
        self.prev_button = ttk.Button(nav, text="←", width=3,
                                      command=self.show_previous_solution, state="disabled")
        self.prev_button.pack(side="left")
        self.solution_label = ttk.Label(nav, text="—", width=15, anchor="center")
        self.solution_label.pack(side="left", padx=4)
        self.next_button = ttk.Button(nav, text="→", width=3,
                                      command=self.show_next_solution, state="disabled")
        self.next_button.pack(side="left")
        self.clear_button = ttk.Button(controls, text="Clear pieces", command=self.clear_pieces,
                                       state="disabled")
        self.clear_button.grid(row=10, column=0, sticky="ew", pady=(4, 6))
        self.new_puzzle_button = ttk.Button(controls, text="Clear board", command=self.new_puzzle)
        self.new_puzzle_button.grid(row=11, column=0, sticky="ew")

        legend = ttk.Frame(controls)
        legend.grid(row=12, column=0, sticky="ew", pady=(25, 0))
        for index, (name, color) in enumerate(PIECE_COLORS.items()):
            tk.Label(legend, text=name, background=color, foreground="#0f172a",
                     width=3, font=("Segoe UI", 11, "bold")).grid(
                         row=index // 6, column=index % 6, padx=2, pady=2)

        self.bind("<Left>", self.key_nav)
        self.bind("<Right>", self.key_nav)
        self.load_preset()

    def load_preset(self, event=None):
        if self.solving:
            return
        rows, cols = PRESETS[self.preset_var.get()]
        row_offset, col_offset = (EDITOR_ROWS - rows) // 2, (EDITOR_COLS - cols) // 2
        self.active_cells = {
            (r + row_offset, c + col_offset)
            for r in range(rows) for c in range(cols)
            if not (rows == cols == 8 and r in (3, 4) and c in (3, 4))
        }
        self.clear_pieces()
        self.update_count_label()

    def toggle_max_solutions_entry(self):
        self.max_solutions_entry.config(
            state="normal" if self.limit_solutions_var.get() and not self.solving else "disabled")

    def start_drag(self, event):
        if self.solving:
            return
        cell = (event.y // CELL_SIZE, event.x // CELL_SIZE)
        if 0 <= cell[0] < EDITOR_ROWS and 0 <= cell[1] < EDITOR_COLS:
            self.clear_pieces()
            self.draw_mode = "remove" if cell in self.active_cells else "add"
            self.last_cell = cell
            self.paint_cell(event)

    def stop_drag(self, event):
        self.draw_mode = None
        self.last_cell = None

    def paint_cell(self, event):
        if self.solving or self.draw_mode is None:
            return
        row, col = event.y // CELL_SIZE, event.x // CELL_SIZE
        if not (0 <= row < EDITOR_ROWS and 0 <= col < EDITOR_COLS):
            return
        old_row, old_col = self.last_cell
        steps = max(abs(row - old_row), abs(col - old_col), 1)
        for step in range(steps + 1):
            cell = (round(old_row + (row - old_row) * step / steps),
                    round(old_col + (col - old_col) * step / steps))
            if self.draw_mode == "add":
                self.active_cells.add(cell)
            else:
                self.active_cells.discard(cell)
            self.canvas.itemconfig(f"cell_{cell[0]}_{cell[1]}",
                                   fill=ACTIVE_COLOR if cell in self.active_cells else INACTIVE_COLOR)
        self.last_cell = (row, col)
        self.preset_var.set("Custom board")
        self.update_count_label()

    def update_count_label(self):
        count = len(self.active_cells)
        pieces = min(len(PENTOMINOES), count // 5)
        blanks = count - pieces * 5
        self.count_label.config(text=f"{count} squares · {pieces} pieces · {blanks} left blank")

    def validate_and_solve(self):
        if self.solving:
            return
        if len(self.active_cells) < 5:
            messagebox.showerror("Empty board", "Select at least five squares.", parent=self)
            return
        limit = None
        if self.limit_solutions_var.get():
            try:
                limit = int(self.max_solutions_var.get())
                if limit < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Solution limit", "Enter a positive whole number.", parent=self)
                return
        self.start_solver_for_board(sorted(self.active_cells), limit)

    def start_solver_for_board(self, board_shape, max_solutions=None):
        if self.solving:
            return
        self.active_cells = set(board_shape)
        self.clear_pieces()
        self.update_count_label()
        self.solving = True
        self.draw_mode = None
        self.max_solutions = max_solutions
        self.started_at = time.perf_counter()
        self.stop_event = threading.Event()
        self.events = queue.Queue()
        self.set_controls_state()
        self.status_label.config(text="Searching · 0 unique solutions")
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start(12)
        self.solver_thread = threading.Thread(
            target=self.run_solver,
            args=(tuple(board_shape), max_solutions, self.stop_event, self.events),
            daemon=True,
        )
        self.solver_thread.start()
        self.after(50, self.poll_solver)

    @staticmethod
    def run_solver(board, limit, stop_event, events):
        try:
            solutions, elapsed = PentominoSolver(board).solve(
                max_solutions=limit, stop_event=stop_event,
                progress_callback=lambda count: events.put(("progress", count)),
            )
            events.put(("finished", (solutions, elapsed, stop_event.is_set())))
        except Exception as error:
            traceback.print_exc()
            events.put(("error", str(error)))

    def poll_solver(self):
        while not self.events.empty():
            kind, result = self.events.get_nowait()
            if kind == "progress":
                if not self.stop_event.is_set():
                    self.status_label.config(text=f"Searching · {result:,} unique solutions")
            elif kind == "finished":
                self.on_solver_finished(*result)
            else:
                self.solving = False
                self.progressbar.stop()
                self.progressbar.config(mode="determinate", value=0)
                self.set_controls_state()
                self.status_label.config(text="Search failed")
                messagebox.showerror("Solver error", result, parent=self)
        if self.solving:
            self.time_label.config(text=f"{time.perf_counter() - self.started_at:.1f} seconds")
            self.after(50, self.poll_solver)

    def on_solver_finished(self, solutions, time_taken, was_cancelled):
        self.solving = False
        self.progressbar.stop()
        self.progressbar.config(mode="determinate", value=0)
        self.solutions = solutions
        if solutions:
            self.current_solution_index = 0
            self.show_solution()
        else:
            self.solution_label.config(text="0 / 0")
        self.set_controls_state()
        if was_cancelled:
            status = "Stopped"
        elif self.max_solutions is not None and len(solutions) >= self.max_solutions:
            status = "Limit reached"
        else:
            status = "Search complete"
        self.status_label.config(text=f"{status} · {len(solutions):,} unique solutions")
        self.time_label.config(text=f"{time_taken:.3f} seconds")

    def cancel_solver(self):
        if self.solving:
            self.stop_event.set()
            self.cancel_button.config(state="disabled")
            self.status_label.config(text="Stopping…")

    def set_controls_state(self):
        state = "disabled" if self.solving else "normal"
        for control in (self.solve_button, self.new_puzzle_button, self.limit_check):
            control.config(state=state)
        self.preset_combo.config(state="disabled" if self.solving else "readonly")
        self.cancel_button.config(state="normal" if self.solving else "disabled")
        self.clear_button.config(state="normal" if self.solutions and not self.solving else "disabled")
        nav_state = "normal" if len(self.solutions) > 1 and not self.solving else "disabled"
        self.prev_button.config(state=nav_state)
        self.next_button.config(state=nav_state)
        self.toggle_max_solutions_entry()

    def clear_pieces(self):
        if self.solving:
            return
        self.solutions = []
        self.current_solution_index = -1
        self.solution_label.config(text="—")
        self.status_label.config(text="Ready")
        self.time_label.config(text="")
        self.set_controls_state()
        self.draw_grid()

    def new_puzzle(self):
        if not self.solving:
            self.active_cells.clear()
            self.preset_var.set("Blank board")
            self.clear_pieces()
            self.update_count_label()

    def draw_grid(self):
        self.canvas.delete("all")
        for r in range(EDITOR_ROWS):
            for c in range(EDITOR_COLS):
                self.canvas.create_rectangle(
                    c * CELL_SIZE, r * CELL_SIZE, (c + 1) * CELL_SIZE, (r + 1) * CELL_SIZE,
                    fill=ACTIVE_COLOR if (r, c) in self.active_cells else INACTIVE_COLOR,
                    outline=GRID_COLOR, tags=f"cell_{r}_{c}",
                )

    def draw_solution(self, solution):
        self.draw_grid()
        for name, orientation, (row, col) in solution:
            cells = {(row + r, col + c) for r, c in orientation}
            color = PIECE_COLORS[name]
            for r, c in cells:
                self.canvas.itemconfig(f"cell_{r}_{c}", fill=color, outline=color)
            for r, c in cells:
                x, y = c * CELL_SIZE, r * CELL_SIZE
                edges = (
                    ((r - 1, c), (x, y, x + CELL_SIZE, y)),
                    ((r + 1, c), (x, y + CELL_SIZE, x + CELL_SIZE, y + CELL_SIZE)),
                    ((r, c - 1), (x, y, x, y + CELL_SIZE)),
                    ((r, c + 1), (x + CELL_SIZE, y, x + CELL_SIZE, y + CELL_SIZE)),
                )
                for neighbor, line in edges:
                    if neighbor not in cells:
                        self.canvas.create_line(*line, fill="#334155", width=2)
            center_r = sum(r for r, c in cells) / 5
            center_c = sum(c for r, c in cells) / 5
            r, c = min(cells, key=lambda cell: ((cell[0] - center_r) ** 2 +
                                               (cell[1] - center_c) ** 2, cell))
            self.canvas.create_text((c + 0.5) * CELL_SIZE, (r + 0.5) * CELL_SIZE,
                                    text=name, fill="#0f172a", font=("Segoe UI", 11, "bold"))

    def show_solution(self):
        self.draw_solution(self.solutions[self.current_solution_index])
        self.solution_label.config(text=f"{self.current_solution_index + 1:,} / {len(self.solutions):,}")

    def show_previous_solution(self):
        if self.solutions and not self.solving:
            self.current_solution_index = (self.current_solution_index - 1) % len(self.solutions)
            self.show_solution()

    def show_next_solution(self):
        if self.solutions and not self.solving:
            self.current_solution_index = (self.current_solution_index + 1) % len(self.solutions)
            self.show_solution()

    def key_nav(self, event):
        if isinstance(self.focus_get(), (ttk.Entry, ttk.Spinbox, ttk.Combobox)):
            return
        if event.keysym == "Left":
            self.show_previous_solution()
        else:
            self.show_next_solution()

    def close(self):
        if self.stop_event is not None:
            self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    PentominoGUI().mainloop()
