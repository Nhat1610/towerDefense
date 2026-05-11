"""
src/hud.py
==========
HUD — draws the right-side UI panel (320 × 720 px).

Panel layout:
  ┌─────────────────────────────┐
  │  TOWER DEFENSE  [wave/phase]│  ← title bar
  │─────────────────────────────│
  │  Gold: 200   Fish: 5        │  ← resources
  │─────────────────────────────│
  │  SELECT TOWER               │  ← tower buttons (1-5)
  │  [Ballista] [Cannon]        │
  │  [Tesla]    [Ice]   [Flame] │
  │─────────────────────────────│
  │  SELECTED:  Ballista  Lv1   │  ← selected tower info
  │  Cost: 100g                 │
  │  Dmg:40  Range:200  Rate:1  │
  │  Description...             │
  │─────────────────────────────│
  │  [  START WAVE  ]           │  ← action button
  │─────────────────────────────│
  │  Castle HP ████████░░ 500   │  ← castle status
  │  Wave: 1 / 4                │
  │─────────────────────────────│
  │  Controls:                  │  ← help
  │  1-5: select tower          │
  │  LClick: place              │
  │  RClick: sell (50%)         │
  │  SPACE: start wave          │
  └─────────────────────────────┘
"""

from __future__ import annotations
import math
import pygame

import config as C


