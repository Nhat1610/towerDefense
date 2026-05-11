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


def main() -> None:
    pygame.init()
    pygame.display.set_caption("Tower Defense  —  IT003 Data Structures Project")

    screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))

    while True:
        menu   = MenuScreen(screen)
        action = menu.run()

        if action == "quit":
            break

        if action == "new":
            SaveManager.delete()
            Game(screen).run()
        elif action == "continue":
            data = SaveManager.load()
            Game(screen, load_state=data).run()
        else:
            break

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
