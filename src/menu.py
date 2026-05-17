"""
src/menu.py
===========
MenuScreen — start menu shown before the game begins.

Returns one of "new", "continue", or "quit" from run().
A "Continue" button is shown only when a save file exists.

Also exposes GameOverScreen which lets the player either start a fresh
game or rewind ~SAVE_REWIND_WAVES waves back from a snapshot.
"""

from __future__ import annotations
import math
import random
import pygame

import config as C
from src.savegame import SaveManager
from src.settings import Settings
from src.settings_overlay import SettingsOverlay
from src.audio import music


class _Button:
    """A simple clickable button with hover state and an enabled flag."""

    def __init__(self, rect: pygame.Rect, label: str,
                 font: pygame.font.Font, enabled: bool = True) -> None:
        self.rect    = rect
        self.label   = label
        self.font    = font
        self.enabled = enabled

    def draw(self, surface: pygame.Surface, hovered: bool) -> None:
        if not self.enabled:
            bg, border, text = (24, 24, 34), (60, 60, 80), C.UI_DIM
        elif hovered:
            bg, border, text = C.UI_SELECTED, C.UI_GOLD, C.UI_GOLD
        else:
            bg, border, text = C.UI_PANEL, C.UI_BORDER, C.UI_TEXT
        pygame.draw.rect(surface, bg,     self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=6)
        lbl = self.font.render(self.label, True, text)
        surface.blit(lbl, (
            self.rect.centerx - lbl.get_width()  // 2,
            self.rect.centery - lbl.get_height() // 2,
        ))

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


def _draw_tower(surface: pygame.Surface, cx: int, cy: int,
                ttype: str, scale: float = 1.0) -> None:
    """Draw a small decorative tower for the menu background."""
    s = scale
    base_w, base_h = int(36 * s), int(30 * s)
    top_w,  top_h  = int(28 * s), int(20 * s)

    colors = {
        "BALLISTA": (C.TOWER_BALLISTA_BASE, C.TOWER_BALLISTA_TOP),
        "CANNON":   (C.TOWER_CANNON_BASE,   C.TOWER_CANNON_TOP),
        "TESLA":    (C.TOWER_TESLA_BASE,     C.TOWER_TESLA_TOP),
        "ICE":      (C.TOWER_ICE_BASE,       C.TOWER_ICE_TOP),
        "FLAME":    (C.TOWER_FLAME_BASE,     C.TOWER_FLAME_TOP),
    }
    base_col, top_col = colors.get(ttype, (C.STONE_MID, C.STONE_LIGHT))

    base_rect = pygame.Rect(cx - base_w // 2, cy - base_h, base_w, base_h)
    top_rect  = pygame.Rect(cx - top_w  // 2, cy - base_h - top_h,
                            top_w, top_h)

    pygame.draw.rect(surface, base_col, base_rect, border_radius=3)
    pygame.draw.rect(surface, top_col,  top_rect,  border_radius=3)

    m_w = max(4, int(7 * s))
    m_h = max(3, int(6 * s))
    gap = (top_w - 3 * m_w) // 4
    for i in range(3):
        mx = top_rect.x + gap + i * (m_w + gap)
        my = top_rect.y - m_h
        pygame.draw.rect(surface, top_col,
                         pygame.Rect(mx, my, m_w, m_h + 2))

    if ttype == "TESLA":
        glow_surf = pygame.Surface((int(20 * s), int(20 * s)), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*C.TOWER_TESLA_GLOW, 80),
                           (int(10 * s), int(10 * s)), int(10 * s))
        surface.blit(glow_surf, (cx - int(10 * s),
                                 top_rect.centery - int(10 * s)))


def _draw_decorative_castle(surface: pygame.Surface,
                             cx: int, cy: int) -> None:
    pygame.draw.rect(surface, C.STONE_MID,
                     pygame.Rect(cx - 55, cy - 70, 110, 70))
    pygame.draw.rect(surface, C.STONE_DARK,
                     pygame.Rect(cx - 65, cy - 95, 32, 95))
    pygame.draw.rect(surface, C.STONE_DARK,
                     pygame.Rect(cx + 33, cy - 95, 32, 95))
    pygame.draw.rect(surface, C.GATE_DARK,
                     pygame.Rect(cx - 18, cy - 40, 36, 40))
    for i in range(3):
        pygame.draw.rect(surface, C.STONE_LIGHT,
                         pygame.Rect(cx - 63 + i * 11, cy - 106, 8, 12))
    for i in range(3):
        pygame.draw.rect(surface, C.STONE_LIGHT,
                         pygame.Rect(cx + 35 + i * 11, cy - 106, 8, 12))
    pygame.draw.circle(surface, C.WINDOW_GLOW, (cx, cy - 52), 6)


