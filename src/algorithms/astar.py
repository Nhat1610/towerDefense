"""
algorithms/astar.py
===================
AStarPathfinder — grid-based A* pathfinding for enemy navigation.

IT003 ASSIGNMENT: Implement every method marked with
    raise NotImplementedError(...)

Grid system
-----------
The game world is divided into GRID_COLS × GRID_ROWS cells.
Each cell is CELL_SIZE × CELL_SIZE pixels.

Cell types (stored in GameState.grid[row][col]):
    "EMPTY"    — traversable, no tower
    "PATH"     — pre-marked path cells (always traversable by enemies)
    "TOWER"    — blocked by a placed tower
    "BUILDING" — blocked by castle / pond / shop

Coordinate conversions (provided as static helpers):
    pixel  → cell:  (px // CELL_SIZE, py // CELL_SIZE) → (col, row)
    cell   → pixel: (col * CELL_SIZE + CELL_SIZE//2, row * CELL_SIZE + CELL_SIZE//2)

Algorithm overview
------------------
A* finds the shortest path from *start_cell* to *goal_cell* using:
    f(n) = g(n) + h(n)
    g(n) = actual cost from start to n  (1 per cardinal step)
    h(n) = heuristic estimate to goal   (Manhattan distance)

The open set is a min-heap of (f, g, cell) tuples.
The closed set is a Python set of already-expanded cells.

Return value: list of (col, row) tuples from start to goal (inclusive),
              or an empty list [] if no path exists.
"""

from __future__ import annotations
import heapq
from typing import Optional

from config import CELL_SIZE, GRID_COLS, GRID_ROWS


class AStarPathfinder:
    
    BLOCKED = {"TOWER", "BUILDING"}

    def __init__(self, grid: list[list[str]]) -> None:
   
        self.grid = grid

    # ── Public interface ───────────────────────────────────────────────────

    def find_path(
        self,
        start: tuple[int, int],
        goal:  tuple[int, int],
    ) -> list[tuple[int, int]]:

        open_set = []
        open_set.append((self.heuristic(start,goal), 0, start))
        heapq.heapify(open_set)
        came_from = {}
        g_score = {start:0}
        while len(open_set):
            cell = heapq.heappop(open_set)
            heapq.heapify(open_set)
            if cell[2] == goal: return self.reconstruct_path(came_from= came_from, current=cell[2])
            valid_cell = self.get_neighbours(cell[2])
            new_g = g_score[cell[2]]+1
            for neighbours in valid_cell:
                if new_g < g_score.get(neighbours, int(1e18)):
                    g_score[neighbours] = new_g
                    f = new_g + self.heuristic(neighbours, goal)
                    open_set.append((f,new_g, neighbours))
                    heapq.heapify(open_set)
                    came_from[neighbours] = cell[2]
        return []

    # ── Helpers ────────────────────────────────────────────────────────────

    def heuristic(
        self,
        cell: tuple[int, int],
        goal: tuple[int, int],
    ) -> int:
        
        return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

    def get_neighbours(
        self,
        cell: tuple[int, int],
    ) -> list[tuple[int, int]]:
        
        move = [[1,0], [0,1], [-1,0], [0,-1]]
        valid = []
        for move_x, move_y in move:
            new_x, new_y = move_x+cell[0], move_y+cell[1]
            if self.is_walkable(new_x, new_y):
                valid.append((new_x, new_y))
        return valid

    def reconstruct_path(
        self,
        came_from: dict[tuple[int, int], tuple[int, int]],
        current:   tuple[int, int],
    ) -> list[tuple[int, int]]:
        
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return path[::-1]

    def is_walkable(self, col: int, row: int) -> bool:
        """Return True if (col, row) is in bounds and not blocked."""
        if not (0 <= col < GRID_COLS and 0 <= row < GRID_ROWS):
            return False
        return self.grid[row][col] not in self.BLOCKED

    # ── Coordinate utilities ───────────────────────────────────────────────

    @staticmethod
    def pixel_to_cell(px: float, py: float) -> tuple[int, int]:
        """Convert pixel position to (col, row) grid cell."""
        return int(px // CELL_SIZE), int(py // CELL_SIZE)

    @staticmethod
    def cell_to_pixel(col: int, row: int) -> tuple[int, int]:
        """Return the pixel center of grid cell (col, row)."""
        return (
            col * CELL_SIZE + CELL_SIZE // 2,
            row * CELL_SIZE + CELL_SIZE // 2,
        )
