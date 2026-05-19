"""
src/game.py
===========
Game — main game loop, state management, and event handling.
"""

from __future__ import annotations
import math
import random
import pygame

import config as C
from src.entities import (
    Castle, Enemy, Tower, Projectile, FishPond, Shop, Hero, Boss,
    create_tower,
)
from src.algorithms import EntityLinkedList
from src.renderer import MapRenderer
from src.hud import HUD
from src.savegame import SaveManager, state_to_dict
from src.menu import GameOverScreen
from src.inventory import Inventory
from src.inventory_overlay import InventoryOverlay
from src.shop_menu import ShopMenu
from src.hero_upgrade_menu import HeroUpgradeMenu
from src.fishing import FishingMinigame
from src.farm import FarmState
from src.settings import Settings
from src.settings_overlay import SettingsOverlay
from src.audio import music
import random


class GameState:
    """All mutable game data in one place."""

    def __init__(self) -> None:
        self.gold:       int   = C.STARTING_GOLD
        self.wave:       int   = 1
        self.phase:      str   = "DAY"   # "DAY" | "NIGHT"
        self.paused:     bool  = False

        self.castle      = Castle()
        self.pond        = FishPond()
        self.shop        = Shop()

        self.hero        = Hero()

        # Player bag — holds purchases (fish food) and caught fish
        self.inventory   = Inventory()

        # Farm scene — plants placed in the farm map.  Time ticks while the
        # hero is on either the main map or the farm map (real-time growth).
        self.farm        = FarmState()
        self.current_map: str = "main"   # "main" | "farm"

        self.towers:      list[Tower]      = []
        # Enemies & projectiles use EntityLinkedList (doubly-linked list)
        # for O(1) append / removal — see src/algorithms/linked_list.py
        self.enemies:     EntityLinkedList  = EntityLinkedList()
        self.projectiles: EntityLinkedList  = EntityLinkedList()

        # Grid: grid[row][col] → "EMPTY" | "PATH" | "TOWER" | "BUILDING"
        self.grid: list[list[str]] = self._build_grid()

        # Night-phase spawn queue: list of (enemy_type, spawn_time)
        self._spawn_queue: list[tuple[str, float]] = []
        self._night_timer: float = 0.0

        # Day-phase prep timer — counts DOWN; wave auto-starts at 0
        self.day_timer: float = C.DAY_DURATION

        # Cached A* path (waypoints in pixel coords)
        # Until the student implements AStarPathfinder, we use C.PATH_WAYPOINTS
        self._enemy_path: list[tuple[float, float]] = list(C.PATH_WAYPOINTS)

        # Wave-snapshot ring buffer used by SaveManager for the rewind feature
        self.snapshots: list[dict] = []

        # Visual effects spawned by ranged bosses (Evil3 explosions, etc.)
        # Each entry: {"x": px, "y": py, "t": elapsed_sec, "kind": "explode"}
        self.boss_vfx: list[dict] = []

    # ── Grid setup ────────────────────────────────────────────────────────

    def _build_grid(self) -> list[list[str]]:
        grid = [["EMPTY"] * C.GRID_COLS for _ in range(C.GRID_ROWS)]

        # Mark cells that overlap the path
        path_cells = self._cells_on_path()
        for col, row in path_cells:
            if 0 <= row < C.GRID_ROWS and 0 <= col < C.GRID_COLS:
                grid[row][col] = "PATH"

        # Mark spawn zone columns LAST so they override any path overlap —
        # the leftmost two columns are reserved for enemy entry and must not
        # accept tower placement.
        for row in range(C.GRID_ROWS):
            for col in range(2):
                grid[row][col] = "BUILDING"

        # Mark castle, pond, shop footprints
        self._mark_building(grid, C.CASTLE_CX, C.CASTLE_CY, 100, 120)
        px, py, pw, ph = C.POND_RECT
        self._mark_rect(grid, px, py, pw, ph)
        sx, sy, sw, sh = C.SHOP_RECT
        self._mark_rect(grid, sx, sy, sw, sh)

        return grid

    def _cells_on_path(self) -> list[tuple[int, int]]:
        """Return grid cells that are close to any path variant."""
        cells = set()
        hw = C.PATH_WIDTH // 2 + C.CELL_SIZE // 2
        for variant in C.PATH_VARIANTS:
            for i in range(len(variant) - 1):
                x0, y0 = variant[i]
                x1, y1 = variant[i + 1]
                seg_len = math.hypot(x1 - x0, y1 - y0)
                steps = max(1, int(seg_len / 8))
                for s in range(steps + 1):
                    t = s / steps
                    mx = x0 + (x1 - x0) * t
                    my = y0 + (y1 - y0) * t
                    for dc in range(-1, 2):
                        for dr in range(-1, 2):
                            col = int(mx / C.CELL_SIZE) + dc
                            row = int(my / C.CELL_SIZE) + dr
                            if 0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS:
                                cx = col * C.CELL_SIZE + C.CELL_SIZE // 2
                                cy = row * C.CELL_SIZE + C.CELL_SIZE // 2
                                if self._dist_to_segment(cx, cy, x0, y0, x1, y1) < hw:
                                    cells.add((col, row))
        return list(cells)

    @staticmethod
    def _dist_to_segment(px, py, ax, ay, bx, by) -> float:
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def _mark_building(self, grid, cx, cy, w, h):
        self._mark_rect(grid, cx - w // 2, cy - h // 2, w, h)

    def _mark_rect(self, grid, x, y, w, h):
        c0 = max(0, int(x / C.CELL_SIZE) - 1)
        c1 = min(C.GRID_COLS - 1, int((x + w) / C.CELL_SIZE) + 1)
        r0 = max(0, int(y / C.CELL_SIZE) - 1)
        r1 = min(C.GRID_ROWS - 1, int((y + h) / C.CELL_SIZE) + 1)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = "BUILDING"


class Game:
    """Main game object.  Call game.run() to start the loop."""

    def __init__(self, screen: pygame.Surface,
                 load_state: dict | None = None,
                 settings: Settings | None = None) -> None:
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self.settings = settings if settings is not None else Settings.load()

        self.state    = GameState()
        self.renderer = MapRenderer(screen)
        self.hud      = HUD(screen)
        self.inv_overlay = InventoryOverlay(screen)
        self.shop_menu   = ShopMenu(screen)
        self.hero_upgrade_menu = HeroUpgradeMenu(screen)
        self.fishing    = FishingMinigame()
        self.settings_overlay = SettingsOverlay(screen, self.settings)

        # Click rects for the buttons drawn inside the pause overlay.
        # Computed once because the overlay layout is screen-centered.
        self._pause_settings_rect: pygame.Rect = pygame.Rect(
            C.SCREEN_WIDTH // 2 - 120,
            C.SCREEN_HEIGHT // 2 + 80,
            240, 44,
        )
        self._pause_save_quit_rect: pygame.Rect = pygame.Rect(
            C.SCREEN_WIDTH // 2 - 120,
            C.SCREEN_HEIGHT // 2 + 136,
            240, 44,
        )

        self.selected_type: str = "BALLISTA"   # last-bought item — UI highlight only
        self.selected_tower: Tower | None = None
        self.hovered_cell: tuple[int, int] | None = None
        self.message:  str   = ""
        self.msg_timer: float = 0.0

        # Drag-and-drop state — set when the player presses-down on an
        # inventory slot, cleared on release / ESC / right-click.
        # {"item_id": str, "source_slot": int} | None
        self.drag_state: dict | None = None

        self.running   = True

        # Was this session resumed from a save?  Tracks whether to write
        # the snapshot ring buffer back to disk on the next wave end.
        self._resumed: bool = load_state is not None
        if load_state is not None:
            self._restore_state(load_state)

    # ══════════════════════════════════════════════════════════════════════
    # Main loop
    # ══════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0

            self._handle_events()

            if not self.state.paused:
                self._update(dt)

            # Music keeps playing while paused — drive phase + crossfade
            # outside the pause gate so the crossfade animation doesn't
            # desync from the actual audio output.
            music.set_phase(self.state.phase)
            music.update(dt)

            self._draw()
            pygame.display.flip()

    # ══════════════════════════════════════════════════════════════════════
    # Events
    # ══════════════════════════════════════════════════════════════════════

    def _handle_events(self) -> None:
        state = self.state
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            # Settings overlay (when visible) takes input priority.
            if self.settings_overlay.visible:
                self.settings_overlay.handle_event(event)
                continue

            # When paused, intercept clicks on the SETTINGS and SAVE-AND-QUIT
            # pause buttons.  Everything else falls through to normal
            # handling so ESC can still un-pause via _handle_key.
            if (state.paused
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1):
                if self._pause_settings_rect.collidepoint(event.pos):
                    self.settings_overlay.open()
                    continue
                if self._pause_save_quit_rect.collidepoint(event.pos):
                    self._save_and_quit_to_menu()
                    continue

            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1:
                    self._handle_left_click(mx, my)
                elif event.button == 3:
                    if self.drag_state is not None:
                        self._cancel_drag()
                    else:
                        self._handle_right_click(mx, my)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.drag_state is not None:
                    self._resolve_drag(*event.pos)
                elif event.button == 3 and self.state.hero.attack2_charging:
                    # Hero released right-click → unleash Attack2 toward cursor
                    self._release_hero_charge(*event.pos)

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_e:
                    self.state.hero.end_block()

            elif event.type == pygame.MOUSEWHEEL:
                # Scroll the HUD item list when wheel happens over the panel
                mx, my = pygame.mouse.get_pos()
                clip = self.hud.menu_clip_rect
                if (mx >= C.GAME_WIDTH or
                    (clip is not None and clip.collidepoint(mx, my))):
                    self.hud.handle_scroll(event.y)

            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if mx < C.GAME_WIDTH:
                    col = mx // C.CELL_SIZE
                    row = my // C.CELL_SIZE
                    self.hovered_cell = (col, row)
                else:
                    self.hovered_cell = None

    def _handle_key(self, key: int) -> None:
        s = self.state
        # 1..9 select an item type in the HUD ITEMS section.  Fish food is
        # bought from the in-world Shop building, not via hotkey.
        digit_keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                      pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9]
        if key in digit_keys:
            idx = digit_keys.index(key)
            if idx < len(C.HUD_BUYABLE_TYPES):
                self.selected_type = C.HUD_BUYABLE_TYPES[idx]
                self._scroll_to_selected()
            return

        if key == pygame.K_m:
            self.hud.toggle_menu()
        elif key == pygame.K_i:
            # I-key cancels any drag, then any fishing, then toggles inventory.
            if self.drag_state is not None:
                self._cancel_drag()
                return
            if self.fishing.is_running():
                self.fishing.cancel()
            if self.shop_menu.visible:
                self._close_shop_and_bag()
            else:
                self.inv_overlay.toggle()
        elif key == pygame.K_SPACE:
            if s.phase == "DAY":
                self._start_wave()
        elif key == pygame.K_ESCAPE:
            # ESC priority: drag → fishing → hero menu → shop+bag → bag → pause
            if self.drag_state is not None:
                self._cancel_drag()
            elif self.fishing.is_running():
                self.fishing.cancel()
                self._show_message("Stopped fishing.")
            elif self.hero_upgrade_menu.visible:
                self.hero_upgrade_menu.close()
            elif self.shop_menu.visible:
                self._close_shop_and_bag()
            elif self.inv_overlay.visible:
                self.inv_overlay.close()
            else:
                s.paused = not s.paused
        elif key == pygame.K_q:
            self.running = False
        elif key == pygame.K_e:
            # Raise the guard.  Hero.begin_block() handles the cd/charge gates.
            if s.hero.begin_block():
                self._show_message("Guard up")
        elif key == pygame.K_r:
            if not s.hero.alive:
                s.hero.hp    = s.hero.max_hp
                s.hero.alive = True
                s.hero.x     = C.HERO_START_X
                s.hero.y     = C.HERO_START_Y
                self._show_message("Hero revived!")

    def _scroll_to_selected(self) -> None:
        """Adjust HUD scroll_offset so the selected item is in view."""
        if self.selected_type not in C.ALL_TYPES:
            return
        idx = C.ALL_TYPES.index(self.selected_type)
        items_per_row = self.hud._items_per_row
        visible_rows  = self.hud._visible_rows
        row = idx // items_per_row
        if row < self.hud.scroll_offset:
            self.hud.scroll_offset = row
        elif row >= self.hud.scroll_offset + visible_rows:
            self.hud.scroll_offset = row - visible_rows + 1

    def _handle_left_click(self, mx: int, my: int) -> None:
        s = self.state

        # ── Hero upgrade menu (modal) ────────────────────────────────────
        if self.hero_upgrade_menu.visible:
            if self.hero_upgrade_menu.hit_close(mx, my):
                self.hero_upgrade_menu.close()
                return
            kind = self.hero_upgrade_menu.hit_buy(mx, my)
            if kind is not None:
                self._upgrade_hero(kind)
                return
            # Modal: clicks inside the panel are absorbed
            if self.hero_upgrade_menu.consumes_click(mx, my):
                return
            # Click outside the panel: close it
            self.hero_upgrade_menu.close()
            return

        # ── Shop menu open: route clicks to BUY / SELL controls first ────
        if self.shop_menu.visible and self.shop_menu.consumes_click(mx, my):
            if self.shop_menu.hit_close(mx, my):
                self._close_shop_and_bag()
                return
            if self.shop_menu.hit_buy(mx, my):
                if self.shop_menu.selected_buy is not None:
                    self._buy_shop_item(self.shop_menu.selected_buy)
                return
            if self.shop_menu.hit_sell(mx, my):
                self._confirm_shop_sell()
                return
            picked = self.shop_menu.hit_buy_item(mx, my)
            if picked is not None:
                self.shop_menu.selected_buy = picked
            return  # shop menu is modal over its own panel

        # ── Inventory overlay open: clicking a slot starts a drag ─────────
        if self.inv_overlay.visible:
            if self.inv_overlay.hit_close(mx, my):
                if self.shop_menu.visible:
                    self._close_shop_and_bag()
                else:
                    self.inv_overlay.close()
                return
            slot = self.inv_overlay.hit_slot(mx, my)
            if slot is not None:
                slot_data = s.inventory.slots[slot]
                if slot_data is not None:
                    self.drag_state = {
                        "item_id":     slot_data["item"],
                        "source_slot": slot,
                    }
                    self.inv_overlay.selected_slot = slot
            # Whether we hit a slot or not, swallow the click; the overlay is modal.
            return

        # ── Fishing minigame: clicks during ACTIVE state are timing inputs ─
        if self.fishing.is_running():
            if self.fishing.state == FishingMinigame.ACTIVE:
                self.fishing.click()
            return

        # HUD panel
        if mx >= C.GAME_WIDTH:
            self._handle_ui_click(mx, my)
            return

        # World-space "Cast" fishing button (visible when hero in range)
        if self._point_in_rect(mx, my, C.FISH_BUTTON_RECT) and self._hero_near_pond():
            self._start_fishing()
            return

        # Shop building — open the in-world Buy/Sell menu (hero must be near)
        if s.shop.contains(mx, my) and s.phase == "DAY":
            dist = math.hypot(s.hero.x - s.shop.cx, s.hero.y - s.shop.cy)
            if dist > C.SHOP_INTERACT_RANGE:
                self._show_message("Move hero near the shop!")
                return
            self._open_shop_and_bag()
            return

        # Click on an existing tower → select for upgrade panel
        col = mx // C.CELL_SIZE
        row = my // C.CELL_SIZE

        # On the farm map, clicking a ripe plant harvests it.
        if s.current_map == "farm":
            if self._try_harvest_at(col, row):
                return

        for tower in s.towers:
            if tower.col == col and tower.row == row:
                self.selected_tower = tower
                self._show_message(f"Selected {tower.name} (Lv {tower.level})")
                return

        # Empty world click — placement now requires drag-from-inventory.
        self.selected_tower = None

        # Hero Attack1 — left-click swings at the closest enemy in range.
        # Faces the cursor regardless of whether anything was hit, so an
        # empty swing still feels deliberate.
        if (s.hero.alive
                and s.current_map == "main"
                and not s.paused):
            s.hero.facing_angle = math.atan2(my - s.hero.y, mx - s.hero.x)
            if s.hero.try_attack(s.enemies):
                self._mark_hero_attack_anim()

    @staticmethod
    def _point_in_rect(mx: int, my: int, rect: tuple) -> bool:
        rx, ry, rw, rh = rect
        return rx <= mx <= rx + rw and ry <= my <= ry + rh

    def _hero_near_pond(self) -> bool:
        s = self.state
        return math.hypot(s.hero.x - s.pond.cx, s.hero.y - s.pond.cy) <= C.POND_INTERACT_RANGE

    def _handle_right_click(self, mx: int, my: int) -> None:
        s = self.state

        # ── Inventory overlay open: right-click on a slot sells the item ──
        # Two-step sell flow: recall a tower from the map first (right-click
        # on map below), then right-click it again in the bag to actually
        # cash it out for 50% of its base cost.
        if self.inv_overlay.visible:
            slot = self.inv_overlay.hit_slot(mx, my)
            if slot is not None:
                slot_data = s.inventory.slots[slot]
                if slot_data is not None:
                    item_id = slot_data["item"]
                    defn = C.ALL_DEFS.get(item_id, {})
                    cost = int(defn.get("cost", 0))
                    if cost > 0:
                        refund = cost // 2
                        if s.inventory.use_slot(slot) is not None:
                            s.gold += refund
                            self._show_message(
                                f"{defn.get('name', item_id)} sold (+{refund}g)"
                            )
                            return
                    self._show_message("Cannot sell this item here.")
            # Modal: swallow the click whether or not it hit a slot.
            return

        if mx >= C.GAME_WIDTH:
            return

        # ── Right-click on a placed tower: recall to bag (no gold) ──
        col = mx // C.CELL_SIZE
        row = my // C.CELL_SIZE
        for tower in list(s.towers):
            if tower.col == col and tower.row == row:
                if not s.inventory.has_room_for(tower.tower_type):
                    self._show_message("Inventory full — cannot recall!")
                    return
                s.inventory.add(tower.tower_type, 1)
                s.towers.remove(tower)
                s.grid[row][col] = "EMPTY"
                if self.selected_tower is tower:
                    self.selected_tower = None
                self._show_message(
                    f"{tower.name} returned to bag (right-click in bag to sell)"
                )
                return

        # No tower hit → begin charging Attack2.  The release (mouse-up)
        # handler unleashes the actual stun + knockback.
        if (s.hero.alive
                and s.current_map == "main"
                and s.hero.attack2_cd <= 0
                and not s.paused):
            if s.hero.begin_attack2_charge():
                self._show_message("Charging strike — release to unleash")

    def _handle_ui_click(self, mx: int, my: int) -> None:
        hud = self.hud
        s   = self.state

        # Menu toggle (collapse/expand the item list)
        if hud.menu_toggle_rect and hud.menu_toggle_rect.collidepoint(mx, my):
            hud.toggle_menu()
            return

        # Scroll arrows
        if hud.scroll_up_rect and hud.scroll_up_rect.collidepoint(mx, my):
            hud.handle_scroll(1)   # one row up
            return
        if hud.scroll_down_rect and hud.scroll_down_rect.collidepoint(mx, my):
            hud.handle_scroll(-1)  # one row down
            return

        # Item / tower buttons → select only.  Confirm purchase via BUY.
        for ttype, rect in hud.tower_btn_rects.items():
            if rect.collidepoint(mx, my):
                self.selected_type = ttype
                self.selected_tower = None  # show buy panel, not upgrade panel
                return

        # BUY button — confirm purchase of the currently selected item type
        if hud.buy_btn_rect and hud.buy_btn_rect.collidepoint(mx, my):
            self._buy_item(self.selected_type)
            return

        # Start wave
        if hud.start_wave_rect and hud.start_wave_rect.collidepoint(mx, my):
            if s.phase == "DAY":
                self._start_wave()
            return

        # Sell fish — hero must be near the shop
        if hud.sell_fish_rect and hud.sell_fish_rect.collidepoint(mx, my):
            dist = math.hypot(s.hero.x - s.shop.cx, s.hero.y - s.shop.cy)
            if dist > C.SHOP_INTERACT_RANGE:
                self._show_message("Move hero near the shop to sell!")
                return
            if s.phase == "DAY":
                self._sell_all_fish()
            return

        # Open inventory overlay
        if hud.inventory_btn_rect and hud.inventory_btn_rect.collidepoint(mx, my):
            self.inv_overlay.toggle()
            return

        # Click on the Hero status row → open the hero upgrade menu
        hr = getattr(hud, "hero_status_rect", None)
        if hr is not None and hr.collidepoint(mx, my):
            self.hero_upgrade_menu.open()
            return

        # Castle HP upgrade
        if hud.upgrade_castle_rect and hud.upgrade_castle_rect.collidepoint(mx, my):
            self._upgrade_castle()
            return

        # Selected tower's damage upgrade
        if hud.upgrade_tower_rect and hud.upgrade_tower_rect.collidepoint(mx, my):
            self._upgrade_selected_tower()
            return

        # Selected tower's targeting-priority buttons
        if self.selected_tower is not None and hud.priority_btn_rects:
            for mode, rect in hud.priority_btn_rects.items():
                if rect.collidepoint(mx, my):
                    self.selected_tower.target_mode = mode
                    self._show_message(f"{self.selected_tower.name} → {mode}")
                    return

    def _recompute_path(self) -> None:
        """
        Recompute the enemy path using AStarPathfinder.
        Until A* is implemented, we keep using C.PATH_WAYPOINTS.

        To integrate your A* implementation, replace the body with:
        """
        from src.algorithms import AStarPathfinder
        pf    = AStarPathfinder(self.state.grid)
        start = AStarPathfinder.pixel_to_cell(*C.PATH_WAYPOINTS[0])
        goal  = AStarPathfinder.pixel_to_cell(C.CASTLE_CX, C.CASTLE_CY)
        cells = pf.find_path(start, goal)
        if cells:
            self.state._enemy_path = [
                AStarPathfinder.cell_to_pixel(c, r) for c, r in cells
            ]
  
        # Fallback: use hardcoded waypoints until A* is ready
        #self.state._enemy_path = list(C.PATH_WAYPOINTS)

    # ── Upgrade & shop actions ────────────────────────────────────────────

    def _buy_item(self, item_type: str) -> None:
        """Spend gold and add the item to inventory.

        Used both by HUD button clicks and number-key hotkeys.  Towers,
        defenses, and shop consumables (fish food) all flow through here.
        """
        s = self.state
        defn = C.ALL_DEFS.get(item_type)
        if defn is None:
            return
        cost = int(defn.get("cost", 0))
        if s.phase != "DAY":
            self._show_message("Buy during the day phase!")
            return
        if s.gold < cost:
            self._show_message(f"Need {cost}g for {defn['name']}!")
            return
        if not s.inventory.has_room_for(item_type):
            self._show_message("Inventory is full!")
            return
        s.gold -= cost
        s.inventory.add(item_type, 1)
        self._show_message(f"+1 {defn['name']} (-{cost}g)  [open bag: I]")

    # ── Drag-and-drop ─────────────────────────────────────────────────────

    def _cancel_drag(self) -> None:
        """Drop the in-progress drag without consuming the item."""
        self.drag_state = None

    def _resolve_drag(self, mx: int, my: int) -> None:
        """Resolve a drag-and-drop release at (mx, my)."""
        if self.drag_state is None:
            return
        item_id = self.drag_state["item_id"]
        src     = self.drag_state["source_slot"]
        s       = self.state

        defn = C.ITEM_DEFS.get(item_id, {})
        target_kind = defn.get("drag_target")

        # Drop onto the shop's SELL slot — works only for sellable items.
        # Suppliers and fish (COMMON / RARE) bulk-transfer the WHOLE stack
        # from the dragged slot in one drop; other sellable items still
        # move one at a time.
        if self.shop_menu.visible and self.shop_menu.hit_sell_slot(mx, my):
            sell_price = C.ITEM_DEFS.get(item_id, {}).get("sell_price", 0)
            slot_data = (s.inventory.slots[src]
                         if 0 <= src < s.inventory.size else None)
            if (sell_price <= 0 or slot_data is None
                    or slot_data["item"] != item_id):
                self._show_message("Not sellable here.")
                self._cancel_drag()
                return

            bulk = (item_id in C.SUPPLIER_DEFS
                    or item_id in ("FISH_COMMON", "FISH_RARE"))
            qty = int(slot_data["count"]) if bulk else 1

            if bulk:
                # Empty the whole slot in one go — avoids N calls to use_slot
                s.inventory.slots[src] = None
            else:
                s.inventory.use_slot(src)

            self.shop_menu.stash_for_sell(item_id, qty)
            name = C.ITEM_DEFS[item_id]["name"]
            self._show_message(f"Queued {qty} {name} for sale")
            self._cancel_drag()
            return

        # Must release on the world (left half), not on HUD or overlay panel.
        on_world = mx < C.GAME_WIDTH
        if not on_world:
            self._cancel_drag()
            return

        if target_kind == "POND" and item_id == "FISH_FOOD":
            # Drop near the pond → feed
            d = math.hypot(mx - s.pond.cx, my - s.pond.cy)
            if d <= C.POND_INTERACT_RANGE:
                if s.inventory.use_slot(src) is not None:
                    s.pond.feed()
                    self._show_message(
                        f"Fed pond — rate {int(s.pond.current_rate * 100)}%"
                    )
                self._cancel_drag()
                return
            # Released too far from pond → cancel silently
            self._cancel_drag()
            return

        if target_kind == "GRID":
            # Place tower / defense at grid cell under the cursor —
            # only on the main map (farm has no tower placement)
            if s.current_map != "main":
                self._show_message("Towers only place on the main map!")
                self._cancel_drag()
                return
            col = mx // C.CELL_SIZE
            row = my // C.CELL_SIZE
            self._try_place_from_inventory(col, row, item_id, src)
            self._cancel_drag()
            return

        if target_kind == "FARM_PLOT":
            # Drop a plant onto a farm plot
            if s.current_map != "farm":
                self._show_message("Plant inside the farm map!")
                self._cancel_drag()
                return
            col = mx // C.CELL_SIZE
            row = my // C.CELL_SIZE
            self._try_plant_from_inventory(col, row, item_id, src)
            self._cancel_drag()
            return

        # No valid drop target for this item type
        self._cancel_drag()

    def _try_place_from_inventory(
        self, col: int, row: int, ttype: str, src_slot: int,
    ) -> bool:
        """Place a tower/defense from inventory slot onto the grid."""
        s = self.state
        '''if s.phase != "DAY":
            self._show_message("Place during the day phase!")
            return False'''
        if not (0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS):
            self._show_message("Out of bounds!")
            return False
        if s.grid[row][col] not in ("EMPTY", "PATH"):
            self._show_message("Cannot place here!")
            return False
        # Verify the slot still holds the expected item before consuming
        slot_data = s.inventory.slots[src_slot]
        if slot_data is None or slot_data["item"] != ttype:
            return False
        s.inventory.use_slot(src_slot)
        tower = create_tower(col, row, ttype)
        s.towers.append(tower)
        s.grid[row][col] = "TOWER"
        self._show_message(f"{tower.name} placed!")
        return True

    # ── Fishing flow ──────────────────────────────────────────────────────

    def _start_fishing(self) -> None:
        """Trigger the fishing roll + minigame from the world Cast button."""
        s = self.state
        if s.phase != "DAY":
            self._show_message("Fish during the day phase!")
            return
        if self.fishing.is_running():
            return
        if not s.inventory.has_room_for("FISH_COMMON") and \
           not s.inventory.has_room_for("FISH_RARE"):
            self._show_message("Inventory is full!")
            return
        self.fishing.start(s.pond.current_rate)

    def _resolve_fishing_result(self) -> None:
        """If the minigame just ended, push the result into the world."""
        result = self.fishing.consume_result()
        if result == "success":
            s = self.state
            is_rare = random.random() < C.FISH_RARE_CHANCE
            item_id = "FISH_RARE" if is_rare else "FISH_COMMON"
            if s.inventory.add(item_id, 1):
                label = C.ITEM_DEFS[item_id]["name"]
                self._show_message(f"Caught a {label}!")
            else:
                self._show_message("Inventory full — fish slipped away!")
        elif result == "failure":
            self._show_message("The fish escaped!")

    # ── Map portal & farm flow ────────────────────────────────────────────

    def _check_map_portal(self) -> None:
        """If the hero stepped into the active map's portal, switch maps."""
        s = self.state
        hx, hy = s.hero.x, s.hero.y
        if s.current_map == "main":
            px, py, pw, ph = C.FARM_PORTAL_RECT_MAIN
            if px <= hx <= px + pw and py <= hy <= py + ph:
                s.current_map = "farm"
                # Drop the hero just inside the farm portal so they don't
                # immediately re-trigger the entry rect.
                fx, fy, fw, fh = C.FARM_PORTAL_RECT_FARM
                s.hero.x = fx + fw + 24
                s.hero.y = fy + fh // 2
                self._show_message("Entered the farm — peaceful here.")
        else:  # farm
            fx, fy, fw, fh = C.FARM_PORTAL_RECT_FARM
            if fx <= hx <= fx + fw and fy <= hy <= fy + fh:
                s.current_map = "main"
                px, py, pw, ph = C.FARM_PORTAL_RECT_MAIN
                s.hero.x = px - 24
                s.hero.y = py + ph // 2
                self._show_message("Returned to the main map.")

    def _try_plant_from_inventory(
        self, col: int, row: int, plant_type: str, src_slot: int,
    ) -> bool:
        """Plant a seed onto the farm grid from an inventory slot."""
        s = self.state
        if s.current_map != "farm":
            self._show_message("Plant inside the farm map!")
            return False
        if not s.farm.is_plot(col, row):
            self._show_message("Not a farm plot!")
            return False
        if s.farm.plant_at(col, row) is not None:
            self._show_message("Plot already used!")
            return False
        slot_data = s.inventory.slots[src_slot]
        if slot_data is None or slot_data["item"] != plant_type:
            return False
        s.inventory.use_slot(src_slot)
        s.farm.plant(plant_type, col, row)
        self._show_message(
            f"{C.PLANT_DEFS[plant_type]['name']} planted!"
        )
        return True

    def _try_harvest_at(self, col: int, row: int) -> bool:
        """Harvest a ripe plant on the farm map.  Returns True if harvested."""
        s = self.state
        plant = s.farm.plant_at(col, row)
        if plant is None or not plant.ripe:
            return False
        supplier_id = s.farm.harvest(col, row)
        if supplier_id is None:
            return False
        if not s.inventory.add(supplier_id, 1):
            self._show_message("Inventory full — harvest lost!")
            return False
        defn = C.SUPPLIER_DEFS[supplier_id]
        self._show_message(f"Harvested {defn['name']}!")
        return True

    # ── Shop menu ─────────────────────────────────────────────────────────

    def _open_shop_and_bag(self) -> None:
        """Open the shop menu side-by-side with the inventory overlay."""
        self.shop_menu.open()
        self.inv_overlay.open()
        # Make sure the inventory panel sits to the right of the shop panel.
        gap = 16
        total = self.shop_menu.PANEL_W + gap + self.inv_overlay.rect.w
        left = (C.SCREEN_WIDTH - total) // 2
        self.shop_menu.rect.x = left
        self.shop_menu.rect.y = (C.SCREEN_HEIGHT - self.shop_menu.PANEL_H) // 2
        self.inv_overlay.rect.x = self.shop_menu.rect.right + gap
        self.inv_overlay.rect.y = self.shop_menu.rect.y

    def _close_shop_and_bag(self) -> None:
        """Close shop + bag.  Anything left in the SELL slot returns to bag."""
        s = self.state
        unsold = self.shop_menu.close()
        for item_id, n in unsold.items():
            for _ in range(n):
                if not s.inventory.add(item_id, 1):
                    break
        self.inv_overlay.close()
        # Restore inventory rect to its centred position
        ow, oh = C.INVENTORY_OVERLAY_W, C.INVENTORY_OVERLAY_H
        self.inv_overlay.rect.x = (C.SCREEN_WIDTH  - ow) // 2
        self.inv_overlay.rect.y = (C.SCREEN_HEIGHT - oh) // 2

    def _buy_shop_item(self, item_id: str) -> None:
        """Spend gold and add a shop-only item (e.g. fish food) to inventory."""
        s    = self.state
        defn = C.ALL_DEFS.get(item_id) or C.ITEM_DEFS.get(item_id, {})
        cost = int(defn.get("cost", 0))
        if s.gold < cost:
            self._show_message(f"Need {cost}g!")
            return
        if not s.inventory.has_room_for(item_id):
            self._show_message("Inventory is full!")
            return
        s.gold -= cost
        s.inventory.add(item_id, 1)
        self._show_message(f"+1 {defn.get('name', item_id)} (-{cost}g)")

    def _confirm_shop_sell(self) -> None:
        """Convert the shop's pending-sell stash to gold."""
        s     = self.state
        stash = self.shop_menu.take_pending()
        if not stash:
            self._show_message("Nothing in the SELL slot!")
            return
        total = 0
        common = stash.get("FISH_COMMON", 0)
        rare   = stash.get("FISH_RARE",   0)
        for item_id, n in stash.items():
            price = C.ITEM_DEFS.get(item_id, {}).get("sell_price", 0)
            total += n * price
        s.gold += total
        if rare > 0 and common > 0:
            tag = f"{common} common + {rare} rare"
        elif rare > 0:
            tag = f"{rare} rare"
        else:
            tag = f"{common} common"
        self._show_message(f"Sold {tag} fish for {total}g!")

    def _sell_all_fish(self) -> None:
        """Sell every fish in the inventory at its per-item shop price."""
        s        = self.state
        common_n = s.inventory.count("FISH_COMMON")
        rare_n   = s.inventory.count("FISH_RARE")
        if common_n + rare_n <= 0:
            self._show_message("No fish to sell!")
            return
        earned = s.shop.sell_inventory_fish(s.inventory)
        s.gold += earned
        if rare_n > 0 and common_n > 0:
            tag = f"{common_n} common + {rare_n} rare"
        elif rare_n > 0:
            tag = f"{rare_n} rare"
        else:
            tag = f"{common_n} common"
        self._show_message(f"Sold {tag} fish for {earned}g!")

    def _upgrade_castle(self) -> None:
        """Spend gold to raise castle max HP by CASTLE_HP_UPGRADE_AMOUNT.

        Cost scales exponentially with upgrade level (×CASTLE_HP_UPGRADE_GROWTH per tier).
        """
        s    = self.state
        cost = s.castle.next_upgrade_cost()
        if s.gold < cost:
            self._show_message(f"Need {cost}g to reinforce the castle!")
            return
        s.gold -= cost
        s.castle.apply_upgrade()
        self._show_message(
            f"Castle reinforced! +{C.CASTLE_HP_UPGRADE_AMOUNT} max HP"
        )

    def _upgrade_hero(self, kind: str) -> None:
        """Spend gold and bump the matching hero stat tier."""
        s    = self.state
        defn = C.HERO_UPGRADE_DEFS.get(kind)
        if defn is None:
            return
        cost = int(defn["cost"])
        if s.hero.upgrades.get(kind, 0) >= int(defn["max_tier"]):
            self._show_message("Already at max tier!")
            return
        if s.gold < cost:
            self._show_message(f"Need {cost}g for that upgrade!")
            return
        if not s.hero.apply_upgrade(kind):
            return
        s.gold -= cost
        new_tier = s.hero.upgrades[kind]
        self._show_message(
            f"Hero {kind} → tier {new_tier} (+{int(defn['step'])})"
        )

    def _upgrade_selected_tower(self) -> None:
        """Spend gold to upgrade the currently selected tower by one level.

        Increases damage, range, and fire rate via Tower.upgrade().
        Defensive structures (DEFENSE category) cannot be upgraded.
        """
        s     = self.state
        tower = self.selected_tower
        if tower is None:
            self._show_message("Select a tower to upgrade!")
            return
        if tower.category == "DEFENSE":
            self._show_message("Defensive structures can't be upgraded.")
            return
        cost = tower.upgrade_cost
        if s.gold < cost:
            self._show_message(f"Need {cost}g to upgrade {tower.name}!")
            return
        s.gold -= cost
        tower.upgrade()
        self._show_message(
            f"{tower.name} → Lv {tower.level} (+dmg)"
        )

    # ── Save / load ──────────────────────────────────────────────────────

    def _take_snapshot(self) -> dict:
        """Serialise the current GameState to a JSON-safe dict for the snapshot ring buffer."""
        return state_to_dict(self.state)

    def _persist(self) -> None:
        """Write the current state + snapshot ring buffer to disk."""
        SaveManager.write(self._take_snapshot(), self.state.snapshots)

    def _save_and_quit_to_menu(self) -> None:
        """Persist the current game then exit the game loop back to the
        main menu (main.py reopens MenuScreen when run() returns)."""
        self._persist()
        self.state.paused = False
        self.running = False

    def _restore_state(self, data: dict) -> None:
        """Apply a save dict to the freshly-built GameState."""
        s = self.state
        cur = data.get("current") or data  # tolerate raw state dicts
        s.gold            = int(cur.get("gold", C.STARTING_GOLD))
        s.wave            = max(1, int(cur.get("wave", 1)))
        s.day_timer       = float(cur.get("day_timer", C.DAY_DURATION))
        s.phase           = "DAY"
        s.paused          = False

        cd = cur.get("castle", {})
        s.castle.upgrade_level = int(cd.get("upgrade_level", 0))
        s.castle.max_hp        = int(cd.get("max_hp", C.CASTLE_HP_MAX + s.castle.upgrade_bonus()))
        s.castle.hp            = int(cd.get("hp", s.castle.max_hp))

        # Pond rate (new system)
        pond_d = cur.get("pond", {})
        s.pond.current_rate = float(pond_d.get("current_rate", C.FISH_RATE_INITIAL))
        s.pond.decay_timer  = float(pond_d.get("decay_timer", 0.0))

        # Hero upgrades — replay each saved tier through apply_upgrade so
        # the matching stat (max_hp / armor / base_speed / atk1_damage)
        # gets re-derived from current config values.
        hero_d = cur.get("hero", {})
        saved_upgrades = hero_d.get("upgrades", {}) if isinstance(hero_d, dict) else {}
        for kind, tier in saved_upgrades.items():
            if kind not in C.HERO_UPGRADE_DEFS:
                continue
            try:
                tier_n = int(tier)
            except (TypeError, ValueError):
                continue
            for _ in range(max(0, tier_n)):
                s.hero.apply_upgrade(kind)
        # Heal hero to full after restoration
        s.hero.hp = s.hero.max_hp

        # Inventory
        inv_d = cur.get("inventory")
        if isinstance(inv_d, dict):
            s.inventory = Inventory.from_dict(inv_d)

        # Farm — plants placed on the farm map with their growth timers
        farm_d = cur.get("farm")
        if isinstance(farm_d, dict):
            s.farm = FarmState.from_dict(farm_d)

        # Rebuild towers
        for t in list(s.towers):
            s.grid[t.row][t.col] = "EMPTY"
        s.towers.clear()
        for td in cur.get("towers", []):
            try:
                col   = int(td["col"])
                row   = int(td["row"])
                ttype = str(td["type"])
            except (KeyError, TypeError, ValueError):
                continue
            if ttype not in C.ALL_DEFS:
                continue
            tower = create_tower(col, row, ttype)
            level = max(1, int(td.get("level", 1)))
            for _ in range(level - 1):
                tower.upgrade()
            tower.hp = float(td.get("hp", tower.max_hp))
            tower.target_mode = td.get("target_mode", "CLOSEST")
            s.towers.append(tower)
            if 0 <= row < C.GRID_ROWS and 0 <= col < C.GRID_COLS:
                s.grid[row][col] = "TOWER"

        # Snapshot history is preserved when continuing
        snaps = data.get("snapshots") if isinstance(data, dict) else None
        s.snapshots = list(snaps) if isinstance(snaps, list) else []

    # ── A* / path helpers ─────────────────────────────────────────────────────

    def _compute_astar_path(
        self, spawn_x: float, spawn_y: float
    ) -> list[tuple[int, int]]:
        """Return pixel-centre waypoints from (spawn_x, spawn_y) to castle gate."""
        from src.algorithms import AStarPathfinder
        pf    = AStarPathfinder(self.state.grid)
        start = AStarPathfinder.pixel_to_cell(spawn_x, spawn_y)
        cells = pf.find_path(start, C.CASTLE_GOAL_CELL)
        if cells:
            return [AStarPathfinder.cell_to_pixel(c, r) for c, r in cells]
        return []

    def _find_blocking_tower(self, enemy):
        """Return the closest tower within melee range of the enemy.

        A* routes around blocked tower cells, so enemies pass through adjacent
        cells (≈48 px from tower center). A range of 1.2 cells catches enemies
        that are right next to a tower without triggering at a distance.
        """
        attack_range = C.CELL_SIZE * 1.2  # ≈57 px — roughly one cell
        closest = None
        closest_dist = float("inf")
        for tower in self.state.towers:
            dist = math.hypot(enemy.x - tower.x, enemy.y - tower.y)
            if dist <= attack_range and dist < closest_dist:
                closest_dist = dist
                closest = tower
        return closest

    def _recompute_all_enemy_paths(self) -> None:
        """Recompute A* paths for every living enemy after the grid changes."""
        from src.algorithms import AStarPathfinder
        pf = AStarPathfinder(self.state.grid)
        for e in self.state.enemies:
            if e.dead or e.reached_end:
                continue
            start = AStarPathfinder.pixel_to_cell(e.x, e.y)
            cells = pf.find_path(start, C.CASTLE_GOAL_CELL)
            if cells:
                e.waypoints = [AStarPathfinder.cell_to_pixel(c, r) for c, r in cells]
                e._wp_index = 0

    # ══════════════════════════════════════════════════════════════════════
    # Wave management
    # ══════════════════════════════════════════════════════════════════════

    def _start_wave(self) -> None:
        s = self.state
        if s.phase != "DAY":
            return
        s.phase = "NIGHT"
        s._night_timer = 0.0

        wave_idx = min(s.wave - 1, len(C.WAVE_CONFIGS) - 1)
        wave_cfg = C.WAVE_CONFIGS[wave_idx]

        # Build spawn queue: (enemy_type, spawn_time)
        s._spawn_queue = []
        t = 1.0
        for etype, count, interval in wave_cfg:
            for _ in range(count):
                s._spawn_queue.append((etype, t))
                t += interval

        self._show_message(f"Wave {s.wave} begins!")

    def _check_wave_end(self) -> None:
        s = self.state
        if s.phase != "NIGHT":
            return
        living = [e for e in s.enemies if not e.dead and not e.reached_end]
        if not living and not s._spawn_queue:
            self._end_wave()

    def _end_wave(self) -> None:
        s = self.state
        # Was this the final wave?  If yes, the player WINS.
        if s.wave >= C.FINAL_WAVE:
            s.enemies.clear()
            s.phase = "DAY"
            self._handle_victory()
            return

        s.enemies.clear()
        s.phase = "DAY"
        s.wave += 1
        s.day_timer = C.DAY_DURATION   # reset 4-minute prep clock
        bonus = 50 + s.wave * 20
        if (s.wave - 1) in C.BOSS_WAVES:
            bonus += 200   # bonus for clearing a boss wave
        s.gold += bonus
        s.castle.scale_for_wave(s.wave)
        if s.wave in C.BOSS_WAVES:
            self._show_message(f"Wave cleared! +{bonus}g — BOSS NEXT!")
        else:
            self._show_message(f"Wave cleared! +{bonus}g")

        # Push snapshot for the rewind feature, then persist.
        snap = self._take_snapshot()
        s.snapshots = SaveManager.push_snapshot(s.snapshots, snap)
        self._persist()

    def _handle_victory(self) -> None:
        """Called when the player clears the final wave (Evil3 boss defeated)."""
        s = self.state
        self._show_message(f"VICTORY!  All {C.MAX_WAVE} waves cleared!")
        # Park the game in DAY phase with no further spawns; the message
        # remains until the player closes the game.  Persist the win in case
        # the user wants to keep playing on top.
        s.day_timer = C.DAY_DURATION
        s.castle.scale_for_wave(s.wave)
        snap = self._take_snapshot()
        s.snapshots = SaveManager.push_snapshot(s.snapshots, snap)
        self._persist()

    # ══════════════════════════════════════════════════════════════════════
    # Update
    # ══════════════════════════════════════════════════════════════════════

    def _update(self, dt: float) -> None:
        s = self.state
        self.renderer.update(dt)
        self.hud.update(dt)

        s.pond.update(dt)

        # Plants grow in real time, regardless of which map the hero is on
        s.farm.update(dt)

        # Tick the fishing minigame regardless of inventory overlay state.
        # The overlay can't open while a minigame is running (the I-key
        # cancels first), so this is safe.
        if self.fishing.is_running():
            self.fishing.update(dt)
        self._resolve_fishing_result()

        if self.msg_timer > 0:
            self.msg_timer -= dt
            if self.msg_timer <= 0:
                self.message = ""

        # Hero always updates (day and night)
        keys = pygame.key.get_pressed()
        s.hero.update(dt, keys)
        # Castle ticks its combat-cooldown timer so Hero.healing() can
        # consult castle._last_hit_t against HERO_HEAL_COMBAT_WINDOW.
        s.castle.tick(dt)

        # Map portal — walking into the door behind the castle warps to farm
        # and vice-versa.  Single-shot: snap hero to the matching portal on
        # the destination map so they don't immediately bounce back.
        self._check_map_portal()

        if s.phase == "DAY":
            # Count down preparation time; auto-start wave when it hits zero
            s.day_timer = max(0.0, s.day_timer - dt)
            if s.day_timer <= 0.0:
                self._start_wave()
        elif s.phase == "NIGHT":
            self._update_spawns(dt)
            self._update_enemies(dt)
            self._update_towers(dt)
            self._update_projectiles(dt)
            # Hero is safe inside the farm — skip combat there
            if s.current_map == "main":
                self._update_hero_combat(dt)
            self._check_wave_end()

        # Game-over check
        if not s.castle.alive:
            self._show_message("GAME OVER — Castle destroyed!")
            self._handle_game_over()
            return
        if not s.hero.alive:
            self._show_message("Hero has fallen! Press R to revive.")

    def _update_hero_combat(self, dt: float) -> None:
        """Hero takes counter-damage from enemies in detect range.

        Note: Attack1 is no longer auto-fired — the player drives every
        swing via left-click (see `_handle_left_click`).  This loop only
        handles the *incoming* damage from nearby enemies.
        """
        s = self.state
        hero = s.hero
        if not hero.alive:
            return

        # Enemies within detect range periodically damage the hero
        for e in s.enemies:
            if e.dead:
                continue
            dist = math.hypot(e.x - hero.x, e.y - hero.y)
            if dist <= C.HERO_DETECT_RANGE:
                e._hero_attack_timer -= dt
                if e._hero_attack_timer <= 0:
                    hero.take_damage(e.damage * C.HERO_ENEMY_DMG)
                    e._hero_attack_timer = C.HERO_ENEMY_HIT_CD

    # ── Hero Attack2 (charged stun + knockback) ───────────────────────────

    def _mark_hero_attack_anim(self) -> None:
        """Tell the renderer to play the ATTACK1 animation for ~0.5 s."""
        # Renderer's _hero_attack_until is updated via the cooldown spike
        # detector, so we don't need to set it explicitly here — leaving
        # this hook in place for future overrides.
        pass

    def _release_hero_charge(self, mx: int, my: int) -> None:
        """Release Attack2 toward (mx, my): stun + knockback enemies in cone."""
        s    = self.state
        hero = s.hero
        if not hero.attack2_charging:
            return

        held = hero.attack2_charge_t
        hero.attack2_charging = False
        hero.attack2_charge_t = 0.0

        # Direction from hero to cursor
        dx = float(mx) - hero.x
        dy = float(my) - hero.y
        mag = math.hypot(dx, dy)
        if mag < 1e-3:
            dx, dy = 1.0, 0.0
            mag    = 1.0
        nx, ny = dx / mag, dy / mag
        hero.facing_angle = math.atan2(dy, dx)

        # Pick knockback distance based on hold time
        if held >= C.HERO_ATK2_HOLD_TIER2_S:
            push_dist = float(C.HERO_ATK2_PUSH_TIER2_PX)
            tier_msg  = "MAX strike!"
        elif held >= C.HERO_ATK2_HOLD_TIER1_S:
            push_dist = float(C.HERO_ATK2_PUSH_TIER1_PX)
            tier_msg  = "Strong strike!"
        else:
            push_dist = 0.0
            tier_msg  = "Quick strike!"

        # Cooldown scales with how long the player held the charge so a
        # tap is cheap to spam (2.5 s) but a fully-charged release locks
        # you out for the full 6 s.
        charge_ratio = min(1.0, held / max(0.001, C.HERO_ATK2_HOLD_TIER2_S))
        cd = C.HERO_ATK2_COOLDOWN_MIN + charge_ratio * (
            C.HERO_ATK2_COOLDOWN_MAX - C.HERO_ATK2_COOLDOWN_MIN
        )
        hero.attack2_cd     = cd
        hero.attack2_cd_max = cd
        # Use a countdown timer on the Hero so the renderer doesn't have to
        # compare two different clocks (real time vs. accumulated game-time
        # which drifts on slow startup and made the swing anim "stick").
        hero.attack2_anim_t      = float(C.HERO_ATK2_SWING_WINDOW)
        hero.attack2_anim_window = float(C.HERO_ATK2_SWING_WINDOW)

        # Damage value for hits
        dmg = hero.atk1_damage * C.HERO_ATK2_DAMAGE_MULT

        # Affect every enemy inside the cone toward the cursor.
        # Cone = within HERO_ATK2_RANGE of hero AND in the half-space
        # facing the cursor (dot product > 0.2 ≈ ~78° cone).
        hits = 0
        for e in s.enemies:
            if e.dead:
                continue
            ex = e.x - hero.x
            ey = e.y - hero.y
            d  = math.hypot(ex, ey)
            if d > C.HERO_ATK2_RANGE:
                continue
            # Direction check — tighter cone (dot >= 0.5 ≈ ±60° = 120° wedge)
            # for better balance.  Skip the test for very-close hits.
            if d > 1.0:
                if (ex / d) * nx + (ey / d) * ny < C.HERO_ATK2_CONE_DOT:
                    continue

            # Apply stun + knockback BEFORE damage so a fatal blow doesn't
            # rob the enemy of the push (every enemy in the cone moves).
            is_boss = isinstance(e, Boss)
            if not is_boss:
                e.stun_timer = max(e.stun_timer, C.HERO_ATK2_STUN_TIME)
            if push_dist > 0.0:
                effective = (push_dist * C.HERO_ATK2_BOSS_PUSH_MULT
                             if is_boss else push_dist)
                duration  = max(0.05, C.HERO_ATK2_KNOCK_DURATION)
                e.knock_vx = nx * effective / duration
                e.knock_vy = ny * effective / duration
                e.knock_t  = duration

            # Damage last
            e.take_damage(dmg)
            hits += 1
            # Cap at 10 simultaneous targets to keep the hit-feedback
            # readable and avoid mass-AoE one-shots.
            if hits >= C.HERO_ATK2_MAX_TARGETS:
                break

        if hits > 0:
            self._show_message(f"{tier_msg} ({hits} hit{'s' if hits != 1 else ''})")
        else:
            self._show_message(tier_msg + "  (no target)")

    def _wallclock(self) -> float:
        """Seconds since pygame.init().  Used for animation triggers."""
        return pygame.time.get_ticks() / 1000.0

    # ── A* repath after knockback ─────────────────────────────────────────

    def _repath_knocked_enemy(self, e) -> None:
        """Run A* to bring an enemy that just stopped sliding back to its lane."""
        from src.algorithms import AStarPathfinder
        s = self.state
        # Find the nearest pixel on the enemy's original lane
        lane = getattr(e, "_original_lane", None) or e.waypoints
        if not lane:
            e._needs_repath = False
            return
        best_pt    = lane[-1]
        best_dist2 = float("inf")
        best_idx   = len(lane) - 1
        for i, (lx, ly) in enumerate(lane):
            d2 = (lx - e.x) ** 2 + (ly - e.y) ** 2
            if d2 < best_dist2:
                best_dist2 = d2
                best_pt    = (lx, ly)
                best_idx   = i

        # A* on the current grid
        try:
            pf = AStarPathfinder(s.grid)
            start_cell = AStarPathfinder.pixel_to_cell(int(e.x), int(e.y))
            goal_cell  = AStarPathfinder.pixel_to_cell(int(best_pt[0]),
                                                       int(best_pt[1]))
            cells = pf.find_path(start_cell, goal_cell) or []
        except Exception:
            cells = []

        # Convert cells to pixel waypoints, then append the rest of the
        # original lane after the merge point so the enemy keeps walking
        # toward the castle.
        new_path = [AStarPathfinder.cell_to_pixel(c, r) for (c, r) in cells]
        new_path.extend(lane[best_idx:])
        if new_path:
            e.waypoints  = new_path
            e._wp_index  = 0
        e._needs_repath = False

    def _update_spawns(self, dt: float) -> None:
        s = self.state
        s._night_timer += dt
        remaining = []
        for etype, spawn_t in s._spawn_queue:
            if s._night_timer >= spawn_t:
                # PvZ-style: pick a random lane and stick to it. No A* rerouting —
                # if a tower blocks the lane, the enemy stops and chews through it
                # via the proximity-based attack in _find_blocking_tower().
                lane = random.choice(C.PATH_VARIANTS)
                if etype.startswith("BOSS_"):
                    boss_id = etype[len("BOSS_"):]   # "BOSS_EVIL1" → "EVIL1"
                    # Bosses ignore the lane variants — they march straight
                    # toward the castle in a single hop.
                    spawn_y = float(C.CASTLE_CY)
                    direct_path = [
                        (0.0, spawn_y),
                        (float(C.CASTLE_CX), float(C.CASTLE_CY)),
                    ]
                    s.enemies.append(Boss(boss_id, direct_path, wave=s.wave))
                else:
                    s.enemies.append(Enemy(etype, lane, wave=s.wave))
            else:
                remaining.append((etype, spawn_t))
        s._spawn_queue = remaining

    def _update_enemies(self, dt: float) -> None:
        s = self.state

        # Assign blocking tower before movement so enemies can start attacking
        for e in s.enemies:
            if not e.dead and not e.reached_end and e.target_tower is None:
                e.target_tower = self._find_blocking_tower(e)
            # Bosses prioritise smashing the hero — feed them a hero ref
            # only while the hero is alive AND on the main map.
            if isinstance(e, Boss):
                e.hero_target = (s.hero
                                 if s.hero.alive and s.current_map == "main"
                                 else None)
            # Castle proximity — once an attacker enters the castle's hit-range
            # it can strike the building immediately, no need to walk to the
            # exact pixel centre.  Boosts physical realism near the castle gate.
            if (not e.dead and not e.reached_end
                    and e.target_tower is None):
                cd = math.hypot(e.x - s.castle.cx, e.y - s.castle.cy)
                if cd <= C.CASTLE_HIT_RANGE:
                    e.reached_end = True

        for e in list(s.enemies):
            e.update(dt)
            # If the enemy just finished a knockback slide it asked the
            # game to compute an A* path back to its original lane.
            if getattr(e, "_needs_repath", False):
                self._repath_knocked_enemy(e)
            # Drain any VFX queued by ranged bosses (Evil3 etc.)
            if isinstance(e, Boss) and getattr(e, "_pending_vfx", None):
                for (vx, vy) in e._pending_vfx:
                    s.boss_vfx.append({
                        "x": float(vx), "y": float(vy),
                        "t": 0.0, "kind": "explode",
                    })
                e._pending_vfx.clear()
            if e.dead:
                s.gold += e.reward
                s.enemies.remove(e)
            elif e.reached_end:
                # Stay at castle gate and keep attacking until killed
                e._castle_atk_timer -= dt
                if e._castle_atk_timer <= 0:
                    s.castle.take_damage(e.damage)
                    e._castle_atk_timer = 1.0
                    # Ranged boss casting on castle → spawn explosion at gate
                    if isinstance(e, Boss) and getattr(e, "is_ranged", False):
                        s.boss_vfx.append({
                            "x": float(s.castle.cx), "y": float(s.castle.cy),
                            "t": 0.0, "kind": "explode",
                        })

        # Tick existing explosion VFX — drop ones that finished animating
        EXPLODE_DURATION = 0.65   # seconds for full Explode cycle
        kept = []
        for fx in s.boss_vfx:
            fx["t"] += dt
            if fx["t"] < EXPLODE_DURATION:
                kept.append(fx)
        s.boss_vfx = kept

        # Remove towers destroyed by enemies; enemies just resume their lane
        # (no A* rerouting — PvZ-style stickiness).
        destroyed = [t for t in s.towers if not t.alive]
        if destroyed:
            for tower in destroyed:
                s.towers.remove(tower)
                s.grid[tower.row][tower.col] = "EMPTY"
                self._show_message(f"{tower.name} destroyed by enemies!")
                for e in s.enemies:
                    if e.target_tower is tower:
                        e.target_tower = None

    def _update_towers(self, dt: float) -> None:
        new_projs: list[Projectile] = []
        for tower in self.state.towers:
            tower.update(dt, self.state.enemies, new_projs)
        self.state.projectiles.extend(new_projs)

    def _update_projectiles(self, dt: float) -> None:
        s = self.state
        for p in s.projectiles:
            p.update(dt, s.enemies)
        # In-place removal — preserves the EntityLinkedList instance
        s.projectiles.remove_if(lambda p: p.dead)

    # ══════════════════════════════════════════════════════════════════════
    # Draw
    # ══════════════════════════════════════════════════════════════════════

    def _draw(self) -> None:
        s = self.state

        self.renderer.draw(
            s,
            self.selected_type,
            self.hovered_cell,
            s.phase,
            selected_tower=self.selected_tower,
            show_cast_button=self._hero_near_pond() and s.phase == "DAY"
                             and not self.fishing.is_running(),
            fishing=self.fishing,
            drag_state=self.drag_state,
        )
        # Drop a stale tower selection if the tower was removed
        if self.selected_tower is not None and self.selected_tower not in s.towers:
            self.selected_tower = None

        self.hud.draw(
            gold=s.gold,
            wave=s.wave,
            phase=s.phase,
            selected_type=self.selected_type,
            castle_hp=s.castle.hp,
            castle_max_hp=s.castle.max_hp,
            hero_hp=s.hero.hp,
            hero_max_hp=s.hero.max_hp,
            hero_alive=s.hero.alive,
            hero_stamina=s.hero.stamina,
            hero_stamina_max=C.HERO_STAMINA_MAX,
            message=self.message if self.msg_timer > 0 else "",
            day_timer=s.day_timer,
            inventory=s.inventory,
            pond_rate=s.pond.current_rate,
            castle_upgrade_lv=s.castle.upgrade_level,
            castle_upgrade_cost=s.castle.next_upgrade_cost(),
            selected_tower=self.selected_tower,
        )

        # Inventory overlay sits on top of HUD but below pause/game-over.
        # Drag-visibility rules:
        #   • Shop is OPEN  → keep both panels visible (player needs to see
        #                     the SELL slot to drop fish/supplier into it)
        #   • Shop is CLOSED + dragging → hide inventory entirely so the
        #                     map underneath is fully visible (placing
        #                     towers / plants on the world)
        #   • Otherwise (idle bag) → draw normally
        if self.shop_menu.visible:
            self.inv_overlay.draw(s.inventory,
                                  drag_active=self.drag_state is not None)
            self.shop_menu.draw(s.gold)
        elif self.drag_state is None:
            self.inv_overlay.draw(s.inventory, drag_active=False)

        # Hero upgrade overlay sits above everything else
        self.hero_upgrade_menu.draw(s.hero, s.gold)

        if s.paused:
            self._draw_pause_overlay()

        # The settings panel is modal — drawn last so it sits above the
        # pause overlay (when opened from pause) and any other UI.
        self.settings_overlay.draw()

    def _draw_pause_overlay(self) -> None:
        s    = self.screen
        surf = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 120))
        s.blit(surf, (0, 0))
        if not hasattr(self, "_font_big"):
            self._font_big = pygame.font.SysFont("consolas", 48, bold=True)
        lbl = self._font_big.render("PAUSED", True, C.UI_GOLD)
        s.blit(lbl, (C.SCREEN_WIDTH // 2 - lbl.get_width() // 2,
                     C.SCREEN_HEIGHT // 2 - lbl.get_height() // 2))

        mouse = pygame.mouse.get_pos()
        btn_font = pygame.font.SysFont("consolas", 22, bold=True)

        # SETTINGS button — opens the volume panel
        self._draw_pause_button(self._pause_settings_rect, "SETTINGS",
                                btn_font, mouse)
        # SAVE AND QUIT — persists then returns to main menu
        self._draw_pause_button(self._pause_save_quit_rect,
                                "SAVE AND QUIT", btn_font, mouse)

        hint = pygame.font.SysFont("consolas", 20).render(
            "Press ESC to resume", True, C.UI_TEXT
        )
        s.blit(hint, (C.SCREEN_WIDTH // 2 - hint.get_width() // 2,
                      self._pause_save_quit_rect.bottom + 16))

    def _draw_pause_button(self, rect: pygame.Rect, label: str,
                           font: pygame.font.Font,
                           mouse: tuple[int, int]) -> None:
        s = self.screen
        hovered = rect.collidepoint(mouse)
        bg     = C.UI_SELECTED if hovered else C.UI_PANEL
        border = C.UI_GOLD     if hovered else C.UI_BORDER
        text   = C.UI_GOLD     if hovered else C.UI_TEXT
        pygame.draw.rect(s, bg,     rect, border_radius=6)
        pygame.draw.rect(s, border, rect, 2, border_radius=6)
        lbl = font.render(label, True, text)
        s.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                     rect.centery - lbl.get_height() // 2))

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _show_message(self, msg: str, duration: float = 2.5) -> None:
        self.message   = msg
        self.msg_timer = duration

    # ── Game-over flow ────────────────────────────────────────────────────

    def _handle_game_over(self) -> None:
        """
        Show the game-over modal and act on the player's choice:

        - "rewind" : load the snapshot ~SAVE_REWIND_WAVES back and continue.
        - "new"    : wipe the save and restart from wave 1.
        - "quit"   : exit to the start menu.
        """
        s     = self.state
        wave  = s.wave
        snap  = SaveManager.pick_rewind(s.snapshots, wave)
        # Render one final frame so the modal sits over the final scene
        self._draw()
        pygame.display.flip()

        modal  = GameOverScreen(self.screen, wave_reached=wave,
                                can_rewind=snap is not None)
        choice = modal.run()

        if choice == "rewind" and snap is not None:
            # Drop the failed wave & later snapshots from the ring buffer
            try:
                target_wave = int(snap.get("wave", 1))
            except (TypeError, ValueError):
                target_wave = 1
            kept: list[dict] = []
            for sn in s.snapshots:
                try:
                    if int(sn.get("wave", 1)) <= target_wave:
                        kept.append(sn)
                except (TypeError, ValueError):
                    continue

            self._reset_world()
            self._restore_state({"current": snap, "snapshots": kept})
            self._persist()
            self._show_message(
                f"Rewound to wave {self.state.wave}. Defend the castle!"
            )
        elif choice == "new":
            SaveManager.delete()
            self._reset_world()
            self._show_message("New game!")
        else:
            # Quit back to the launcher
            self.running = False

    def _reset_world(self) -> None:
        """Re-instantiate GameState so a rewind / new game starts clean."""
        self.state          = GameState()
        self.selected_tower = None
        self.hovered_cell   = None
        self.message        = ""
        self.msg_timer      = 0.0
