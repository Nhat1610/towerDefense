"""
algorithms/priority_queue.py
============================
TowerTargetQueue — a min-heap priority queue used by towers to select
which enemy to shoot.

IT003 ASSIGNMENT: Implement every method marked with
    raise NotImplementedError(...)

Priority modes
--------------
Each tower can target enemies using one of three strategies:
    "CLOSEST"   — enemy with smallest distance to the tower fires first
    "WEAKEST"   — enemy with lowest remaining HP fires first
    "STRONGEST" — enemy with highest remaining HP fires first

The queue uses a **min-heap** internally. The "priority value" inserted
into the heap depends on the mode:
    CLOSEST   → distance (lower = higher priority)
    WEAKEST   → current HP (lower = higher priority)
    STRONGEST → negative of current HP  (lower value = higher HP)

Usage example (inside Tower.find_target):
    q = TowerTargetQueue(mode="CLOSEST")
    for enemy in enemies_in_range:
        dist = math.hypot(enemy.x - self.x, enemy.y - self.y)
        q.enqueue(enemy, dist)
    target = q.dequeue()   # returns the highest-priority enemy
"""

from __future__ import annotations
from typing import Any, Optional


class TowerTargetQueue:
    """
    Min-heap priority queue for tower targeting.

    Each element is stored as a (priority, tie_breaker, data) tuple
    so that equal priorities never trigger a comparison on the data object.
    """

    def __init__(self, mode: str = "CLOSEST") -> None:
        """
        Parameters
        ----------
        mode : str
            One of "CLOSEST", "WEAKEST", "STRONGEST".
            Stored as self.mode and used by convenience method enqueue_enemy().
        """
        self.mode: str = mode
        self._heap: list[tuple[float, int, Any]] = []
        self._counter: int = 0   # tie-breaker: insertion order

    # ── Core heap operations ───────────────────────────────────────────────

    def enqueue(self, data: Any, priority: float) -> None:
        """
        Insert *data* with the given *priority* into the heap.

        Lower priority value = higher urgency (min-heap semantics).

        Steps:
            1. Append (priority, self._counter, data) to self._heap.
            2. Increment self._counter.
            3. Call _sift_up() to restore heap property.
        """
        self._heap.append((priority, self._counter, data))
        self._counter += 1
        self._sift_up(len(self._heap)-1)

    def dequeue(self) -> Optional[Any]:
        """
        Remove and return the data with the **lowest** priority value.

        Returns None if the queue is empty.

        Steps (standard heap pop):
            1. If empty, return None.
            2. Swap root with last element.
            3. Pop the last element (save its data).
            4. Call _sift_down(0) to restore heap property.
            5. Return the saved data.
        """
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
        """
        Move the element at *index* upward until the heap property is restored.

        Parent of index i is at (i - 1) // 2.
        Swap with parent while heap[index] < heap[parent].
        """
        while index > 0 and self._heap[index] < self._heap[(index-1)//2]:
            self._heap[index], self._heap[(index-1)//2] = self._heap[(index-1)//2],self._heap[index]
            index = (index-1)//2

    def _sift_down(self, index: int) -> None:
        """
        Move the element at *index* downward until the heap property is restored.

        Children of index i are at 2*i+1 (left) and 2*i+2 (right).
        Swap with the smaller child while that child < current element.
        """
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
