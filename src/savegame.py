"""
src/savegame.py
===============
SaveManager — JSON persistence for game progress.

Save layout
-----------
{
  "version":   1,
  "current":   <state-dict>,            # state to load on "Continue"
  "snapshots": [<state-dict>, ...]      # ring buffer of recent waves (oldest first)
}

A `state-dict` captures everything needed to restore a game session:
    gold, wave, day_timer
    castle    : { hp, max_hp, upgrade_level }
    pond      : { current_rate, decay_timer }
    inventory : { size, slots: [ {item, count} | None, ... ] }
    towers    : [ { col, row, type, level, hp } ]

Snapshots are pushed at the START of each wave (i.e. when the player has
finished the previous wave and the new wave's resources are settled).
On game-over the player can rewind to ~5 waves back by loading the
oldest snapshot in the ring buffer.
"""

from __future__ import annotations
import json
import os
from typing import Optional

import config as C


def state_to_dict(gs) -> dict:
    """Serialise a GameState into a plain JSON-safe dict."""
    return {
        "gold":      int(gs.gold),
        "wave":      int(gs.wave),
        "day_timer": float(gs.day_timer),
        "castle": {
            "hp":            int(gs.castle.hp),
            "max_hp":        int(gs.castle.max_hp),
            "upgrade_level": int(gs.castle.upgrade_level),
        },
        "pond": {
            "current_rate": float(gs.pond.current_rate),
            "decay_timer":  float(gs.pond.decay_timer),
        },
        "hero": {
            "upgrades": dict(getattr(gs.hero, "upgrades", {})),
        },
        "inventory": gs.inventory.to_dict(),
        "towers": [
            {
                "col":         t.col,
                "row":         t.row,
                "type":        t.tower_type,
                "level":       t.level,
                "hp":          float(t.hp),
                "target_mode": getattr(t, "target_mode", "CLOSEST"),
            }
            for t in gs.towers
        ],
        # Plants placed on the farm map.  Each entry carries the species,
        # grid position, and elapsed growth time so a saved plant resumes
        # at the same growth stage (or stays ripe) on the next load.
        "farm": gs.farm.to_dict() if hasattr(gs, "farm") else {"plants": []},
    }


class SaveManager:
    """Static helpers around the JSON save file."""

    # ── File ops ──────────────────────────────────────────────────────────

    @staticmethod
    def exists() -> bool:
        return os.path.exists(C.SAVE_FILE)

    @staticmethod
    def load() -> Optional[dict]:
        """Return the parsed save file, or None if missing / corrupt."""
        if not SaveManager.exists():
            return None
        try:
            with open(C.SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "current" not in data:
                return None
            data.setdefault("snapshots", [])
            return data
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def write(current: dict, snapshots: list[dict]) -> None:
        payload = {
            "version":   1,
            "current":   current,
            "snapshots": snapshots,
        }
        try:
            with open(C.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass

    @staticmethod
    def delete() -> None:
        if SaveManager.exists():
            try:
                os.remove(C.SAVE_FILE)
            except OSError:
                pass

    # ── Snapshot helpers ─────────────────────────────────────────────────

    @staticmethod
    def push_snapshot(snapshots: list[dict], snap: dict) -> list[dict]:
        """Append snapshot, trim oldest so length <= SAVE_MAX_SNAPSHOTS."""
        snapshots = list(snapshots)
        snapshots.append(snap)
        if len(snapshots) > C.SAVE_MAX_SNAPSHOTS:
            snapshots = snapshots[-C.SAVE_MAX_SNAPSHOTS:]
        return snapshots

    @staticmethod
    def pick_rewind(snapshots: list[dict], current_wave: int) -> Optional[dict]:
        """
        Choose the snapshot that represents ~SAVE_REWIND_WAVES waves earlier.

        Snapshots are ordered oldest → newest.  We want the most recent
        snapshot whose wave <= current_wave - SAVE_REWIND_WAVES.  If none
        match (e.g. the player died before 5 waves elapsed), fall back to
        the oldest available snapshot.
        """
        if not snapshots:
            return None
        target = current_wave - C.SAVE_REWIND_WAVES
        candidate = None
        for snap in snapshots:
            try:
                w = int(snap.get("wave", 1))
            except (TypeError, ValueError):
                w = 1
            if w <= target:
                candidate = snap
        return candidate or snapshots[0]
