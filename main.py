"""
main.py — Entry point for the Tower Defense game.

Run:
    python main.py

Requirements:
    pip install pygame
"""

import sys
import pygame
import config as C
from src.menu import MenuScreen
from src.game import Game
from src.savegame import SaveManager
from src.settings import Settings
from src.audio import music


def main() -> None:
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        # Audio device unavailable (headless / muted host) — MusicManager
        # will detect this and silently degrade to a no-op.
        pass
    pygame.display.set_caption("Tower Defense  —  IT003 Data Structures Project")

    screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))

    settings = Settings.load()
    music.init()
    music.set_volume(settings.music_volume)

    while True:
        # Menu always shows the calmer DAY track.  Idempotent if already on it.
        music.set_phase("DAY")

        menu   = MenuScreen(screen, settings)
        action = menu.run()

        if action == "quit":
            break

        if action == "new":
            SaveManager.delete()
            Game(screen, settings=settings).run()
        elif action == "continue":
            data = SaveManager.load()
            Game(screen, load_state=data, settings=settings).run()
        else:
            break

    music.shutdown()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
