"""
src/audio.py
============
MusicManager — background music with day/night crossfade.

The two tracks (day.mp3 and night.mp3) are loaded once as
`pygame.mixer.Sound` and played on dedicated channels.  Switching phase
crossfades between them over MUSIC_CROSSFADE_S seconds by ramping one
channel's volume down while the other ramps up.

Exposed as a module-level singleton `music` so the main menu, game loop,
and settings overlay all share the same playback state.

If pygame.mixer fails to initialise or one of the audio files is missing,
the manager silently degrades to a no-op so the game stays runnable.
"""

from __future__ import annotations
import os
import pygame

import config as C


# Reserved channel indices for the two music tracks.  Picked high enough
# to leave channels 0-5 free for any future SFX layer.
_CH_DAY   = 6
_CH_NIGHT = 7


class MusicManager:
    """Singleton — use the module-level `music` instance."""

    def __init__(self) -> None:
        self._volume: float = C.DEFAULT_MUSIC_VOLUME
        self._current_phase: str | None = None     # "DAY" | "NIGHT" | None
        self._fade_t: float = 0.0                  # 0 .. MUSIC_CROSSFADE_S
        self._fading: bool = False
        self._day_snd:   pygame.mixer.Sound  | None = None
        self._night_snd: pygame.mixer.Sound  | None = None
        self._day_ch:    pygame.mixer.Channel | None = None
        self._night_ch:  pygame.mixer.Channel | None = None
        self._available: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def init(self) -> None:
        """Initialise mixer and load the two tracks.  Safe to call once."""
        if self._available:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Make sure we have enough channels for both music tracks plus
            # whatever the default count gave us for future SFX use.
            need = max(8, pygame.mixer.get_num_channels())
            pygame.mixer.set_num_channels(need)

            self._day_snd   = self._safe_load(C.MUSIC_DAY_PATH)
            self._night_snd = self._safe_load(C.MUSIC_NIGHT_PATH)
            self._day_ch    = pygame.mixer.Channel(_CH_DAY)
            self._night_ch  = pygame.mixer.Channel(_CH_NIGHT)
            self._available = (
                self._day_snd is not None and self._night_snd is not None
            )
        except pygame.error:
            self._available = False

    @staticmethod
    def _safe_load(path: str) -> pygame.mixer.Sound | None:
        if not os.path.exists(path):
            return None
        try:
            return pygame.mixer.Sound(path)
        except pygame.error:
            return None

    def shutdown(self) -> None:
        if not self._available:
            return
        try:
            if self._day_ch:
                self._day_ch.stop()
            if self._night_ch:
                self._night_ch.stop()
        except pygame.error:
            pass

    # ── Public API ────────────────────────────────────────────────────────

    def set_phase(self, phase: str) -> None:
        """Switch to the DAY or NIGHT track, crossfading if already playing.

        Idempotent — calling with the same phase the manager is already
        on (or already crossfading INTO) is a no-op, so the game loop
        can call this every frame without restarting the crossfade timer.
        """
        if not self._available:
            return
        phase = "DAY" if phase == "DAY" else "NIGHT"
        if phase == self._current_phase:
            # Already on (or fading into) this phase — let the in-flight
            # crossfade finish; never reset _fade_t mid-fade.
            return

        if self._current_phase is None:
            # First time — start the target track at the user's volume.
            self._start(phase, volume=self._volume)
            self._current_phase = phase
            self._fading = False
            self._fade_t = 0.0
            return

        # Crossfade — ensure the target channel is playing at volume 0,
        # then ramp it up while ramping the previous channel down.
        target_ch = self._channel_for(phase)
        if target_ch is not None and not target_ch.get_busy():
            self._start(phase, volume=0.0)
        self._current_phase = phase
        self._fading = True
        self._fade_t = 0.0

    def set_volume(self, v: float) -> None:
        """Update master music volume in [0, 1].  Applies live."""
        self._volume = max(0.0, min(1.0, float(v)))
        if not self._available:
            return
        if self._fading:
            # The fade tick will pick up the new volume on its next update.
            return
        ch = self._channel_for(self._current_phase) if self._current_phase else None
        if ch is not None:
            ch.set_volume(self._volume)
        # Make sure the inactive channel stays silent.
        other = "NIGHT" if self._current_phase == "DAY" else "DAY"
        other_ch = self._channel_for(other)
        if other_ch is not None:
            other_ch.set_volume(0.0)

    def get_volume(self) -> float:
        return self._volume

    def update(self, dt: float) -> None:
        """Drive the crossfade.  Call every frame regardless of pause."""
        if not self._available or not self._fading:
            return
        self._fade_t += dt
        ratio = min(1.0, self._fade_t / max(0.001, C.MUSIC_CROSSFADE_S))

        new_ch = self._channel_for(self._current_phase)
        old_phase = "NIGHT" if self._current_phase == "DAY" else "DAY"
        old_ch = self._channel_for(old_phase)

        if new_ch is not None:
            new_ch.set_volume(self._volume * ratio)
        if old_ch is not None:
            old_ch.set_volume(self._volume * (1.0 - ratio))

        if ratio >= 1.0:
            self._fading = False
            if old_ch is not None:
                old_ch.stop()

    # ── Internals ─────────────────────────────────────────────────────────

    def _start(self, phase: str, volume: float) -> None:
        snd = self._sound_for(phase)
        ch  = self._channel_for(phase)
        if snd is None or ch is None:
            return
        ch.play(snd, loops=-1)
        ch.set_volume(volume)

    def _sound_for(self, phase: str) -> pygame.mixer.Sound | None:
        return self._day_snd if phase == "DAY" else self._night_snd

    def _channel_for(self, phase: str | None) -> pygame.mixer.Channel | None:
        if phase == "DAY":
            return self._day_ch
        if phase == "NIGHT":
            return self._night_ch
        return None


# Module-level singleton — import as `from src.audio import music`.
music = MusicManager()
