"""
src/settings_overlay.py
=======================
SettingsOverlay — modal panel with a Music Volume slider.

Shown from the main-menu SETTINGS button and from the in-game pause
screen.  Changes apply live to the MusicManager and are persisted to
settings.json on close.
"""

from __future__ import annotations
import pygame

import config as C
from src.audio import music
from src.settings import Settings


class SettingsOverlay:
    """Modal volume-settings panel.  Reused by menu.py and game.py."""

    PANEL_W = 460
    PANEL_H = 240

    SLIDER_W = 320
    SLIDER_H = 8
    KNOB_R   = 10

    def __init__(self, screen: pygame.Surface, settings: Settings) -> None:
        self.screen   = screen
        self.settings = settings
        self.visible: bool = False
        self._dragging: bool = False

        self._font_title = pygame.font.SysFont("consolas", 26, bold=True)
        self._font_med   = pygame.font.SysFont("consolas", 18, bold=True)
        self._font_sm    = pygame.font.SysFont("consolas", 14)

        self.panel_rect = pygame.Rect(
            (C.SCREEN_WIDTH  - self.PANEL_W) // 2,
            (C.SCREEN_HEIGHT - self.PANEL_H) // 2,
            self.PANEL_W, self.PANEL_H,
        )
        self.slider_rect = pygame.Rect(
            self.panel_rect.x + (self.PANEL_W - self.SLIDER_W) // 2,
            self.panel_rect.y + 130,
            self.SLIDER_W, self.SLIDER_H,
        )
        self.close_rect = pygame.Rect(
            self.panel_rect.right - 110,
            self.panel_rect.bottom - 50,
            90, 34,
        )

    # ── Toggling ──────────────────────────────────────────────────────────

    def open(self) -> None:
        self.visible = True
        self._dragging = False

    def close(self) -> None:
        if not self.visible:
            return
        self.visible = False
        self._dragging = False
        self.settings.save()

    # ── Event handling ────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed by this overlay."""
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.close()
            return True   # swallow all keys while modal is up

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.close_rect.collidepoint(mx, my):
                self.close()
                return True
            if (self._knob_hitbox().collidepoint(mx, my)
                    or self._track_hitbox().collidepoint(mx, my)):
                self._dragging = True
                self._apply_slider_x(mx)
                return True
            if not self.panel_rect.collidepoint(mx, my):
                self.close()
                return True
            return True   # other clicks inside panel: swallow

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                self.settings.save()
                return True
            return True

        if event.type == pygame.MOUSEMOTION:
            if self._dragging:
                self._apply_slider_x(event.pos[0])
                return True
            # Don't swallow plain motion so cursor updates elsewhere stay live.
            return False

        # Swallow any other event type that fires while we're modal so
        # game logic underneath doesn't react to it.
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEWHEEL):
            return True

        return False

    def _apply_slider_x(self, mx: int) -> None:
        x = max(self.slider_rect.x, min(self.slider_rect.right, mx))
        ratio = (x - self.slider_rect.x) / max(1, self.slider_rect.w)
        self.settings.set_music_volume(ratio)
        music.set_volume(self.settings.music_volume)

    def _knob_x(self) -> int:
        return self.slider_rect.x + int(
            self.settings.music_volume * self.slider_rect.w
        )

    def _knob_hitbox(self) -> pygame.Rect:
        kx = self._knob_x()
        ky = self.slider_rect.centery
        return pygame.Rect(kx - self.KNOB_R, ky - self.KNOB_R,
                           self.KNOB_R * 2, self.KNOB_R * 2)

    def _track_hitbox(self) -> pygame.Rect:
        # Pad the click target vertically so the slim track is easy to hit.
        return self.slider_rect.inflate(0, 28)

    # ── Drawing ───────────────────────────────────────────────────────────

    def draw(self) -> None:
        if not self.visible:
            return
        s = self.screen

        # Dim background
        veil = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 170))
        s.blit(veil, (0, 0))

        # Panel
        pygame.draw.rect(s, C.UI_BG,     self.panel_rect, border_radius=10)
        pygame.draw.rect(s, C.UI_BORDER, self.panel_rect, 3, border_radius=10)

        # Title
        title = self._font_title.render("SETTINGS", True, C.UI_GOLD)
        s.blit(title, (self.panel_rect.centerx - title.get_width() // 2,
                       self.panel_rect.y + 18))

        # Label + percentage
        lbl = self._font_med.render("Music Volume", True, C.UI_TEXT)
        s.blit(lbl, (self.slider_rect.x,
                     self.slider_rect.y - 42))
        pct = int(round(self.settings.music_volume * 100))
        val = self._font_med.render(f"{pct}%", True, C.UI_GOLD)
        s.blit(val, (self.slider_rect.right - val.get_width(),
                     self.slider_rect.y - 42))

        # Slider track
        pygame.draw.rect(s, (60, 60, 80), self.slider_rect, border_radius=4)
        fill_w = int(self.settings.music_volume * self.slider_rect.w)
        if fill_w > 0:
            fill = pygame.Rect(self.slider_rect.x, self.slider_rect.y,
                               fill_w, self.slider_rect.h)
            pygame.draw.rect(s, C.UI_GOLD, fill, border_radius=4)

        # Knob
        kx = self._knob_x()
        ky = self.slider_rect.centery
        pygame.draw.circle(s, (240, 220, 120), (kx, ky), self.KNOB_R)
        pygame.draw.circle(s, (40, 40, 60), (kx, ky), self.KNOB_R, 2)

        # Close button
        pygame.draw.rect(s, C.UI_PANEL,  self.close_rect, border_radius=6)
        pygame.draw.rect(s, C.UI_BORDER, self.close_rect, 2, border_radius=6)
        c_lbl = self._font_med.render("CLOSE", True, C.UI_TEXT)
        s.blit(c_lbl, (self.close_rect.centerx - c_lbl.get_width() // 2,
                       self.close_rect.centery - c_lbl.get_height() // 2))

        # Hint
        hint = self._font_sm.render(
            "Drag the slider  ·  ESC / Click outside to close",
            True, C.UI_DIM,
        )
        s.blit(hint, (self.panel_rect.centerx - hint.get_width() // 2,
                      self.panel_rect.bottom - 16))
