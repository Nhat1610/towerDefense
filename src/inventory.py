"""
src/inventory.py
================
Inventory — fixed-capacity bag holding stackable items.

Layout:
    self.slots : list[dict | None] of length INVENTORY_SIZE
                 each slot is either None (empty) or
                 {"item": <ITEM_ID>, "count": <int>}.

Adding an item first looks for an existing slot of the same kind to stack into,
then falls back to the first empty slot.  Adding fails (returns False) if the
inventory is full and no matching stack exists.
"""

from __future__ import annotations
from typing import Optional

import config as C


class Inventory:
    """A 20-slot stackable inventory."""

    def __init__(self, size: int = C.INVENTORY_SIZE) -> None:
        self.size: int = size
        self.slots: list[Optional[dict]] = [None] * size

    # ── Mutation ──────────────────────────────────────────────────────────

    def add(self, item_id: str, count: int = 1) -> bool:
        """Add `count` of `item_id`.  Stacks first, then takes empty slot.

        Returns True if all items fit, False if there's no room.
        """
        if item_id not in C.ITEM_DEFS or count <= 0:
            return False

        stackable = C.ITEM_DEFS[item_id].get("stackable", True)

        # Try to stack into existing slot of the same kind
        if stackable:
            for slot in self.slots:
                if slot is not None and slot["item"] == item_id:
                    slot["count"] += count
                    return True

        # Otherwise find the first empty slot
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = {"item": item_id, "count": count}
                return True

        return False  # full

    def remove(self, item_id: str, count: int = 1) -> bool:
        """Remove `count` of `item_id`.  Returns True on success, False if not enough."""
        if count <= 0:
            return False
        # Tally available count first
        if self.count(item_id) < count:
            return False

        remaining = count
        for i, slot in enumerate(self.slots):
            if slot is None or slot["item"] != item_id:
                continue
            take = min(slot["count"], remaining)
            slot["count"] -= take
            remaining -= take
            if slot["count"] <= 0:
                self.slots[i] = None
            if remaining <= 0:
                return True
        return remaining <= 0

    def use_slot(self, slot_index: int) -> Optional[str]:
        """Consume one item from the given slot.  Returns the item_id used, or None."""
        if not (0 <= slot_index < self.size):
            return None
        slot = self.slots[slot_index]
        if slot is None or slot["count"] <= 0:
            return None
        item_id = slot["item"]
        slot["count"] -= 1
        if slot["count"] <= 0:
            self.slots[slot_index] = None
        return item_id

    def clear_item(self, item_id: str) -> int:
        """Remove every stack of `item_id`.  Returns total count removed."""
        total = 0
        for i, slot in enumerate(self.slots):
            if slot is not None and slot["item"] == item_id:
                total += slot["count"]
                self.slots[i] = None
        return total

    # ── Inspection ────────────────────────────────────────────────────────

    def count(self, item_id: str) -> int:
        """Return the total number of `item_id` across all slots."""
        return sum(s["count"] for s in self.slots
                   if s is not None and s["item"] == item_id)

    def is_full(self) -> bool:
        return all(s is not None for s in self.slots)

    def has_room_for(self, item_id: str) -> bool:
        """True if `item_id` can be added (existing stack or empty slot)."""
        if item_id not in C.ITEM_DEFS:
            return False
        if C.ITEM_DEFS[item_id].get("stackable", True):
            for slot in self.slots:
                if slot is not None and slot["item"] == item_id:
                    return True
        return any(s is None for s in self.slots)

    def used_slots(self) -> int:
        return sum(1 for s in self.slots if s is not None)

    # ── Persistence ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "size":  self.size,
            "slots": [
                None if s is None else {"item": s["item"], "count": int(s["count"])}
                for s in self.slots
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        size = int(data.get("size", C.INVENTORY_SIZE))
        inv  = cls(size)
        slots = data.get("slots", [])
        for i, s in enumerate(slots[:size]):
            if isinstance(s, dict) and s.get("item") in C.ITEM_DEFS:
                inv.slots[i] = {"item": s["item"], "count": int(s.get("count", 0))}
        return inv
