"""
src/inventory_overlay.py
========================
InventoryOverlay — grid view of the player's inventory.

Drawn ON TOP of the game world when the player toggles it (default key: I).
Press-down on a slot to start dragging the item; release the drag onto the
world to use it (drop fish food on the pond, drop a tower onto a grid cell).
The overlay fades to semi-transparent while a drag is active so the player
can see the world underneath.

The overlay stores click rects for each slot so game.py can route mouse
button events back to the right slot index.
"""

from __future__ import annotations
import pygame

import config as C


class InventoryOverlay:
    """Modal inventory window with 5×4 slot grid."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.visible: bool = False
        self.selected_slot: int | None = None

        self._font_title = pygame.font.SysFont("consolas", 22, bold=True)
        self._font_med   = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_sm    = pygame.font.SysFont("consolas", 12)
        self._font_xs    = pygame.font.SysFont("consolas", 11)
        self._font_count = pygame.font.SysFont("consolas", 13, bold=True)

        # Centred panel rect
        ow, oh = C.INVENTORY_OVERLAY_W, C.INVENTORY_OVERLAY_H
        self.rect = pygame.Rect(
            (C.SCREEN_WIDTH  - ow) // 2,
            (C.SCREEN_HEIGHT - oh) // 2,
            ow, oh,
        )

        # Click hit-boxes (rebuilt each draw for safety)
        self.slot_rects: list[pygame.Rect] = []
        self.close_btn_rect: pygame.Rect | None = None

    # ── Toggling ──────────────────────────────────────────────────────────

    def toggle(self) -> None:
        self.visible = not self.visible
        if not self.visible:
            self.selected_slot = None

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False
        self.selected_slot = None

    # ── Click routing ─────────────────────────────────────────────────────

    def hit_slot(self, mx: int, my: int) -> int | None:
        """Return slot index under (mx, my), or None."""
        for i, r in enumerate(self.slot_rects):
            if r.collidepoint(mx, my):
                return i
        return None

    def hit_close(self, mx: int, my: int) -> bool:
        return self.close_btn_rect is not None and self.close_btn_rect.collidepoint(mx, my)

    def consumes_click(self, mx: int, my: int) -> bool:
        """True while open AND the click is anywhere on the panel (modal block)."""
        return self.visible and self.rect.collidepoint(mx, my)

    # ── Drawing ───────────────────────────────────────────────────────────

    def draw(self, inventory, drag_active: bool = False) -> None:
        """Render the inventory grid.  Fades when `drag_active` so the player
        can see the world underneath while dragging an item out of a slot."""
        if not self.visible:
            return

        s = self.screen

        # Dim background — much subtler while dragging so the world is visible.
        veil_alpha = 60 if drag_active else 150
        veil = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, veil_alpha))
        s.blit(veil, (0, 0))

        # Panel — also fades while dragging
        if drag_active:
            panel_surf = pygame.Surface(
                (self.rect.w, self.rect.h), pygame.SRCALPHA,
            )
            pygame.draw.rect(panel_surf, (*C.UI_BG, 130),
                             panel_surf.get_rect(), border_radius=10)
            pygame.draw.rect(panel_surf, (*C.UI_BORDER, 200),
                             panel_surf.get_rect(), 3, border_radius=10)
            s.blit(panel_surf, self.rect.topleft)
        else:
            pygame.draw.rect(s, C.UI_BG,     self.rect, border_radius=10)
            pygame.draw.rect(s, C.UI_BORDER, self.rect, 3, border_radius=10)

        # Title
        title = self._font_title.render("INVENTORY", True, C.UI_GOLD)
        s.blit(title, (self.rect.x + 20, self.rect.y + 16))

        used = inventory.used_slots()
        sub = self._font_sm.render(
            f"{used} / {inventory.size}", True, C.UI_DIM,
        )
        s.blit(sub, (self.rect.x + 20, self.rect.y + 44))

        # Close button (X) in top-right
        cx = self.rect.right - 36
        cy = self.rect.y + 16
        close_rect = pygame.Rect(cx, cy, 24, 24)
        pygame.draw.rect(s, (90, 30, 30), close_rect, border_radius=4)
        pygame.draw.rect(s, (220, 80, 80), close_rect, 1, border_radius=4)
        x_lbl = self._font_med.render("X", True, (255, 220, 220))
        s.blit(x_lbl, (close_rect.centerx - x_lbl.get_width() // 2,
                       close_rect.centery - x_lbl.get_height() // 2))
        self.close_btn_rect = close_rect

        # Slot grid
        cols = C.INVENTORY_COLS
        slot = C.INVENTORY_SLOT_SIZE
        gap  = C.INVENTORY_SLOT_GAP
        total_w = cols * slot + (cols - 1) * gap
        start_x = self.rect.x + (self.rect.w - total_w) // 2
        start_y = self.rect.y + 70

        self.slot_rects = []
        for i in range(inventory.size):
            row = i // cols
            col = i %  cols
            sx = start_x + col * (slot + gap)
            sy = start_y + row * (slot + gap)
            r  = pygame.Rect(sx, sy, slot, slot)
            self.slot_rects.append(r)

            # Slot bg
            is_sel = (self.selected_slot == i)
            bg = (50, 50, 75) if is_sel else (30, 30, 45)
            pygame.draw.rect(s, bg, r, border_radius=6)
            border_col = C.UI_GOLD if is_sel else C.UI_BORDER
            pygame.draw.rect(s, border_col, r, 2, border_radius=6)

            # Item content
            item_slot = inventory.slots[i]
            if item_slot is not None:
                self._draw_item(s, r, item_slot["item"], item_slot["count"])

        # Selected-item info + "USE" button
        info_y = start_y + 4 * (slot + gap) + 12
        if self.selected_slot is not None and self.selected_slot < len(inventory.slots):
            sel = inventory.slots[self.selected_slot]
        else:
            sel = None

        if sel is not None:
            defn = C.ITEM_DEFS[sel["item"]]
            name_lbl = self._font_med.render(
                f"{defn['name']}  x{sel['count']}", True, C.UI_TEXT,
            )
            s.blit(name_lbl, (self.rect.x + 24, info_y))

            for i_line, line in enumerate(defn["description"].split("\n")):
                d_lbl = self._font_xs.render(line, True, C.UI_DIM)
                s.blit(d_lbl, (self.rect.x + 24, info_y + 22 + i_line * 14))
        else:
            hint = self._font_sm.render(
                "Drag a slot onto the world to use.  ESC / I to close.",
                True, C.UI_DIM,
            )
            s.blit(hint, (self.rect.x + 24, info_y + 4))

    # ── Helpers ───────────────────────────────────────────────────────────

    def _draw_item(self, s, rect: pygame.Rect, item_id: str, count: int) -> None:
        """Render the item icon inside a slot.

        - Tower / wall items use the actual sprite from `Assets`, scaled down
          to fit the slot.  Walls (vector style in-game) get their own
          drawn icon to match the world rendering.
        - Fish food / fish products use small vector motifs (no sprite for them).
        """
        from src.assets import Assets

        inner   = rect.inflate(-12, -12)
        slot_px = min(inner.w, inner.h)

        non_combat    = ("WALL", "FENCE", "SPIKE", "BARRICADE")
        plant_kind    = item_id in C.PLANT_DEFS
        supplier_kind = item_id in C.SUPPLIER_DEFS
        sprite_kind = (item_id not in ("FISH_FOOD", "FISH_COMMON", "FISH_RARE")
                       and item_id not in non_combat
                       and not plant_kind
                       and not supplier_kind)

        if plant_kind or supplier_kind:
            # Plant — matured (last) growth stage so the player can tell
            # species apart at a glance.
            # Supplier — same matured sprite, since a harvested supplier
            # IS visually the ripe crop the player just picked.
            sprite_id = (item_id if plant_kind
                         else C.SUPPLIER_TO_PLANT.get(item_id, ""))
            stages = Assets._plant_frames.get(sprite_id, [])
            if stages:
                sprite = stages[-1]
                sw, sh = sprite.get_size()
                scale = min(slot_px / max(1, sw), slot_px / max(1, sh), 1.4)
                tw = max(1, int(sw * scale))
                th = max(1, int(sh * scale))
                icon = pygame.transform.scale(sprite, (tw, th)) if (tw, th) != (sw, sh) else sprite
                s.blit(icon, (inner.centerx - tw // 2,
                              inner.centery - th // 2))
            else:
                pygame.draw.rect(s, (140, 200, 120), inner, border_radius=4)
        elif sprite_kind:
            # Combat tower → real sprite, scaled to fit
            sprite = Assets.tower(item_id, anim_t=0.0)
            if sprite is not None:
                sw, sh = sprite.get_size()
                scale = min(slot_px / sw, slot_px / sh, 1.5)
                tw = max(1, int(sw * scale))
                th = max(1, int(sh * scale))
                icon = pygame.transform.scale(sprite, (tw, th)) if (tw, th) != (sw, sh) else sprite
                s.blit(icon, (inner.centerx - tw // 2, inner.centery - th // 2))
            else:
                # Fallback colored block
                defn = C.ITEM_DEFS.get(item_id, {})
                pygame.draw.rect(s, defn.get("color", (180, 180, 200)),
                                 inner, border_radius=4)
        elif item_id in non_combat:
            # Wall / fence / spike / barricade — draw a compact vector icon
            cx, cy = inner.centerx, inner.centery
            self._draw_wall_icon(s, item_id, cx, cy)
        elif item_id == "FISH_FOOD":
            # Bag of pellets
            pygame.draw.circle(s, (250, 200, 80),
                               (inner.centerx, inner.centery), 12)
            pygame.draw.circle(s, (200, 150, 60),
                               (inner.centerx, inner.centery), 12, 2)
            for ox, oy in ((-4, -3), (4, -3), (0, 5)):
                pygame.draw.circle(s, (160, 110, 40),
                                   (inner.centerx + ox, inner.centery + oy), 3)
        elif item_id in ("FISH_COMMON", "FISH_RARE"):
            cx, cy   = inner.centerx, inner.centery
            body_col = (110, 200, 240) if item_id == "FISH_COMMON" else (255, 180, 220)
            pygame.draw.ellipse(s, body_col, (cx - 14, cy - 6, 22, 12))
            pygame.draw.polygon(s, body_col, [
                (cx + 8, cy), (cx + 16, cy - 6), (cx + 16, cy + 6),
            ])
            pygame.draw.circle(s, (20, 20, 30), (cx - 6, cy - 1), 2)

        # Count badge (only when stacked)
        if count > 1:
            cnt = self._font_count.render(str(count), True, (255, 255, 255))
            bx = rect.right - cnt.get_width() - 4
            by = rect.bottom - cnt.get_height() - 2
            pygame.draw.rect(s, (20, 20, 30),
                             (bx - 2, by - 1, cnt.get_width() + 4, cnt.get_height() + 2),
                             border_radius=3)
            s.blit(cnt, (bx, by))

    def _draw_wall_icon(self, s, item_id: str, cx: int, cy: int) -> None:
        """Compact vector icons for wall / fence / spike / barricade slots."""
        if item_id == "WALL":
            pygame.draw.rect(s, C.WALL_STONE, (cx - 14, cy - 12, 28, 24), border_radius=2)
            pygame.draw.line(s, C.WALL_DARK, (cx - 14, cy), (cx + 14, cy), 1)
            pygame.draw.line(s, C.WALL_DARK, (cx, cy - 12), (cx, cy + 12), 1)
        elif item_id == "FENCE":
            for off in (-10, -3, 4, 11):
                pygame.draw.polygon(s, C.FENCE_WOOD, [
                    (cx + off,     cy + 12),
                    (cx + off + 4, cy + 12),
                    (cx + off + 4, cy - 8),
                    (cx + off + 2, cy - 11),
                    (cx + off,     cy - 8),
                ])
            pygame.draw.line(s, C.FENCE_DARK, (cx - 12, cy - 1), (cx + 14, cy - 1), 2)
            pygame.draw.line(s, C.FENCE_DARK, (cx - 12, cy + 6), (cx + 14, cy + 6), 2)
        elif item_id == "SPIKE":
            pygame.draw.rect(s, C.SPIKE_BASE, (cx - 14, cy + 5, 28, 10), border_radius=1)
            for off in (-10, -3, 4, 11):
                pts = [(cx + off - 3, cy + 5), (cx + off + 3, cy + 5),
                       (cx + off,     cy - 12)]
                pygame.draw.polygon(s, C.SPIKE_TIP, pts)
        elif item_id == "BARRICADE":
            pygame.draw.rect(s, C.BARRICADE_BAND, (cx - 16, cy - 12, 32, 24), border_radius=2)
            pygame.draw.rect(s, C.BARRICADE_STEEL, (cx - 13, cy - 9, 26, 18))
            pygame.draw.line(s, C.BARRICADE_BAND, (cx - 13, cy), (cx + 13, cy), 2)
            for rx in (cx - 11, cx + 9):
                pygame.draw.circle(s, C.BARRICADE_RIVET, (rx, cy - 6), 2)
                pygame.draw.circle(s, C.BARRICADE_RIVET, (rx, cy + 6), 2)
