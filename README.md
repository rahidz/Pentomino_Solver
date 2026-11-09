# Pentomino Solver

Draw a board and pack it with the twelve pentominoes. Python and Tkinter only; no packages to install.

## Run

```powershell
python pentomino_gui.py
```

The app opens with a 6 × 10 rectangle and stops after the first solution.

- Choose a rectangle or the 8 × 8 board with a central 2 × 2 hole, or draw on the 20 × 20 grid. Click and drag to add or erase squares.
- Click **Solve board**. Raise the solution limit, or uncheck **Stop after** to enumerate every unique solution.
- Browse results with **← / →** or the arrow keys.
- **Stop search** keeps solutions already found. **Clear pieces** keeps your board; **Clear board** empties it.

Each piece is used at most once, with rotations and reflections allowed. The target is `min(12, squares // 5)` pieces; remaining squares stay blank. The count beneath the editor shows the target before solving. If that many pieces cannot fit, the search returns no solutions.

Solutions related by a rotation or reflection of the **whole board** count once. Only transformations preserving the board shape are identified; square boards include quarter-turns.

## Python API

```python
from pentomino_solver import PentominoSolver, generate_board_shape

solver = PentominoSolver(generate_board_shape())
solutions, seconds = solver.solve(max_solutions=1)

for name, orientation, (row, col) in solutions[0]:
    cells = [(row + dr, col + dc) for dr, dc in orientation]
    print(name, cells)
```

Pass any collection of distinct `(row, column)` cells as the board. Returned coordinates stay in that coordinate system. `max_solutions=None` enumerates all unique results. Optional `stop_event` (`threading.Event`) cancels the search; `progress_callback(count)` runs on the calling thread when a new unique solution is found.

Running `python pentomino_solver.py` prints one solution to the 6 × 10 rectangle.

## Search

The solver builds sparse Dancing Links rows directly from legal placements. Board cells are required columns; piece columns enforce one use, becoming optional when the board uses fewer than twelve pieces. Uncovered cells use individual blank rows with a shared blank budget, rather than permutations of labeled slots. Disconnected regions prune impossible branches, and a required piece breaks board symmetry before searching.

Full enumeration reproduces these classic counts:

| Board | Unique solutions |
| --- | ---: |
| 3 × 20 | 2 |
| 4 × 15 | 368 |
| 5 × 12 | 1,010 |
| 6 × 10 | 2,339 |
| 8 × 8, central 2 × 2 hole | 65 |

Algorithm: Donald Knuth, [Dancing Links](https://arxiv.org/abs/cs/0011047).
