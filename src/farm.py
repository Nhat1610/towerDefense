"""
src/farm.py
===========
Farm map state — Plant entities placed on a grid of plots.

The farm is a separate "scene" of the game.  The hero walks into a portal
behind the castle to enter it; once there, monsters can't reach the hero
and towers can't be placed.  Plots inside the farm rectangle accept Plant
items dragged from the inventory; over time each plant ticks through 4
growth stages and, once ripe, can be clicked to harvest a Supplier item.

Coordinates are grid-cell indices (col, row), matching the rest of the game.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Iterable

import config as C


@dataclass
class Plant:
    """One plant occupying a single farm plot."""

    plant_type: str
    col: int
    row: int
    growth_t: float = 0.0           # seconds elapsed since planting

    def update(self, dt: float) -> None:
        """Tick the growth timer (capped to total growth time)."""
        total = float(C.PLANT_DEFS[self.plant_type]["growth_seconds"])
        if self.growth_t < total:
            self.growth_t = min(total, self.growth_t + dt)

    @property
    def stage(self) -> int:
        """Current growth stage 0..(stages-1).

        The number of growth stages is detected at sprite-load time and
        varies per plant species (some have 4, some have 5).
        """
        total  = float(C.PLANT_DEFS[self.plant_type]["growth_seconds"])
        ratio  = self.growth_t / total if total > 0 else 1.0
        stages = self._stage_count()
        idx = int(ratio * stages)
        return max(0, min(stages - 1, idx))

    @property
    def ripe(self) -> bool:
        return self.stage >= self._stage_count() - 1

    def _stage_count(self) -> int:
        """Resolve actual frame count from the loaded sprite sheet, fallback to config."""
        try:
            from src.assets import Assets
            frames = Assets._plant_frames.get(self.plant_type)
            if frames:
                return len(frames)
        except Exception:
            pass
        return C.PLANT_GROWTH_STAGES

    @property
    def progress(self) -> float:
        total = float(C.PLANT_DEFS[self.plant_type]["growth_seconds"])
        return min(1.0, self.growth_t / total) if total > 0 else 1.0

    def to_dict(self) -> dict:
        return {
            "type":     self.plant_type,
            "col":      int(self.col),
            "row":      int(self.row),
            "growth_t": float(self.growth_t),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plant":
        return cls(
            plant_type=d["type"],
            col=int(d.get("col", 0)),
            row=int(d.get("row", 0)),
            growth_t=float(d.get("growth_t", 0.0)),
        )


class FarmState:
    """Holds every plant placed on the farm map and provides plot lookup."""

    def __init__(self) -> None:
        self.plants: list[Plant] = []

    # ── Plot helpers ──────────────────────────────────────────────────────

    @staticmethod
    def plot_rect_cells() -> tuple[int, int, int, int]:
        return C.FARM_PLOT_RECT  # (col0, row0, w, h)

    @classmethod
    def is_plot(cls, col: int, row: int) -> bool:
        c0, r0, w, h = C.FARM_PLOT_RECT
        return (c0 <= col < c0 + w) and (r0 <= row < r0 + h)

    def plant_at(self, col: int, row: int) -> Optional[Plant]:
        for p in self.plants:
            if p.col == col and p.row == row:
                return p
        return None

    # ── Mutation ──────────────────────────────────────────────────────────

    def plant(self, plant_type: str, col: int, row: int) -> bool:
        """Place a new plant on (col,row).  Returns False if invalid/occupied."""
        if not self.is_plot(col, row):
            return False
        if plant_type not in C.PLANT_DEFS:
            return False
        if self.plant_at(col, row) is not None:
            return False
        self.plants.append(Plant(plant_type=plant_type, col=col, row=row))
        return True

    def harvest(self, col: int, row: int) -> Optional[str]:
        """Harvest a ripe plant at (col,row).  Returns the supplier item id, else None."""
        p = self.plant_at(col, row)
        if p is None or not p.ripe:
            return None
        supplier = C.PLANT_DEFS[p.plant_type]["supplier"]
        self.plants.remove(p)
        return supplier

    def update(self, dt: float) -> None:
        """Tick every plant's growth timer."""
        for p in self.plants:
            p.update(dt)

    # ── Persistence ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"plants": [p.to_dict() for p in self.plants]}

    @classmethod
    def from_dict(cls, d: dict) -> "FarmState":
        out = cls()
        for pd in d.get("plants", []):
            try:
                out.plants.append(Plant.from_dict(pd))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def __iter__(self) -> Iterable[Plant]:
        return iter(self.plants)
