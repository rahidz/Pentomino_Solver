# Pentomino Puzzle Solver

This project provides a graphical user interface (GUI) and a powerful backend solver for Pentomino puzzles. Users can design their own puzzle boards and use the solver to find all unique solutions. The solver is implemented using Donald Knuth's Algorithm X with Dancing Links (DLX) for high efficiency.

## Features

### GUI (`pentomino_gui.py`)
- **Interactive Puzzle Editor**: Draw any board shape you can imagine on a 20x20 grid.
- **Live Feedback**: See the number of squares you've selected in real-time.
- **Responsive Interface**: The solver runs in a separate thread, ensuring the GUI never freezes, even on complex puzzles.
- **Solution Navigation**: Once solutions are found, easily browse through them using arrow keys or on-screen buttons.
- **Cancellable Solver**: Stop the search process at any time.
- **Solution Limiting**: Optionally, set a maximum number of solutions to find.
- **Progress Bar**: Visual feedback on the solver's progress.

### Solver (`pentomino_solver.py`)
- **Algorithm X & Dancing Links**: Employs a highly efficient algorithm for solving exact cover problems.
- **Custom Board Support**: Can solve for any board shape defined by the user.
- **Handles Incomplete Boards**: Automatically determines the optimal number of pentominoes to use if the board size is not a multiple of 5.
- **Unique Solution Detection**: Intelligently identifies and discards symmetrical solutions (rotations and flips) to present only unique results.
- **Standalone Operation**: The solver can be run independently from the GUI for testing or scripting purposes.

## How to Run

1.  **Ensure you have Python installed.**
2.  **No external libraries are needed.** The project uses the built-in `tkinter` library for the GUI.
3.  **Run the GUI** by executing the following command in your terminal:
    ```bash
    python pentomino_gui.py
    ```
4.  **Use the editor** to draw a shape.
5.  Click **"Solve Custom Board"** to find the solutions.

## Code Overview

### `pentomino_solver.py`
This file contains the core logic for solving the Pentomino puzzles.
-   **`PENTOMINOES`**: A dictionary defining the shapes of the 12 standard pentominoes.
-   **`generate_orientations()`**: A function that computes all 8 possible orientations (rotations and flips) for a given pentomino piece.
-   **`PentominoSolver` class**:
    -   Initializes with a user-defined board shape.
    -   `_build_dlx_matrix()`: Translates the pentomino puzzle into an exact cover problem matrix.
    -   `_build_dlx_links()`: Constructs the toroidal doubly-linked list structure for the Dancing Links algorithm.
    -   `solve()`: The main public method that initiates the search. It handles threading, stopping conditions, and progress reporting.
    -   `_search()`: The recursive private method that implements the core of Algorithm X.
-   The script can be run standalone to solve a default 6x10 rectangular board.

### `pentomino_gui.py`
This file creates the user interface using `tkinter`.
-   **`PentominoGUI` class**: The main application window.
-   **Canvas Editor**: Manages user input for drawing and erasing the puzzle board shape.
-   **Solver Threading**: When the "Solve" button is clicked, it creates a `PentominoSolver` instance and runs it in a separate `threading.Thread` to prevent the GUI from becoming unresponsive.
-   **State Management**: Handles the UI state for solving, cancelled, and solution-found scenarios.
-   **Solution Display**: Renders the found pentomino placements onto the board canvas, with distinct colors for each piece.