# ══════════════════════════════════════════════════════════════════════════════
# Start menu
# ══════════════════════════════════════════════════════════════════════════════

class MenuScreen:
    """
    Full-screen start menu.

    Usage:
        menu   = MenuScreen(screen)
        action = menu.run()   # → "new", "continue", or "quit"
    """

    def __init__(self, screen: pygame.Surface,
                 settings: Settings | None = None) -> None:
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self.settings = settings if settings is not None else Settings.load()

        self._font_title    = pygame.font.SysFont("consolas", 64, bold=True)
        self._font_subtitle = pygame.font.SysFont("consolas", 20)
        self._font_btn      = pygame.font.SysFont("consolas", 24, bold=True)
        self._font_hint     = pygame.font.SysFont("consolas", 15)

        cx = C.SCREEN_WIDTH  // 2
        cy = C.SCREEN_HEIGHT // 2

        btn_w, btn_h = 280, 50

        self._btn_new = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 20, btn_w, btn_h),
            "NEW GAME",
            self._font_btn,
        )
        self._btn_continue = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 80, btn_w, btn_h),
            "CONTINUE",
            self._font_btn,
            enabled=SaveManager.exists(),
        )
        self._btn_settings = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 140, btn_w, btn_h),
            "SETTINGS",
            self._font_btn,
        )
        self._btn_quit = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 200, btn_w, btn_h),
            "QUIT",
            self._font_btn,
        )

        self._settings_overlay = SettingsOverlay(screen, self.settings)

        rng = random.Random(42)
        self._stars = [
            (rng.randint(0, C.SCREEN_WIDTH),
             rng.randint(0, C.SCREEN_HEIGHT),
             rng.choice([1, 1, 1, 2]))
            for _ in range(120)
        ]

        self._anim_t: float = 0.0

    def run(self) -> str:
        # Refresh the continue-button state in case a save was deleted between menus
        self._btn_continue.enabled = SaveManager.exists()
        while True:
            dt = self.clock.tick(C.FPS) / 1000.0
            self._anim_t += dt
            music.update(dt)

            action = self._handle_events()
            if action:
                return action

            self._draw()
            pygame.display.flip()

    def _handle_events(self) -> str | None:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            # Settings overlay takes input priority while open
            if self._settings_overlay.visible:
                self._settings_overlay.handle_event(event)
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    return "continue" if self._btn_continue.enabled else "new"
                if event.key == pygame.K_n:
                    return "new"
                if event.key == pygame.K_c and self._btn_continue.enabled:
                    return "continue"
                if event.key == pygame.K_s:
                    self._settings_overlay.open()
                    continue
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._btn_new.contains(mouse):
                    return "new"
                if self._btn_continue.contains(mouse):
                    return "continue"
                if self._btn_settings.contains(mouse):
                    self._settings_overlay.open()
                    continue
                if self._btn_quit.contains(mouse):
                    return "quit"
        return None

    def _draw(self) -> None:
        s  = self.screen
        cx = C.SCREEN_WIDTH  // 2
        cy = C.SCREEN_HEIGHT // 2

        s.fill(C.UI_BG)
        self._draw_stars(s)

        tower_positions = [
            (120,  C.SCREEN_HEIGHT - 20, "BALLISTA", 1.4),
            (300,  C.SCREEN_HEIGHT - 20, "CANNON",   1.2),
            (cx,   C.SCREEN_HEIGHT - 20, "TESLA",    1.6),
            (C.SCREEN_WIDTH - 300, C.SCREEN_HEIGHT - 20, "ICE",   1.2),
            (C.SCREEN_WIDTH - 120, C.SCREEN_HEIGHT - 20, "FLAME", 1.4),
        ]
        for tx, ty, ttype, scale in tower_positions:
            _draw_tower(s, tx, ty, ttype, scale)

        _draw_decorative_castle(s, cx, cy - 200)

        pygame.draw.line(s, C.UI_BORDER,
                         (cx - 300, cy - 88), (cx + 300, cy - 88), 1)

        pulse = 1.0 + 0.012 * math.sin(self._anim_t * 2.0)
        title_surf = self._font_title.render("TOWER DEFENSE", True, C.UI_GOLD)
        scaled_w = int(title_surf.get_width()  * pulse)
        scaled_h = int(title_surf.get_height() * pulse)
        title_scaled = pygame.transform.smoothscale(
            title_surf, (scaled_w, scaled_h)
        )
        s.blit(title_scaled, (cx - scaled_w // 2, cy - 80))

        mouse = pygame.mouse.get_pos()
        self._btn_new.draw(s,      self._btn_new.contains(mouse))
        self._btn_continue.draw(s, self._btn_continue.contains(mouse))
        self._btn_settings.draw(s, self._btn_settings.contains(mouse))
        self._btn_quit.draw(s,     self._btn_quit.contains(mouse))

        if not self._btn_continue.enabled:
            note = self._font_hint.render(
                "(no saved game found)", True, C.UI_DIM
            )
            s.blit(note, (cx - note.get_width() // 2,
                          self._btn_continue.rect.bottom + 4))

        hint = self._font_hint.render(
            "N = New  ·  C = Continue  ·  S = Settings  ·  ESC = Quit",
            True, C.UI_DIM,
        )
        s.blit(hint, (cx - hint.get_width() // 2, C.SCREEN_HEIGHT - 32))

        # Modal settings panel sits on top of everything else
        self._settings_overlay.draw()

    def _draw_stars(self, surface: pygame.Surface) -> None:
        for x, y, r in self._stars:
            brightness = int(
                160 + 50 * math.sin(self._anim_t * 0.8 + x * 0.05)
            )
            pygame.draw.circle(surface, (brightness, brightness, brightness),
                               (x, y), r)


# ══════════════════════════════════════════════════════════════════════════════
# Game-over overlay
# ══════════════════════════════════════════════════════════════════════════════

class GameOverScreen:
    """
    Modal shown when the castle is destroyed.

    `run()` blocks until the player chooses:
        "new"    → start a brand-new game
        "rewind" → load the rewind snapshot (only if available)
        "quit"   → exit
    """

    def __init__(self, screen: pygame.Surface,
                 wave_reached: int, can_rewind: bool) -> None:
        self.screen        = screen
        self.clock         = pygame.time.Clock()
        self.wave_reached  = wave_reached
        self.can_rewind    = can_rewind

        self._font_big = pygame.font.SysFont("consolas", 64, bold=True)
        self._font_med = pygame.font.SysFont("consolas", 22, bold=True)
        self._font_btn = pygame.font.SysFont("consolas", 22, bold=True)
        self._font_sm  = pygame.font.SysFont("consolas", 15)

        cx = C.SCREEN_WIDTH  // 2
        cy = C.SCREEN_HEIGHT // 2
        btn_w, btn_h = 320, 52

        self._btn_new = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 20, btn_w, btn_h),
            "NEW GAME",
            self._font_btn,
        )
        self._btn_rewind = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 80, btn_w, btn_h),
            f"CONTINUE (-{C.SAVE_REWIND_WAVES} WAVES)",
            self._font_btn,
            enabled=can_rewind,
        )
        self._btn_quit = _Button(
            pygame.Rect(cx - btn_w // 2, cy + 140, btn_w, btn_h),
            "QUIT TO MENU",
            self._font_btn,
        )

        self._anim_t: float = 0.0

    def run(self) -> str:
        while True:
            dt = self.clock.tick(C.FPS) / 1000.0
            self._anim_t += dt

            action = self._handle_events()
            if action:
                return action

            self._draw()
            pygame.display.flip()

    def _handle_events(self) -> str | None:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_n:
                    return "new"
                if event.key == pygame.K_c and self.can_rewind:
                    return "rewind"
                if event.key == pygame.K_ESCAPE:
                    return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._btn_new.contains(mouse):
                    return "new"
                if self._btn_rewind.contains(mouse):
                    return "rewind"
                if self._btn_quit.contains(mouse):
                    return "quit"
        return None

    def _draw(self) -> None:
        s  = self.screen
        cx = C.SCREEN_WIDTH  // 2
        cy = C.SCREEN_HEIGHT // 2

        # Dim the previous frame already on screen
        veil = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 200))
        s.blit(veil, (0, 0))

        # Title
        pulse = 0.9 + 0.1 * math.sin(self._anim_t * 2.5)
        title_surf = self._font_big.render("GAME OVER", True, (255, 90, 80))
        sw = int(title_surf.get_width()  * pulse)
        sh = int(title_surf.get_height() * pulse)
        scaled = pygame.transform.smoothscale(title_surf, (sw, sh))
        s.blit(scaled, (cx - sw // 2, cy - 200))

        sub = self._font_med.render(
            f"Castle fell on wave {self.wave_reached}", True, C.UI_TEXT,
        )
        s.blit(sub, (cx - sub.get_width() // 2, cy - 110))

        mouse = pygame.mouse.get_pos()
        self._btn_new.draw(s,    self._btn_new.contains(mouse))
        self._btn_rewind.draw(s, self._btn_rewind.contains(mouse))
        self._btn_quit.draw(s,   self._btn_quit.contains(mouse))

        if not self.can_rewind:
            note = self._font_sm.render(
                f"(need at least {C.SAVE_REWIND_WAVES} waves of progress to rewind)",
                True, C.UI_DIM,
            )
            s.blit(note, (cx - note.get_width() // 2,
                          self._btn_rewind.rect.bottom + 4))
