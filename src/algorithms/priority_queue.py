

from __future__ import annotations
from typing import Any, Optional


class TowerTargetQueue:


    def __init__(self, mode: str = "CLOSEST") -> None:

        self.mode: str = mode
        self._heap: list[tuple[float, int, Any]] = []
        self._counter: int = 0   # tie-breaker: insertion order

    # ── Core heap operations ───────────────────────────────────────────────

    def enqueue(self, data: Any, priority: float) -> None:

        self._heap.append((priority, self._counter, data))
        self._counter += 1
        self._sift_up(len(self._heap)-1)

    def dequeue(self) -> Optional[Any]:

        if not len(self._heap): return None
        self._heap[0], self._heap[len(self._heap)-1] =  self._heap[len(self._heap)-1], self._heap[0]
        last = self._heap[len(self._heap)-1]
        self._heap.pop()
        self._sift_down(0)
        return last[2]


    def peek(self) -> Optional[Any]:
        """Return the highest-priority data WITHOUT removing it.
        Returns None if empty."""
        if len(self._heap):
            return self._heap[0][2]

    def clear(self) -> None:
        """Remove all elements."""
        self._heap = []

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    # ── Heap helpers ───────────────────────────────────────────────────────

    def _sift_up(self, index: int) -> None:

        while index > 0 and self._heap[index] < self._heap[(index-1)//2]:
            self._heap[index], self._heap[(index-1)//2] = self._heap[(index-1)//2],self._heap[index]
            index = (index-1)//2

    def _sift_down(self, index: int) -> None:
 
        size = len(self._heap)
        while True:
            smallest = index
            if 2*index + 1 < size and self._heap[2*index+1] < self._heap[index]:
                smallest = 2*index+1  
            if 2*index + 2 < size and self._heap[2*index + 2] < self._heap[index]:
                smallest = 2*index+2
            if smallest == index:break
            self._heap[smallest],self._heap[index] = self._heap[index], self._heap[smallest]
            index = smallest

    # ── Convenience wrapper ────────────────────────────────────────────────

    def enqueue_enemy(self, enemy: Any, tower_x: float, tower_y: float) -> None:
        """
        Compute priority automatically from self.mode and enqueue the enemy.

        Parameters
        ----------
        enemy    : any Enemy object — must have attributes .x, .y, .hp
        tower_x  : tower's pixel x-coordinate
        tower_y  : tower's pixel y-coordinate

        Modes:
            CLOSEST   → priority = Euclidean distance
            WEAKEST   → priority = enemy.hp
            STRONGEST → priority = -enemy.hp   (negate so min-heap pops highest)
        """
        import math
        if self.mode == "CLOSEST":
            priority = math.hypot(enemy.x - tower_x, enemy.y - tower_y)
        elif self.mode == "WEAKEST":
            priority = enemy.hp
        elif self.mode == "STRONGEST":
            priority = -enemy.hp
        else:
            priority = 0.0
        self.enqueue(enemy, priority)