class HUD:
    """Renders the right-side UI panel."""

    PANEL_X = C.GAME_WIDTH       # 960
    PANEL_W = C.UI_WIDTH          # 320
    PAD     = 14

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self._time: float = 0.0

        # Fonts
        self._font_title = pygame.font.SysFont("consolas", 18, bold=True)
        self._font_med   = pygame.font.SysFont("consolas", 15, bold=True)
        self._font_sm    = pygame.font.SysFont("consolas", 13)
        self._font_xs    = pygame.font.SysFont("consolas", 11)
        self._font_bold  = pygame.font.SysFont("consolas", 14, bold=True)

        # Button rects (built once, used for click detection in game.py)
        self.tower_btn_rects: dict[str, pygame.Rect] = {}
        self.start_wave_rect:    pygame.Rect | None = None
        self.sell_fish_rect:     pygame.Rect | None = None
        self.buy_food_rect:      pygame.Rect | None = None
        self.buy_btn_rect:       pygame.Rect | None = None  # confirm-purchase button
        self.inventory_btn_rect: pygame.Rect | None = None
        self.upgrade_castle_rect: pygame.Rect | None = None
        self.upgrade_tower_rect: pygame.Rect | None = None
        # Priority-mode buttons in the upgrade panel — click to retarget
        self.priority_btn_rects: dict[str, pygame.Rect] = {}
        # Hero status row — click opens the hero upgrade menu
        self.hero_status_rect: pygame.Rect | None = None

        # ── Scrollable / toggleable item menu state ─────────────────────────
        self.menu_open:        bool   = True
        self.scroll_offset:    int    = 0       # row offset
        self.menu_toggle_rect: pygame.Rect | None = None
        self.scroll_up_rect:   pygame.Rect | None = None
        self.scroll_down_rect: pygame.Rect | None = None
        self.menu_clip_rect:   pygame.Rect | None = None  # area where wheel scrolls

        # Layout config for the item menu
        self._items_per_row:     int = 2
        self._visible_rows:      int = 3

        # Pre-built panel background
        self._bg_surf = pygame.Surface((self.PANEL_W, C.SCREEN_HEIGHT))
        self._bg_surf.fill(C.UI_BG)
        # Subtle gradient stripe on left edge
        for i in range(6):
            alpha_surf = pygame.Surface((2, C.SCREEN_HEIGHT), pygame.SRCALPHA)
            alpha_surf.fill((80, 80, 120, max(0, 60 - i * 10)))
            self._bg_surf.blit(alpha_surf, (i, 0))

    def update(self, dt: float) -> None:
        self._time += dt

    # ══════════════════════════════════════════════════════════════════════
    # Main draw
    # ══════════════════════════════════════════════════════════════════════

    def draw(
        self,
        gold:          int,
        wave:          int,
        phase:         str,
        selected_type: str,
        castle_hp:     int,
        castle_max_hp: int,
        hero_hp:       float = 0,
        hero_max_hp:   float = 0,
        hero_alive:    bool  = True,
        hero_stamina:  float = 0.0,
        hero_stamina_max: float = 1.0,
        message:       str = "",
        day_timer:     float = 0.0,
        # ── New: inventory + probabilistic fishing ────────────────────────
        inventory=None,
        pond_rate:    float = C.FISH_RATE_INITIAL,
        castle_upgrade_lv: int = 0,
        castle_upgrade_cost: int = 0,
        selected_tower=None,
    ) -> None:
        s = self.screen
        px = self.PANEL_X

        # Background
        s.blit(self._bg_surf, (px, 0))
        # Left border line
        pygame.draw.line(s, C.UI_BORDER, (px, 0), (px, C.SCREEN_HEIGHT), 2)

        # Reset transient button rects each frame so collapsed sections
        # don't keep stale hit-boxes alive.
        self.buy_food_rect       = None
        self.buy_btn_rect        = None
        self.inventory_btn_rect  = None
        self.upgrade_castle_rect = None
        self.upgrade_tower_rect  = None
        self.priority_btn_rects.clear()

        # Pull fish counts from the inventory (they live there now)
        fish_common = inventory.count("FISH_COMMON") if inventory is not None else 0
        fish_rare   = inventory.count("FISH_RARE")   if inventory is not None else 0
        food_count  = inventory.count("FISH_FOOD")   if inventory is not None else 0
        inv_used    = inventory.used_slots() if inventory is not None else 0
        inv_size    = inventory.size if inventory is not None else 0

        y = self._draw_title(y=0, phase=phase, wave=wave)
        y = self._draw_resources(y, gold, fish_common, fish_rare,
                                 food_count, pond_rate)
        y = self._draw_divider(y)
        y = self._draw_hero_status(y, hero_hp, hero_max_hp, hero_alive,
                                   hero_stamina, hero_stamina_max)
        y = self._draw_divider(y)
        y = self._draw_tower_buttons(y, selected_type, gold)
        y = self._draw_divider(y)
        if selected_tower is not None:
            y = self._draw_tower_upgrade_panel(y, selected_tower, gold)
        else:
            y = self._draw_selected_info(y, selected_type, gold)
        y = self._draw_divider(y)
        y = self._draw_action_buttons(
            y, phase, fish_common + fish_rare, gold, day_timer,
            inv_used, inv_size,
        )
        y = self._draw_divider(y)
        y = self._draw_castle_status(
            y, castle_hp, castle_max_hp, wave,
            castle_upgrade_lv, castle_upgrade_cost, gold,
        )
        y = self._draw_divider(y)
        self._draw_help(y)

        if message:
            self._draw_message(message)

    # ══════════════════════════════════════════════════════════════════════
    # Sections
    # ══════════════════════════════════════════════════════════════════════

    def _draw_title(self, y, phase, wave) -> int:
        s  = self.screen
        px = self.PANEL_X

        # Title background
        phase_color = (20, 30, 60) if phase == "DAY" else (40, 10, 10)
        pygame.draw.rect(s, phase_color, (px, y, self.PANEL_W, 48))

        title_lbl = self._font_title.render("TOWER DEFENSE", True, C.UI_GOLD)
        s.blit(title_lbl, (px + self.PAD, y + 4))

        phase_str = "  Day Phase" if phase == "DAY" else "  Night Phase"
        phase_col = (100, 160, 255) if phase == "DAY" else (255, 100, 80)
        phase_lbl = self._font_sm.render(phase_str, True, phase_col)
        s.blit(phase_lbl, (px + self.PAD, y + 26))

        wave_lbl = self._font_sm.render(f"Wave {wave}", True, C.UI_DIM)
        s.blit(wave_lbl, (px + self.PANEL_W - wave_lbl.get_width() - self.PAD, y + 26))

        return y + 50

    def _draw_resources(self, y, gold, fish_common, fish_rare,
                        fish_food=0, pond_rate=C.FISH_RATE_INITIAL) -> int:
        """Draw gold + fish counts (common/rare) + fish-food count + pond catch-rate."""
        s  = self.screen
        px = self.PANEL_X

        pygame.draw.rect(s, C.UI_PANEL, (px, y, self.PANEL_W, 64))

        # Gold icon (circle + G)
        pygame.draw.circle(s, C.UI_GOLD, (px + self.PAD + 8, y + 14), 9)
        pygame.draw.circle(s, (200, 165, 0), (px + self.PAD + 8, y + 14), 9, 2)
        g_lbl = self._font_xs.render("G", True, (80, 50, 0))
        s.blit(g_lbl, (px + self.PAD + 5, y + 8))

        gold_lbl = self._font_bold.render(f" {gold:,}", True, C.UI_GOLD)
        s.blit(gold_lbl, (px + self.PAD + 20, y + 6))

        # Fish counts (common + rare)
        fish_x = px + self.PANEL_W // 2 + 10
        pygame.draw.ellipse(s, (100, 180, 255), (fish_x, y + 6, 18, 11))
        pygame.draw.polygon(s, (70, 140, 220),
                            [(fish_x + 18, y + 11), (fish_x + 24, y + 5), (fish_x + 24, y + 17)])
        fish_lbl = self._font_bold.render(
            f" {fish_common}c  {fish_rare}r", True, (150, 220, 255)
        )
        s.blit(fish_lbl, (fish_x + 26, y + 6))

        # Fish food count (mirrored from inventory) + pond rate %
        food_x = px + self.PAD
        food_y = y + 30
        pygame.draw.circle(s, (200, 150, 60), (food_x + 8, food_y + 10), 8)
        pygame.draw.circle(s, (250, 200, 80), (food_x + 8, food_y + 10), 8, 2)
        food_lbl = self._font_bold.render(
            f"  {fish_food}  food", True, (250, 210, 130),
        )
        s.blit(food_lbl, (food_x + 18, food_y + 2))

        rate_lbl = self._font_xs.render(
            f"Catch rate: {int(pond_rate * 100)}%", True, (180, 240, 180),
        )
        s.blit(rate_lbl, (px + self.PANEL_W // 2 + 10, food_y + 6))

        return y + 66

    def _draw_hero_status(self, y, hero_hp, hero_max_hp, hero_alive,
                           hero_stamina=0.0, hero_stamina_max=1.0) -> int:
        s   = self.screen
        px  = self.PANEL_X
        pad = self.PAD
        row_top = y                                 # remember for click rect

        hdr_color = C.UI_TEXT if hero_alive else C.UI_RED
        hdr = self._font_med.render("Hero", True, hdr_color)
        s.blit(hdr, (px + pad, y + 4))

        status_lbl = self._font_xs.render(
            "ALIVE" if hero_alive else "FALLEN — press R",
            True, C.UI_GREEN if hero_alive else C.UI_RED,
        )
        s.blit(status_lbl, (px + pad + 50, y + 6))

        # Subtle hint that the row is clickable
        hint = self._font_xs.render("[upgrade]", True, (140, 180, 230))
        s.blit(hint, (px + self.PANEL_W - pad - hint.get_width() - 2, y + 6))
        y += 24

        # HP bar
        ratio   = max(0.0, hero_hp / max(1, hero_max_hp))
        bar_x   = px + pad
        bar_w   = self.PANEL_W - pad * 2
        bar_h   = 12
        bar_col = C.HP_GREEN if ratio > 0.6 else (C.HP_YELLOW if ratio > 0.3 else C.HP_RED)
        pygame.draw.rect(s, C.HP_BG,   (bar_x, y, bar_w, bar_h), border_radius=3)
        if ratio > 0:
            pygame.draw.rect(s, bar_col,
                             (bar_x, y, int(bar_w * ratio), bar_h), border_radius=3)
        pygame.draw.rect(s, C.UI_BORDER, (bar_x, y, bar_w, bar_h), 1, border_radius=3)
        hp_lbl = self._font_xs.render(
            f"HP {int(hero_hp)} / {int(hero_max_hp)}", True, C.UI_TEXT
        )
        s.blit(hp_lbl, (bar_x + bar_w // 2 - hp_lbl.get_width() // 2, y + 1))
        y += bar_h + 4

        # Stamina bar (sprint resource)
        st_ratio = max(0.0, min(1.0,
                                hero_stamina / max(0.001, hero_stamina_max)))
        st_h = 6
        pygame.draw.rect(s, (40, 30, 20),
                         (bar_x, y, bar_w, st_h), border_radius=2)
        if st_ratio > 0:
            stam_col = (240, 220, 90) if st_ratio > 0.2 else (220, 120, 60)
            pygame.draw.rect(s, stam_col,
                             (bar_x, y, int(bar_w * st_ratio), st_h),
                             border_radius=2)
        pygame.draw.rect(s, C.UI_BORDER,
                         (bar_x, y, bar_w, st_h), 1, border_radius=2)

        # Register the entire status block as a clickable rect
        self.hero_status_rect = pygame.Rect(
            px + pad, row_top, bar_w, (y + st_h) - row_top,
        )

        return y + st_h + 6

    # ── Scroll / toggle controls ──────────────────────────────────────────

    def toggle_menu(self) -> None:
        self.menu_open = not self.menu_open

    def handle_scroll(self, direction: int) -> None:
        """direction>0 scrolls up, <0 scrolls down (mouse-wheel convention)."""
        if not self.menu_open:
            return
        max_scroll = self._max_scroll()
        # Wheel up (positive y in pygame.MOUSEWHEEL) → smaller offset
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset - direction))

    def _max_scroll(self) -> int:
        total_items = len(C.HUD_BUYABLE_TYPES)
        rows = (total_items + self._items_per_row - 1) // self._items_per_row
        return max(0, rows - self._visible_rows)

    def _draw_tower_buttons(self, y, selected_type, gold) -> int:
        s    = self.screen
        px   = self.PANEL_X
        pad  = self.PAD
        bw   = (self.PANEL_W - pad * 2 - 8) // 2   # button width
        bh   = 58
        gap  = 8

        # ── Header with toggle ────────────────────────────────────────────
        arrow = "▼" if self.menu_open else "▶"
        hdr_text = f"ITEMS  {arrow}   (M to toggle)"
        hdr_color = C.UI_TEXT if self.menu_open else C.UI_DIM
        hdr = self._font_med.render(hdr_text, True, hdr_color)
        s.blit(hdr, (px + pad, y + 6))
        # Whole header strip is clickable to toggle
        self.menu_toggle_rect = pygame.Rect(
            px + pad, y, self.PANEL_W - pad * 2, 24
        )
        y += 28

        # Always reset rects so old buttons don't trigger when menu collapses
        self.tower_btn_rects.clear()

        if not self.menu_open:
            # Show only the currently selected item as a small reminder
            if selected_type and selected_type in C.ALL_DEFS:
                defn = C.ALL_DEFS[selected_type]
                tag  = self._font_sm.render(
                    f"Selected: {defn['name']}  [{defn['hotkey']}]",
                    True, C.UI_GOLD,
                )
                s.blit(tag, (px + pad, y))
                y += 18
            self.scroll_up_rect = None
            self.scroll_down_rect = None
            self.menu_clip_rect = None
            return y + 4

        # ── Scroll arrows ──────────────────────────────────────────────────
        max_scroll = self._max_scroll()
        arrow_w   = 22
        ax        = px + self.PANEL_W - pad - arrow_w
        ay_top    = y
        ay_bot    = y + (bh + gap) * self._visible_rows - arrow_w

        # Visible area for buttons (mouse wheel scroll zone)
        self.menu_clip_rect = pygame.Rect(
            px + pad, y,
            self.PANEL_W - pad * 2 - arrow_w - 4,
            (bh + gap) * self._visible_rows,
        )

        # Up arrow
        up_active = self.scroll_offset > 0
        self.scroll_up_rect = pygame.Rect(ax, ay_top, arrow_w, arrow_w)
        pygame.draw.rect(s, C.UI_PANEL if up_active else (24, 24, 34),
                         self.scroll_up_rect, border_radius=4)
        pygame.draw.rect(s, C.UI_BORDER, self.scroll_up_rect, 1, border_radius=4)
        up_col = C.UI_TEXT if up_active else (60, 60, 80)
        pygame.draw.polygon(s, up_col, [
            (ax + arrow_w // 2, ay_top + 5),
            (ax + 5,             ay_top + arrow_w - 6),
            (ax + arrow_w - 5,   ay_top + arrow_w - 6),
        ])

        # Down arrow
        down_active = self.scroll_offset < max_scroll
        self.scroll_down_rect = pygame.Rect(ax, ay_bot, arrow_w, arrow_w)
        pygame.draw.rect(s, C.UI_PANEL if down_active else (24, 24, 34),
                         self.scroll_down_rect, border_radius=4)
        pygame.draw.rect(s, C.UI_BORDER, self.scroll_down_rect, 1, border_radius=4)
        down_col = C.UI_TEXT if down_active else (60, 60, 80)
        pygame.draw.polygon(s, down_col, [
            (ax + 5,             ay_bot + 5),
            (ax + arrow_w - 5,   ay_bot + 5),
            (ax + arrow_w // 2,  ay_bot + arrow_w - 5),
        ])

        # Scroll-bar track between arrows
        track_x = ax + arrow_w // 2 - 1
        track_y = ay_top + arrow_w + 2
        track_h = ay_bot - track_y - 2
        pygame.draw.rect(s, (40, 40, 55),
                         (track_x, track_y, 2, track_h))
        if max_scroll > 0:
            thumb_h = max(12, track_h * self._visible_rows //
                          max(1, max_scroll + self._visible_rows))
            thumb_y = track_y + (track_h - thumb_h) * self.scroll_offset // max_scroll
            pygame.draw.rect(s, C.UI_HIGHLIGHT,
                             (track_x - 2, thumb_y, 6, thumb_h),
                             border_radius=3)

        # ── Visible buttons ────────────────────────────────────────────────
        items = C.HUD_BUYABLE_TYPES
        start = self.scroll_offset * self._items_per_row
        end   = start + self._visible_rows * self._items_per_row
        visible = items[start:end]

        for i, ttype in enumerate(visible):
            row = i // self._items_per_row
            col = i %  self._items_per_row
            bx  = px + pad + col * (bw + gap)
            by  = y + row * (bh + gap)
            defn   = C.ALL_DEFS[ttype]
            is_sel = (ttype == selected_type)
            can_aff = (gold >= defn["cost"])
            is_def  = (defn.get("category") == "DEFENSE")

            # Button background
            if is_sel:
                pygame.draw.rect(s, C.UI_SELECTED, (bx, by, bw, bh), border_radius=5)
            elif can_aff:
                pygame.draw.rect(s, C.UI_HIGHLIGHT, (bx, by, bw, bh), border_radius=5)
            else:
                pygame.draw.rect(s, (25, 25, 35), (bx, by, bw, bh), border_radius=5)

            # Border (defense items get a slightly different border tint)
            if is_sel:
                border_c = C.UI_GOLD
            elif can_aff:
                border_c = (110, 110, 130) if is_def else C.UI_BORDER
            else:
                border_c = (40, 40, 55)
            pygame.draw.rect(s, border_c, (bx, by, bw, bh), 2, border_radius=5)

            # Small icon
            self._draw_tower_icon(s, bx + 18, by + bh // 2, ttype)

            # Name
            name_lbl = self._font_sm.render(defn["name"], True,
                                             C.UI_GOLD if is_sel else C.UI_TEXT)
            s.blit(name_lbl, (bx + 34, by + 6))

            # Cost
            cost_color = C.UI_GOLD if can_aff else C.UI_RED
            cost_lbl = self._font_xs.render(
                f"{defn['cost']}g  [{defn['hotkey']}]", True, cost_color
            )
            s.blit(cost_lbl, (bx + 34, by + 26))

            # Short description
            desc_lines = defn["description"].split("\n")
            for li, dl in enumerate(desc_lines[:2]):
                dl_lbl = self._font_xs.render(dl, True, C.UI_DIM)
                s.blit(dl_lbl, (bx + 34, by + 40 + li * 10))

            self.tower_btn_rects[ttype] = pygame.Rect(bx, by, bw, bh)

        return y + (bh + gap) * self._visible_rows + 6

    def _draw_tower_icon(self, s, cx, cy, ttype):
        """Tiny icon for the ITEMS button.

        - Combat towers (BALLISTA/CANNON/TESLA/ICE/FLAME) use sprite assets.
        - Walls / fences / spikes / barricades use the original vector icons
          (per user request to keep them in the legacy style).
        - FISH_FOOD has its own vector icon.
        """
        from src.assets import Assets

        non_combat = ("WALL", "FENCE", "SPIKE", "BARRICADE")

        # Combat tower → sprite scaled to ~30 px
        if ttype not in non_combat and ttype != "FISH_FOOD":
            sprite = Assets.tower(ttype, anim_t=0.0)
            if sprite is not None:
                sw, sh = sprite.get_size()
                max_dim = 30
                scale = min(max_dim / sw, max_dim / sh, 1.0)
                tw = max(1, int(sw * scale))
                th = max(1, int(sh * scale))
                icon = pygame.transform.scale(sprite, (tw, th)) if (tw, th) != (sw, sh) else sprite
                s.blit(icon, (cx - tw // 2, cy - th // 2))
                return

        # Original vector icons for walls / fences / spikes / barricades
        if ttype == "WALL":
            pygame.draw.rect(s, C.WALL_STONE, (cx - 8, cy - 7, 16, 14), border_radius=1)
            pygame.draw.line(s, C.WALL_DARK, (cx - 8, cy), (cx + 8, cy), 1)
            pygame.draw.line(s, C.WALL_DARK, (cx,     cy - 7), (cx,     cy), 1)
            pygame.draw.line(s, C.WALL_DARK, (cx - 4, cy),     (cx - 4, cy + 7), 1)
            pygame.draw.line(s, C.WALL_DARK, (cx + 4, cy),     (cx + 4, cy + 7), 1)
        elif ttype == "FENCE":
            for off in (-6, -2, 2, 6):
                pygame.draw.polygon(s, C.FENCE_WOOD, [
                    (cx + off,     cy + 8),
                    (cx + off + 3, cy + 8),
                    (cx + off + 3, cy - 5),
                    (cx + off + 1, cy - 7),
                    (cx + off,     cy - 5),
                ])
            pygame.draw.line(s, C.FENCE_DARK, (cx - 7, cy - 1), (cx + 9, cy - 1), 2)
            pygame.draw.line(s, C.FENCE_DARK, (cx - 7, cy + 4), (cx + 9, cy + 4), 2)
        elif ttype == "SPIKE":
            pygame.draw.rect(s, C.SPIKE_BASE, (cx - 8, cy + 3, 16, 6), border_radius=1)
            for off in (-6, -2, 2, 6):
                pts = [(cx + off - 2, cy + 3), (cx + off + 2, cy + 3), (cx + off, cy - 7)]
                pygame.draw.polygon(s, C.SPIKE_TIP, pts)
        elif ttype == "BARRICADE":
            pygame.draw.rect(s, C.BARRICADE_BAND, (cx - 9, cy - 7, 18, 14), border_radius=1)
            pygame.draw.rect(s, C.BARRICADE_STEEL, (cx - 7, cy - 5, 14, 10))
            pygame.draw.line(s, C.BARRICADE_BAND, (cx - 7, cy), (cx + 7, cy), 2)
            for rx in (cx - 6, cx + 5):
                pygame.draw.circle(s, C.BARRICADE_RIVET, (rx, cy - 4), 1)
                pygame.draw.circle(s, C.BARRICADE_RIVET, (rx, cy + 4), 1)
        elif ttype == "FISH_FOOD":
            pygame.draw.circle(s, (250, 200, 80), (cx, cy + 1), 8)
            pygame.draw.circle(s, (200, 150, 60), (cx, cy + 1), 8, 2)
            for ox, oy in ((-3, -2), (3, -2), (0, 3)):
                pygame.draw.circle(s, (160, 110, 40), (cx + ox, cy + oy + 1), 2)

    def _draw_selected_info(self, y, selected_type, gold) -> int:
        s  = self.screen
        px = self.PANEL_X
        pad = self.PAD

        if not selected_type:
            lbl = self._font_sm.render("Nothing selected", True, C.UI_DIM)
            s.blit(lbl, (px + pad, y + 6))
            return y + 26

        defn = C.ALL_DEFS[selected_type]
        is_defense = (defn.get("category") == "DEFENSE")
        title = f"  {defn['name']}" + ("" if is_defense else "  (Lv 1)")
        hdr = self._font_med.render(title, True, C.UI_GOLD)
        s.blit(hdr, (px + pad, y + 6))
        y += 28

        stats = [
            (f"Cost:     {defn['cost']}g", C.UI_GOLD),
            (f"HP:       {defn['hp']}",    C.UI_GREEN),
        ]
        if not is_defense or defn["damage"] > 0:
            stats.append((f"Damage:   {defn['damage']}", C.UI_RED))
        if defn["range"] > 0:
            stats.append((f"Range:    {defn['range']}px", C.UI_BLUE))
        if defn["fire_rate"] > 0:
            stats.append((f"Fire rate: {defn['fire_rate']}/s", C.UI_TEXT))
        elif is_defense:
            tag = "Passive trap" if defn["damage"] > 0 else "Pure barrier"
            stats.append((f"Type:     {tag}", (200, 200, 230)))
        if defn["splash"] > 0:
            stats.append((f"Splash:   {defn['splash']}px", (255, 160, 60)))
        if defn["slow"] > 0:
            stats.append((f"Slow:     {int(defn['slow']*100)}%", (150, 220, 255)))
        if defn["burn_dps"] > 0:
            stats.append((f"Burn DPS: {defn['burn_dps']}", (255, 130, 30)))
        if defn["chain"] > 0:
            stats.append((f"Chain:    {defn['chain']} enemies", C.TOWER_TESLA_GLOW))

        for stat, color in stats:
            lbl = self._font_sm.render(stat, True, color)
            s.blit(lbl, (px + pad, y))
            y += 16

        y += 2
        for line in defn["description"].split("\n"):
            lbl = self._font_xs.render(line, True, C.UI_DIM)
            s.blit(lbl, (px + pad, y))
            y += 14

        # ── BUY button (confirms purchase, item goes to inventory) ─────────
        y += 4
        bw = self.PANEL_W - pad * 2
        bh = 32
        cost = int(defn["cost"])
        can_afford = (gold >= cost)
        buy_rect = pygame.Rect(px + pad, y, bw, bh)
        bg = (40, 110, 60) if can_afford else (40, 40, 55)
        bd = (120, 220, 140) if can_afford else (80, 80, 100)
        pygame.draw.rect(s, bg, buy_rect, border_radius=5)
        pygame.draw.rect(s, bd, buy_rect, 2, border_radius=5)
        lbl = self._font_bold.render(
            f"BUY  {cost}g  >  Bag", True,
            (220, 255, 220) if can_afford else C.UI_DIM,
        )
        s.blit(lbl, (buy_rect.centerx - lbl.get_width() // 2,
                      buy_rect.centery - lbl.get_height() // 2))
        self.buy_btn_rect = buy_rect

        return y + bh + 6

    def _draw_tower_upgrade_panel(self, y, tower, gold) -> int:
        """Show stats and an Upgrade button for the tower the player clicked on."""
        s   = self.screen
        px  = self.PANEL_X
        pad = self.PAD

        title = self._font_med.render(
            f"Selected: {tower.name}  Lv {tower.level}",
            True, C.UI_GOLD,
        )
        s.blit(title, (px + pad, y + 6))
        y += 26

        defs_only = (getattr(tower, "category", "TOWER") == "DEFENSE")

        stats = [
            (f"Cell:      ({tower.col}, {tower.row})", C.UI_DIM),
            (f"HP:        {int(tower.hp)} / {int(tower.max_hp)}", C.UI_GREEN),
        ]
        if not defs_only or tower.damage > 0:
            stats.append((f"Damage:    {int(tower.damage)}", C.UI_RED))
        if tower.range > 0:
            stats.append((f"Range:     {int(tower.range)}px", C.UI_BLUE))
        if tower.fire_rate > 0:
            stats.append((f"Fire rate: {tower.fire_rate}/s", C.UI_TEXT))

        for line, color in stats:
            lbl = self._font_sm.render(line, True, color)
            s.blit(lbl, (px + pad, y))
            y += 16

        y += 4

        if defs_only:
            note = self._font_xs.render(
                "Defensive structure — not upgradeable", True, C.UI_DIM,
            )
            s.blit(note, (px + pad, y))
            self.upgrade_tower_rect = None
            return y + 20

        # ── Targeting priority — three small toggle buttons ───────────────
        prio_hdr = self._font_xs.render("Target priority:", True, C.UI_DIM)
        s.blit(prio_hdr, (px + pad, y))
        y += 14
        modes = ("CLOSEST", "WEAKEST", "STRONGEST")
        bw_total = self.PANEL_W - pad * 2
        gap_p    = 4
        each_w   = (bw_total - gap_p * (len(modes) - 1)) // len(modes)
        for i, mode in enumerate(modes):
            bx = px + pad + i * (each_w + gap_p)
            br = pygame.Rect(bx, y, each_w, 22)
            is_sel = (getattr(tower, "target_mode", "CLOSEST") == mode)
            bg = (60, 80, 130) if is_sel else (32, 36, 56)
            bd = (140, 180, 240) if is_sel else (70, 80, 110)
            pygame.draw.rect(s, bg, br, border_radius=4)
            pygame.draw.rect(s, bd, br, 2, border_radius=4)
            mlbl = self._font_xs.render(
                mode, True,
                (220, 235, 255) if is_sel else C.UI_DIM,
            )
            s.blit(mlbl, (br.centerx - mlbl.get_width() // 2,
                          br.centery - mlbl.get_height() // 2))
            self.priority_btn_rects[mode] = br
        y += 26

        # Upgrade button
        bw = self.PANEL_W - pad * 2
        bh = 32
        cost = tower.upgrade_cost
        can_afford = (gold >= cost)
        upg_rect = pygame.Rect(px + pad, y, bw, bh)
        bg = (90, 60, 30) if can_afford else (35, 28, 20)
        bd = (240, 180, 80) if can_afford else (80, 60, 40)
        pygame.draw.rect(s, bg, upg_rect, border_radius=5)
        pygame.draw.rect(s, bd, upg_rect, 2, border_radius=5)
        lbl = self._font_sm.render(
            f"UPGRADE DAMAGE  → Lv {tower.level + 1}  {cost}g",
            True, (255, 220, 140) if can_afford else C.UI_DIM,
        )
        s.blit(lbl, (upg_rect.centerx - lbl.get_width() // 2,
                      upg_rect.centery - lbl.get_height() // 2))
        self.upgrade_tower_rect = upg_rect
        y += bh + 4

        hint = self._font_xs.render(
            "Right-click the tower to sell (50%)", True, C.UI_DIM,
        )
        s.blit(hint, (px + pad, y))
        return y + 16

    def _draw_action_buttons(self, y, phase, fish, gold, day_timer=0.0,
                              inv_used=0, inv_size=C.INVENTORY_SIZE) -> int:
        """Draw phase-dependent action buttons: START WAVE, SELL FISH, BUY FOOD, INVENTORY."""
        s  = self.screen
        px = self.PANEL_X
        pad = self.PAD
        bw = self.PANEL_W - pad * 2
        bh = 36

        if phase == "DAY":
            # ── Day-prep countdown ───────────────────────────────────────────
            mins  = int(day_timer) // 60
            secs  = int(day_timer) % 60
            timer_str = f"Wave in  {mins:02d}:{secs:02d}"
            # Color shifts red as time runs low
            ratio = max(0.0, min(1.0, day_timer / max(1.0, C.DAY_DURATION)))
            timer_col = (
                (255, 220, 100) if ratio > 0.5 else
                (255, 170,  60) if ratio > 0.2 else
                (255,  90,  90)
            )
            timer_lbl = self._font_bold.render(timer_str, True, timer_col)
            s.blit(timer_lbl, (px + pad, y + 4))
            # Thin progress bar underneath
            prog_x = px + pad
            prog_w = bw
            prog_h = 4
            prog_y = y + 22
            pygame.draw.rect(s, (35, 35, 50), (prog_x, prog_y, prog_w, prog_h))
            pygame.draw.rect(s, timer_col,
                             (prog_x, prog_y, int(prog_w * ratio), prog_h))
            y += 32

            # Start Wave button
            can_start = True
            btn_color = (40, 100, 60) if can_start else (30, 40, 30)
            btn_rect  = pygame.Rect(px + pad, y + 4, bw, bh)
            pygame.draw.rect(s, btn_color, btn_rect, border_radius=6)
            pygame.draw.rect(s, (80, 200, 80), btn_rect, 2, border_radius=6)
            pulse = 0.6 + 0.4 * abs(math.sin(self._time * 2))
            lbl   = self._font_bold.render("START WAVE  [SPACE]", True,
                                            (int(80 * pulse + 175), 255, int(80 * pulse + 100)))
            s.blit(lbl, (btn_rect.centerx - lbl.get_width() // 2,
                         btn_rect.centery - lbl.get_height() // 2))
            self.start_wave_rect = btn_rect
            y += bh + 8

            # Selling fish has moved to the in-world shop building.
            # Drag fish from your bag onto the shop's SELL slot.
            self.sell_fish_rect = None

            # Inventory button — full-width row, hotkey "I"
            inv_rect = pygame.Rect(px + pad, y + 4, bw, bh)
            pygame.draw.rect(s, (50, 60, 100), inv_rect, border_radius=6)
            pygame.draw.rect(s, (140, 160, 230), inv_rect, 2, border_radius=6)
            inv_lbl = self._font_bold.render(
                f"OPEN BAG  {inv_used}/{inv_size}  [I]", True, (200, 220, 255),
            )
            s.blit(inv_lbl, (inv_rect.centerx - inv_lbl.get_width() // 2,
                              inv_rect.centery - inv_lbl.get_height() // 2))
            self.inventory_btn_rect = inv_rect
            self.buy_food_rect = None  # legacy slot kept for game.py guards
            y += bh + 8
        else:
            # Night phase — show wave progress placeholder
            lbl = self._font_med.render("  Enemies incoming!", True, (255, 100, 80))
            s.blit(lbl, (px + pad, y + 8))
            y += 36

        return y

    def _draw_castle_status(self, y, castle_hp, castle_max_hp, wave,
                              upgrade_lv=0, upgrade_cost=0, gold=0) -> int:
        """Draw castle HP bar, reinforcement tier label, and UPGRADE CASTLE button."""
        s  = self.screen
        px = self.PANEL_X
        pad = self.PAD

        hdr = self._font_med.render("Castle Status", True, C.UI_TEXT)
        s.blit(hdr, (px + pad, y + 6))
        if upgrade_lv > 0:
            tier = self._font_xs.render(
                f"Reinforced Lv {upgrade_lv}", True, (255, 200, 80),
            )
            s.blit(tier,
                   (px + self.PANEL_W - pad - tier.get_width(), y + 8))
        y += 26

        # HP bar (wide)
        ratio = max(0.0, castle_hp / max(1, castle_max_hp))
        bar_x = px + pad
        bar_w = self.PANEL_W - pad * 2
        bar_h = 16
        pygame.draw.rect(s, C.HP_BG, (bar_x, y, bar_w, bar_h), border_radius=4)
        bar_color = (
            C.HP_GREEN  if ratio > 0.6 else
            C.HP_YELLOW if ratio > 0.3 else
            C.HP_RED
        )
        pygame.draw.rect(s, bar_color,
                         (bar_x, y, int(bar_w * ratio), bar_h), border_radius=4)
        pygame.draw.rect(s, C.UI_BORDER, (bar_x, y, bar_w, bar_h), 1, border_radius=4)

        hp_lbl = self._font_xs.render(
            f"HP: {castle_hp} / {castle_max_hp}", True, C.UI_TEXT
        )
        s.blit(hp_lbl, (bar_x + bar_w // 2 - hp_lbl.get_width() // 2, y + 2))
        y += bar_h + 6

        # Upgrade castle button
        btn_h = 30
        upg_rect = pygame.Rect(bar_x, y, bar_w, btn_h)
        can_afford = (gold >= upgrade_cost)
        bg = (60, 50, 90) if can_afford else (30, 28, 40)
        bd = (160, 130, 230) if can_afford else (60, 55, 80)
        pygame.draw.rect(s, bg, upg_rect, border_radius=5)
        pygame.draw.rect(s, bd, upg_rect, 2, border_radius=5)
        lbl = self._font_sm.render(
            f"UPGRADE CASTLE  +{C.CASTLE_HP_UPGRADE_AMOUNT} HP  {upgrade_cost}g",
            True, (220, 200, 255) if can_afford else C.UI_DIM,
        )
        s.blit(lbl, (upg_rect.centerx - lbl.get_width() // 2,
                      upg_rect.centery - lbl.get_height() // 2))
        self.upgrade_castle_rect = upg_rect
        y += btn_h + 6

        max_wave = len(C.WAVE_CONFIGS)
        wave_lbl = self._font_sm.render(
            f"Wave: {wave} / {max_wave}", True, C.UI_DIM
        )
        s.blit(wave_lbl, (px + pad, y))
        return y + 20

    def _draw_help(self, y) -> None:
        s   = self.screen
        px  = self.PANEL_X
        pad = self.PAD

        hdr = self._font_sm.render("Controls:", True, C.UI_DIM)
        s.blit(hdr, (px + pad, y + 4))
        y += 20

        lines = [
            "WASD/Arrows : move hero",
            "1-9, 0 : select item type",
            "BUY button : confirm",
            "I : open / close inventory",
            "Drag from bag onto map",
            "  to place / feed pond",
            "R-click placed tower : sell",
            "Cast button : start fishing",
            "ESC : cancel drag / fishing",
            "SPACE : start wave",
        ]
        for line in lines:
            lbl = self._font_xs.render(line, True, (90, 90, 110))
            s.blit(lbl, (px + pad, y))
            y += 14

    def _draw_message(self, message: str) -> None:
        s  = self.screen
        px = self.PANEL_X
        lbl = self._font_bold.render(message, True, (255, 220, 60))
        bg  = pygame.Surface((lbl.get_width() + 20, lbl.get_height() + 10),
                              pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        mx = px + self.PANEL_W // 2 - lbl.get_width() // 2 - 10
        my = C.SCREEN_HEIGHT - 80
        s.blit(bg, (mx, my))
        s.blit(lbl, (mx + 10, my + 5))

    # ── Section divider ────────────────────────────────────────────────────

    def _draw_divider(self, y) -> int:
        pygame.draw.line(
            self.screen, C.UI_BORDER,
            (self.PANEL_X + 8, y + 3),
            (self.PANEL_X + self.PANEL_W - 8, y + 3),
        )
        return y + 8
