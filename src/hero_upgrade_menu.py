"""
src/hero_upgrade_menu.py
========================
HeroUpgradeMenu — modal panel for buying hero stat upgrades.

Opens when the player clicks the "Hero" row on the right-side HUD.  Lays
out one row per upgrade kind (HP / ARMOR / SPEED / DAMAGE) showing the
current tier, next-tier preview, and a BUY button.  Closes via X / ESC
/ I just like the other modal overlays.

The menu is presentation-only — `Game._upgrade_hero(kind)` performs the
gold deduction and calls `Hero.apply_upgrade(kind)`.
"""

from __future__ import annotations
import pygame

import config as C


class HeroUpgradeMenu:
    """Modal hero-stat upgrade window."""

    PANEL_W = 360
    PANEL_H = 420

    # Order rows are presented in (matches HERO_UPGRADE_DEFS keys)
    ORDER = ("HP", "ARMOR", "SPEED", "DAMAGE")

    LABELS = {
        "HP":     "Max HP",
        "ARMOR":  "Armor",
        "SPEED":  "Move Speed",
        "DAMAGE": "Attack Damage",
    }

    UNITS = {
        "HP":     "hp",
        "ARMOR":  "",
        "SPEED":  "px/s",
        "DAMAGE": "dmg",
    }

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.visible: bool = False

        self._font_title = pygame.font.SysFont("consolas", 22, bold=True)
        self._font_med   = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_sm    = pygame.font.SysFont("consolas", 12)
        self._font_xs    = pygame.font.SysFont("consolas", 11)

        # Panel rect — centred on screen by default
        self.rect = pygame.Rect(
            (C.SCREEN_WIDTH - self.PANEL_W) // 2,
            (C.SCREEN_HEIGHT - self.PANEL_H) // 2,
            self.PANEL_W,
            self.PANEL_H,
        )

        # Click hit-boxes (rebuilt every draw)
        self.buy_btn_rects:  dict[str, pygame.Rect] = {}
        self.close_btn_rect: pygame.Rect | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def toggle(self) -> None:
        self.visible = not self.visible

    def is_visible(self) -> bool:
        return self.visible

    # ── Click routing ─────────────────────────────────────────────────────

    def hit_buy(self, mx: int, my: int) -> str | None:
        """Return the upgrade kind under (mx, my), or None."""
        for kind, r in self.buy_btn_rects.items():
            if r.collidepoint(mx, my):
                return kind
        return None

    def hit_close(self, mx: int, my: int) -> bool:
        return (self.close_btn_rect is not None
                and self.close_btn_rect.collidepoint(mx, my))

    def consumes_click(self, mx: int, my: int) -> bool:
        return self.visible and self.rect.collidepoint(mx, my)

    # ── Drawing ───────────────────────────────────────────────────────────

    def draw(self, hero, gold: int) -> None:
        if not self.visible:
            return
        s = self.screen

        # Dim background
        veil = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        s.blit(veil, (0, 0))

        # Panel
        pygame.draw.rect(s, C.UI_BG,     self.rect, border_radius=10)
        pygame.draw.rect(s, C.UI_BORDER, self.rect, 3, border_radius=10)

        # Title
        title = self._font_title.render("HERO UPGRADES", True, C.UI_GOLD)
        s.blit(title, (self.rect.x + 18, self.rect.y + 14))

        # Close button
        cb = pygame.Rect(self.rect.right - 36, self.rect.y + 14, 24, 24)
        pygame.draw.rect(s, (90, 30, 30), cb, border_radius=4)
        pygame.draw.rect(s, (220, 80, 80), cb, 1, border_radius=4)
        x_lbl = self._font_med.render("X", True, (255, 220, 220))
        s.blit(x_lbl, (cb.centerx - x_lbl.get_width() // 2,
                       cb.centery - x_lbl.get_height() // 2))
        self.close_btn_rect = cb

        # Gold readout
        gold_lbl = self._font_sm.render(f"Your gold: {gold}", True, C.UI_DIM)
        s.blit(gold_lbl, (self.rect.x + 18, self.rect.y + 42))

        # ── One row per upgrade kind ──────────────────────────────────────
        self.buy_btn_rects.clear()
        row_h = 76
        first_y = self.rect.y + 76
        for i, kind in enumerate(self.ORDER):
            y = first_y + i * row_h
            self._draw_row(hero, gold, kind, y)

    def _draw_row(self, hero, gold: int, kind: str, y: int) -> None:
        s    = self.screen
        defn = C.HERO_UPGRADE_DEFS[kind]
        cur  = hero.upgrades.get(kind, 0)
        max_t = int(defn["max_tier"])
        cost  = int(defn["cost"])
        step  = float(defn["step"])
        unit  = self.UNITS.get(kind, "")
        label = self.LABELS.get(kind, kind)

        # Row background
        row_rect = pygame.Rect(self.rect.x + 16, y, self.PANEL_W - 32, 64)
        pygame.draw.rect(s, (30, 32, 50), row_rect, border_radius=6)
        pygame.draw.rect(s, C.UI_BORDER, row_rect, 1, border_radius=6)

        # Label + tier counter
        name_lbl = self._font_med.render(label, True, C.UI_TEXT)
        s.blit(name_lbl, (row_rect.x + 12, row_rect.y + 8))

        tier_lbl = self._font_sm.render(
            f"Tier {cur} / {max_t}", True, C.UI_DIM,
        )
        s.blit(tier_lbl, (row_rect.x + 12, row_rect.y + 28))

        # Current stat preview
        stat_val = self._stat_value(hero, kind)
        next_val = stat_val + step  # what one more tier would yield
        if cur < max_t:
            preview = f"{stat_val:.0f} → {next_val:.0f} {unit}".strip()
        else:
            preview = f"{stat_val:.0f} {unit} (MAX)".strip()
        prev_lbl = self._font_xs.render(preview, True, (180, 220, 255))
        s.blit(prev_lbl, (row_rect.x + 12, row_rect.y + 46))

        # BUY button
        bb = pygame.Rect(row_rect.right - 100, row_rect.y + 16, 88, 32)
        affordable = (cur < max_t) and (gold >= cost)
        if cur >= max_t:
            bg, bd, txt = (40, 40, 55), (80, 80, 100), "MAX"
        elif affordable:
            bg, bd, txt = (40, 110, 60), (130, 220, 140), f"BUY  {cost}g"
        else:
            bg, bd, txt = (60, 30, 30), (140, 70, 70), f"{cost}g"
        pygame.draw.rect(s, bg, bb, border_radius=5)
        pygame.draw.rect(s, bd, bb, 2, border_radius=5)
        bbl = self._font_sm.render(
            txt, True,
            (220, 255, 220) if affordable else C.UI_DIM,
        )
        s.blit(bbl, (bb.centerx - bbl.get_width() // 2,
                     bb.centery - bbl.get_height() // 2))
        # Only register the rect when buying is actually allowed
        if cur < max_t:
            self.buy_btn_rects[kind] = bb

    @staticmethod
    def _stat_value(hero, kind: str) -> float:
        """Read the current stat that this upgrade kind controls."""
        if kind == "HP":
            return float(hero.max_hp)
        if kind == "ARMOR":
            return float(hero.armor)
        if kind == "SPEED":
            return float(hero.base_speed)
        if kind == "DAMAGE":
            return float(hero.atk1_damage)
        return 0.0
