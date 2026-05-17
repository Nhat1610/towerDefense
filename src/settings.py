"""
src/settings.py
===============
Settings — persistent user preferences (currently: music volume).

Stored in `settings.json` next to the savegame.  Kept separate from the
savegame so that pressing NEW GAME (which wipes savegame.json) does not
reset the player's volume preference.

Layout:
    {
      "music_volume": 0.6
    }
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict

import config as C


@dataclass
class Settings:
    music_volume: float = C.DEFAULT_MUSIC_VOLUME

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from disk, returning defaults if file is missing/corrupt."""
        if not os.path.exists(C.SETTINGS_FILE):
            return cls()
        try:
            with open(C.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            vol = float(data.get("music_volume", C.DEFAULT_MUSIC_VOLUME))
            return cls(music_volume=max(0.0, min(1.0, vol)))
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        """Persist settings to disk. Silently ignores write errors."""
        try:
            with open(C.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except OSError:
            pass

    def set_music_volume(self, v: float) -> None:
        self.music_volume = max(0.0, min(1.0, float(v)))
