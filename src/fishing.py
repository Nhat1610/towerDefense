"""
src/fishing.py
==============
FishingMinigame — click-timing minigame triggered by the pond's "Cast" button.

State machine:
    IDLE                 : not active.
    AWAITING_FISH        : button was pressed; waiting on the appearance roll.
    ACTIVE               : minigame running — slider sweeping, green zone visible.
    SUCCESS / FAILURE    : terminal states; resolved by the game on the next tick.

Mechanics:
    - Three rounds.  Each round picks a NEW random green-zone position; widths
      shrink per round (FISHING_GREEN_WIDTHS).
    - A white slider sweeps left↔right at FISHING_SLIDER_SPEED full passes/sec.
    - Player clicks once per round.  If the slider is over the green band the
      round succeeds and width shrinks for the next; otherwise FAILURE.
    - After 3 successes the minigame resolves SUCCESS.
    - If FISHING_TIMEOUT seconds pass without resolution the fish escapes.
"""

from __future__ import annotations
import random

import config as C


class FishingMinigame:
    """Encapsulates the click-timing fishing minigame."""

    IDLE          = "idle"
    AWAITING_FISH = "awaiting"
    ACTIVE        = "active"
    SUCCESS       = "success"
    FAILURE       = "failure"

    def __init__(self) -> None:
        self.state: str = self.IDLE
        self.hits: int = 0                     # successful clicks so far
        self.green_start: float = 0.0          # green-zone start  (0..1)
        self.green_width: float = 0.0          # green-zone width  (0..1)
        self.slider_pos: float = 0.0           # current slider position (0..1)
        self._slider_dir: float = 1.0          # +1 → right, -1 → left
        self.timer: float = 0.0                # elapsed time in current state
        self._appear_delay: float = 0.0        # AWAITING_FISH wait before answer
        self._will_appear: bool = False        # outcome of the appearance roll

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, current_rate: float) -> None:
        """Trigger a new fishing attempt.  Rolls appearance after a short delay."""
        self.state          = self.AWAITING_FISH
        self.hits           = 0
        self.timer          = 0.0
        self._appear_delay  = random.uniform(0.6, 1.6)
        self._will_appear   = random.random() < max(0.0, min(1.0, current_rate))
        self.slider_pos     = 0.0
        self._slider_dir    = 1.0

    def cancel(self) -> None:
        self.state = self.IDLE

    def is_running(self) -> bool:
        return self.state in (self.AWAITING_FISH, self.ACTIVE)

    def update(self, dt: float) -> None:
        if self.state == self.AWAITING_FISH:
            self.timer += dt
            if self.timer >= self._appear_delay:
                if self._will_appear:
                    self._begin_round(0)
                else:
                    # No fish appeared — close silently.
                    self.state = self.IDLE
            return

        if self.state == self.ACTIVE:
            self.timer += dt
            self.slider_pos += self._slider_dir * C.FISHING_SLIDER_SPEED * dt
            if self.slider_pos >= 1.0:
                self.slider_pos = 1.0
                self._slider_dir = -1.0
            elif self.slider_pos <= 0.0:
                self.slider_pos = 0.0
                self._slider_dir = 1.0

            if self.timer >= C.FISHING_TIMEOUT:
                self.state = self.FAILURE

    def click(self) -> None:
        """Handle a player click during ACTIVE state."""
        if self.state != self.ACTIVE:
            return
        in_zone = self.green_start <= self.slider_pos <= self.green_start + self.green_width
        if in_zone:
            self.hits += 1
            if self.hits >= C.FISHING_HITS_REQUIRED:
                self.state = self.SUCCESS
            else:
                self._begin_round(self.hits)
        else:
            self.state = self.FAILURE

    def consume_result(self) -> str | None:
        """Return 'success' / 'failure' if the minigame just resolved, else None.

        Resets to IDLE after returning a terminal result.
        """
        if self.state == self.SUCCESS:
            self.state = self.IDLE
            return "success"
        if self.state == self.FAILURE:
            self.state = self.IDLE
            return "failure"
        return None

    # ── Internal ──────────────────────────────────────────────────────────

    def _begin_round(self, round_idx: int) -> None:
        idx = min(round_idx, len(C.FISHING_GREEN_WIDTHS) - 1)
        self.green_width = C.FISHING_GREEN_WIDTHS[idx]
        # Green zone never clips off the bar
        self.green_start = random.uniform(0.05, 0.95 - self.green_width)
        self.timer       = 0.0
        self.state       = self.ACTIVE
