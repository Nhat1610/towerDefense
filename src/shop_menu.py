"""
src/shop_menu.py
================
ShopMenu — overlay that lets the player buy consumables and sell fish.

Opens together with the inventory overlay when the player clicks the
shop building (or runs into it within `SHOP_INTERACT_RANGE`).  It sits
to the LEFT of the inventory panel so both are visible at once.

Layout:
    ┌─────────── SHOP ─────────────┐
    │ BUY                           │
    │  ┌──┐ Fish Food   40g  [BUY] │
    │  └──┘                         │
    │  ...                          │
    │ ─────────────────────────────│
    │ SELL                          │
    │  drop fish here →  [Sell box]│
    │  Total: NN gold      [SELL]  │
    └───────────────────────────────┘

The SELL slot accepts drag-and-drop from the inventory.  Fish dropped on
it are tallied; clicking SELL converts the tally to gold.
"""

from __future__ import annotations
import pygame

import config as C


class ShopMenu:
    """Sliding shop window with BUY list + SELL drop-slot."""

    PANEL_W = 280
    # Tall enough to fit FISH_FOOD + 5 plants + BUY button + divider + SELL
    # section with drop slot and SELL button without overflow.
    PANEL_H = 600

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.visible: bool = False

        self._font_title = pygame.font.SysFont("consolas", 20, bold=True)
        self._font_med   = pygame.font.SysFont("consolas", 14, bold=True)
        self._font_sm    = pygame.font.SysFont("consolas", 12)
        self._font_xs    = pygame.font.SysFont("consolas", 11)

        # Centre vertically; sit to the LEFT of the inventory overlay so both
        # are visible side-by-side.
        inv_w = C.INVENTORY_OVERLAY_W
        gap   = 16
        total = self.PANEL_W + gap + inv_w
        left  = (C.SCREEN_WIDTH - total) // 2
        self.rect = pygame.Rect(
            left,
            (C.SCREEN_HEIGHT - self.PANEL_H) // 2,
            self.PANEL_W,
            self.PANEL_H,
        )

        # Selected BUY item (highlighted; BUY button operates on this)
        self.selected_buy: str | None = None
        if C.SHOP_BUYABLE_TYPES:
            self.selected_buy = C.SHOP_BUYABLE_TYPES[0]

        # Pending SELL stash — items dragged into the sell slot, kept until
        # the player clicks SELL or cancels (closes the menu).
        # {item_id: count}
        self.pending_sell: dict[str, int] = {}

        # Click hit-boxes (rebuilt every draw)
        self.buy_item_rects:  dict[str, pygame.Rect] = {}
        self.buy_btn_rect:    pygame.Rect | None = None
        self.sell_btn_rect:   pygame.Rect | None = None
        self.sell_slot_rect:  pygame.Rect | None = None
        self.close_btn_rect:  pygame.Rect | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        self.visible = True

    def close(self) -> dict[str, int]:
        """Close the menu, returning the still-pending SELL stash."""
        self.visible = False
        unsold = dict(self.pending_sell)
        self.pending_sell.clear()
        return unsold

    def is_visible(self) -> bool:
        return self.visible

    # ── Click routing ─────────────────────────────────────────────────────

    def hit_buy_item(self, mx: int, my: int) -> str | None:
        """Return the item_id under (mx, my), or None."""
        for item_id, r in self.buy_item_rects.items():
            if r.collidepoint(mx, my):
                return item_id
        return None

    def hit_buy(self, mx: int, my: int) -> bool:
        return self.buy_btn_rect is not None and self.buy_btn_rect.collidepoint(mx, my)

    def hit_sell(self, mx: int, my: int) -> bool:
        return self.sell_btn_rect is not None and self.sell_btn_rect.collidepoint(mx, my)

    def hit_sell_slot(self, mx: int, my: int) -> bool:
        return self.sell_slot_rect is not None and self.sell_slot_rect.collidepoint(mx, my)

    def hit_close(self, mx: int, my: int) -> bool:
        return self.close_btn_rect is not None and self.close_btn_rect.collidepoint(mx, my)

    def consumes_click(self, mx: int, my: int) -> bool:
        return self.visible and self.rect.collidepoint(mx, my)

    # ── Pending-sell helpers ──────────────────────────────────────────────

    def stash_for_sell(self, item_id: str, count: int = 1) -> None:
        self.pending_sell[item_id] = self.pending_sell.get(item_id, 0) + count

    def pending_total_value(self) -> int:
        total = 0
        for item_id, n in self.pending_sell.items():
            price = C.ITEM_DEFS.get(item_id, {}).get("sell_price", 0)
            total += n * price
        return total

    def take_pending(self) -> dict[str, int]:
        snapshot = dict(self.pending_sell)
        self.pending_sell.clear()
        return snapshot

    # ── Drawing ───────────────────────────────────────────────────────────

    def draw(self, gold: int) -> None:
        if not self.visible:
            return
        s = self.screen

        # Panel background
        pygame.draw.rect(s, C.UI_BG,     self.rect, border_radius=10)
        pygame.draw.rect(s, C.UI_BORDER, self.rect, 3, border_radius=10)

        # Title bar
        title = self._font_title.render("SHOP", True, C.UI_GOLD)
        s.blit(title, (self.rect.x + 18, self.rect.y + 14))

        # Close button (X)
        cb = pygame.Rect(self.rect.right - 36, self.rect.y + 14, 24, 24)
        pygame.draw.rect(s, (90, 30, 30), cb, border_radius=4)
        pygame.draw.rect(s, (220, 80, 80), cb, 1, border_radius=4)
        x_lbl = self._font_med.render("X", True, (255, 220, 220))
        s.blit(x_lbl, (cb.centerx - x_lbl.get_width() // 2,
                       cb.centery - x_lbl.get_height() // 2))
        self.close_btn_rect = cb

        # Gold readout under title
        gold_lbl = self._font_sm.render(f"Your gold: {gold}", True, C.UI_DIM)
        s.blit(gold_lbl, (self.rect.x + 18, self.rect.y + 42))

        # ── BUY section ──────────────────────────────────────────────────
        sec_y = self.rect.y + 70
        hdr = self._font_med.render("BUY", True, (255, 220, 140))
        s.blit(hdr, (self.rect.x + 18, sec_y))
        sec_y += 22

        self.buy_item_rects.clear()
        row_h = 44
        for item_id in C.SHOP_BUYABLE_TYPES:
            defn = C.ALL_DEFS.get(item_id) or C.ITEM_DEFS.get(item_id, {})
            row = pygame.Rect(self.rect.x + 16, sec_y,
                              self.PANEL_W - 32, row_h)
            is_sel = (item_id == self.selected_buy)
            bg = (50, 60, 90) if is_sel else (30, 32, 50)
            bd = C.UI_GOLD if is_sel else C.UI_BORDER
            pygame.draw.rect(s, bg, row, border_radius=5)
            pygame.draw.rect(s, bd, row, 2, border_radius=5)

            # Icon (small)
            icon_cx = row.x + 22
            icon_cy = row.centery
            self._draw_buy_icon(s, item_id, icon_cx, icon_cy)

            # Name + cost
            name = defn.get("name", item_id)
            cost = int(defn.get("cost", 0))
            n_lbl = self._font_med.render(name, True, C.UI_TEXT)
            c_lbl = self._font_sm.render(f"{cost}g", True, C.UI_GOLD)
            s.blit(n_lbl, (row.x + 44, row.y + 6))
            s.blit(c_lbl, (row.x + 44, row.y + 24))

            self.buy_item_rects[item_id] = row
            sec_y += row_h + 6

        # BUY button
        bb = pygame.Rect(self.rect.x + 16, sec_y + 2,
                         self.PANEL_W - 32, 32)
        sel_defn = (C.ALL_DEFS.get(self.selected_buy) or
                    C.ITEM_DEFS.get(self.selected_buy, {})) if self.selected_buy else {}
        cost = int(sel_defn.get("cost", 0))
        affordable = (gold >= cost) and self.selected_buy is not None
        bg = (40, 110, 60) if affordable else (40, 40, 55)
        bd = (130, 220, 140) if affordable else (80, 80, 100)
        pygame.draw.rect(s, bg, bb, border_radius=5)
        pygame.draw.rect(s, bd, bb, 2, border_radius=5)
        bb_lbl = self._font_med.render(
            f"BUY  {cost}g", True,
            (220, 255, 220) if affordable else C.UI_DIM,
        )
        s.blit(bb_lbl, (bb.centerx - bb_lbl.get_width() // 2,
                        bb.centery - bb_lbl.get_height() // 2))
        self.buy_btn_rect = bb
        sec_y = bb.bottom + 14

        # Divider
        pygame.draw.line(s, C.UI_BORDER,
                         (self.rect.x + 16, sec_y),
                         (self.rect.right - 16, sec_y), 1)
        sec_y += 10

        # ── SELL section ─────────────────────────────────────────────────
        hdr = self._font_med.render("SELL", True, (255, 220, 140))
        s.blit(hdr, (self.rect.x + 18, sec_y))
        sec_y += 22

        # Drop slot
        slot_h = 64
        ss = pygame.Rect(self.rect.x + 16, sec_y,
                         self.PANEL_W - 32, slot_h)
        pygame.draw.rect(s, (30, 40, 55), ss, border_radius=6)
        pygame.draw.rect(s, (90, 130, 180), ss, 2, border_radius=6)
        # Hint when empty, contents when full
        if not self.pending_sell:
            ph = self._font_sm.render("Drag fish here", True, C.UI_DIM)
            s.blit(ph, (ss.centerx - ph.get_width() // 2,
                        ss.centery - ph.get_height() // 2))
        else:
            text_lines = []
            for item_id, n in self.pending_sell.items():
                defn  = C.ITEM_DEFS.get(item_id, {})
                price = defn.get("sell_price", 0)
                text_lines.append(
                    f"{n} x {defn.get('name', item_id)}  ({n * price}g)"
                )
            for li, line in enumerate(text_lines):
                lbl = self._font_sm.render(line, True, (180, 230, 255))
                s.blit(lbl, (ss.x + 8, ss.y + 6 + li * 16))
        self.sell_slot_rect = ss
        sec_y = ss.bottom + 6

        # Total + SELL button
        total_val = self.pending_total_value()
        tot_lbl = self._font_med.render(
            f"Total: {total_val}g", True, C.UI_GOLD,
        )
        s.blit(tot_lbl, (self.rect.x + 18, sec_y))

        sb = pygame.Rect(self.rect.right - 16 - 100, sec_y - 4,
                         100, 28)
        can_sell = total_val > 0
        bg = (40, 80, 130) if can_sell else (35, 35, 50)
        bd = (110, 180, 240) if can_sell else (70, 70, 95)
        pygame.draw.rect(s, bg, sb, border_radius=5)
        pygame.draw.rect(s, bd, sb, 2, border_radius=5)
        sb_lbl = self._font_med.render(
            "SELL", True,
            (200, 230, 255) if can_sell else C.UI_DIM,
        )
        s.blit(sb_lbl, (sb.centerx - sb_lbl.get_width() // 2,
                        sb.centery - sb_lbl.get_height() // 2))
        self.sell_btn_rect = sb

    # ── Helpers ───────────────────────────────────────────────────────────

    def _draw_buy_icon(self, s, item_id: str, cx: int, cy: int) -> None:
        """Compact icon for the BUY row."""
        from src.assets import Assets

        if item_id == "FISH_FOOD":
            pygame.draw.circle(s, (250, 200, 80), (cx, cy), 10)
            pygame.draw.circle(s, (200, 150, 60), (cx, cy), 10, 2)
            for ox, oy in ((-3, -2), (3, -2), (0, 4)):
                pygame.draw.circle(s, (160, 110, 40), (cx + ox, cy + oy), 2)
            return

        # Plants and suppliers — use the dedicated sprite so the player can
        # recognise what they're buying or selling.
        # Plants:    matured (last) growth stage from Farm/Plants/.
        # Suppliers: harvested-product icon from Farm/Supplier/, with a
        #            fallback to the matured plant sprite if the supplier
        #            asset failed to load.
        if item_id in C.PLANT_DEFS or item_id in C.SUPPLIER_DEFS:
            sprite = None
            if item_id in C.SUPPLIER_DEFS:
                sprite = Assets._supplier_sprite.get(item_id)
                if sprite is None:
                    stages = Assets._plant_frames.get(
                        C.SUPPLIER_TO_PLANT.get(item_id, ""), [])
                    sprite = stages[-1] if stages else None
            else:
                stages = Assets._plant_frames.get(item_id, [])
                sprite = stages[-1] if stages else None

            if sprite is not None:
                sw, sh = sprite.get_size()
                # Scale down to fit a ~28×28 icon slot, preserving aspect
                max_dim = 28
                scale = min(max_dim / max(1, sw), max_dim / max(1, sh), 1.0)
                tw = max(1, int(sw * scale))
                th = max(1, int(sh * scale))
                icon = (pygame.transform.scale(sprite, (tw, th))
                        if (tw, th) != (sw, sh) else sprite)
                s.blit(icon, (cx - tw // 2, cy - th // 2))
                return

        # Generic fallback
        defn  = C.ITEM_DEFS.get(item_id, {})
        color = defn.get("color", (180, 180, 200))
        pygame.draw.rect(s, color, (cx - 10, cy - 10, 20, 20),
                         border_radius=3)
        pygame.draw.rect(s, (40, 40, 55),
                         (cx - 10, cy - 10, 20, 20), 1, border_radius=3)
