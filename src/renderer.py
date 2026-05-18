"""
src/renderer.py
===============
MapRenderer — draws the game world (terrain, path, buildings, entities).
All drawing uses pygame.draw — no image files needed.
"""

from __future__ import annotations
import math
import pygame

import config as C
from src.entities import (
    Castle, Enemy, Tower, Projectile, FishPond, Shop, Hero,
)
from src.assets import Assets


class MapRenderer:
    """Draws everything inside the game world (left 960 px of the screen)."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        # Pre-build surfaces for semi-transparent overlays
        self._overlay_surf = pygame.Surface(
            (C.GAME_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA
        )
        self._time: float = 0.0   # for animations

        # Hero animation state — tracked here because Hero entity itself is
        # purely physical; the renderer maps physical state → animation state.
        self._hero_last_x:    float = float(C.HERO_START_X)
        self._hero_last_y:    float = float(C.HERO_START_Y)
        self._hero_facing_left: bool = False
        self._hero_attack_until: float = 0.0   # show ATTACK anim until this time
        self._hero_hurt_until:   float = 0.0   # show HURT anim until this time
        self._hero_last_attack_cd: float = 0.0
        self._hero_last_hp:        float = float(C.HERO_HP_MAX)

    def update(self, dt: float) -> None:
        self._time += dt

    # ══════════════════════════════════════════════════════════════════════
    # Top-level draw call
    # ══════════════════════════════════════════════════════════════════════

    def draw(
        self,
        game_state,
        selected_type: str,
        hovered_cell: tuple[int, int] | None,
        phase: str,
        selected_tower=None,
        show_cast_button: bool = False,
        fishing=None,
        drag_state=None,
    ) -> None:
        hero = game_state.hero

        # ── Farm map: simpler scene, no spawns/towers/projectiles ─────────
        if getattr(game_state, "current_map", "main") == "farm":
            self._draw_farm_terrain()
            self._draw_farm_portal_back()
            self._draw_farm_plants(game_state.farm)
            self._draw_hero(hero)
            self._draw_farm_plot_overlay(drag_state)
            # Drag preview last so the ghost icon sits above the plots
            if drag_state is not None:
                self._draw_drag_preview(drag_state, game_state)
            return

        # ── Main map (existing behaviour) ──────────────────────────────────
        self._draw_terrain()
        self._draw_spawn_area(phase)
        self._draw_interact_rings(hero, game_state.pond, game_state.shop, game_state.castle)
        self._draw_pond(game_state.pond)
        self._draw_shop(game_state.shop)
        self._draw_towers(game_state.towers)
        if selected_tower is not None:
            self._draw_tower_selection(selected_tower)
        self._draw_castle(game_state.castle)
        self._draw_farm_portal_main()
        self._draw_enemies(game_state.enemies)
        self._draw_projectiles(game_state.projectiles)
        self._draw_hero(hero)
        # Live cone preview while the player is charging Attack2
        if getattr(hero, "alive", False) and getattr(
                hero, "attack2_charging", False):
            self._draw_attack2_charge_cone(hero, pygame.mouse.get_pos())
        # Boss-cast explosions (Evil3 ranged) sit above hero/enemies
        self._draw_boss_vfx(getattr(game_state, "boss_vfx", []))
        self._draw_grid_overlay(
            game_state.grid, selected_type, hovered_cell
        )
        if phase == "NIGHT":
            self._draw_night_vignette()

        # Fishing UI overlays — drawn last so they sit above the world
        if show_cast_button:
            self._draw_cast_button(game_state.pond)
        if fishing is not None and fishing.is_running():
            if fishing.state == fishing.AWAITING_FISH:
                self._draw_fishing_waiting(game_state.pond)
            else:
                self._draw_fishing_minigame(fishing)

        # Drag-and-drop preview — ghost icon following the cursor
        if drag_state is not None:
            self._draw_drag_preview(drag_state, game_state)

    def _draw_tower_selection(self, tower) -> None:
        """Highlight the tower the player has selected for upgrade."""
        s  = self.screen
        cx = int(tower.x)
        cy = int(tower.y)

        # Range ring (animated dashed effect by alpha pulse)
        rng = int(max(C.CELL_SIZE // 2, tower.range))
        pulse = int(120 + 80 * abs(math.sin(self._time * 3)))
        ring  = pygame.Surface((rng * 2 + 4, rng * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 220, 80, 32),
                           (rng + 2, rng + 2), rng)
        pygame.draw.circle(ring, (255, 220, 80, pulse),
                           (rng + 2, rng + 2), rng, 2)
        s.blit(ring, (cx - rng - 2, cy - rng - 2))

        # Selection box around the cell
        cell_x = tower.col * C.CELL_SIZE
        cell_y = tower.row * C.CELL_SIZE
        pygame.draw.rect(
            s, (255, 220, 80),
            (cell_x + 1, cell_y + 1, C.CELL_SIZE - 2, C.CELL_SIZE - 2),
            2,
        )

    # ══════════════════════════════════════════════════════════════════════
    # Terrain
    # ══════════════════════════════════════════════════════════════════════

    def _draw_terrain(self) -> None:
        """Tile the world with grass_02 and grass_03 sprites for an organic look."""
        s = self.screen
        # Cache the deterministic tile pattern once — random per (row, col)
        # but stable across frames so the world doesn't shimmer.
        if not hasattr(self, "_grass_pattern"):
            import random as _r
            rng = _r.Random(1337)
            self._grass_pattern = [
                [rng.randint(1, 2) for _ in range(C.GRID_COLS)]
                for _ in range(C.GRID_ROWS)
            ]

        # Pre-scaled 48×48 grass tiles (grass_02 idx=1, grass_03 idx=2)
        tile_a = Assets.grass_tile(1)   # spr_grass_02
        tile_b = Assets.grass_tile(2)   # spr_grass_03

        if tile_a is None or tile_b is None:
            # Fallback to flat green if assets missing
            pygame.draw.rect(s, C.GRASS_DARK,
                             (0, 0, C.GAME_WIDTH, C.SCREEN_HEIGHT))
        else:
            # Re-scale once to exactly CELL_SIZE so cells align cleanly
            cell = C.CELL_SIZE
            if tile_a.get_width() != cell:
                tile_a = pygame.transform.scale(tile_a, (cell, cell))
            if tile_b.get_width() != cell:
                tile_b = pygame.transform.scale(tile_b, (cell, cell))
            for row in range(C.GRID_ROWS):
                for col in range(C.GRID_COLS):
                    tile = tile_a if self._grass_pattern[row][col] == 1 else tile_b
                    s.blit(tile, (col * cell, row * cell))

        self._draw_trees()

    def _draw_trees(self) -> None:
        """Place trees and rocks at fixed positions using sprite assets."""
        # (x, y, tree_idx) — y is the FOOT of the tree (sprite's bottom)
        tree_spots = [
            (50, 100, 0), (120, 70, 1), (870, 100, 2), (900, 180, 0),
            (820, 520, 3), (60, 460, 1), (140, 500, 0), (750, 620, 2),
            (800, 660, 4), (440, 110, 1), (500, 80, 3), (580, 120, 0),
            (680, 100, 4),
        ]
        for tx, ty, idx in tree_spots:
            self._draw_tree(tx, ty, idx)

        # Sprinkle a few rocks in unused corners
        rock_spots = [
            (200, 120, 0), (760, 50, 1), (40, 380, 2),
            (330, 670, 1), (640, 690, 0),
        ]
        for rx, ry, idx in rock_spots:
            rock = Assets.rock(idx)
            if rock is not None:
                rw, rh = rock.get_size()
                self.screen.blit(rock, (rx - rw // 2, ry - rh // 2))

    def _draw_tree(self, cx: int, cy: int, idx: int = 0) -> None:
        """Draw one tree sprite anchored so its base sits at (cx, cy)."""
        sprite = Assets.tree(idx)
        if sprite is None:
            return
        sw, sh = sprite.get_size()
        self.screen.blit(sprite, (cx - sw // 2, cy - sh))

    # ══════════════════════════════════════════════════════════════════════
    # Path
    # ══════════════════════════════════════════════════════════════════════

    def _draw_path(self) -> None:
        s  = self.screen
        hw = C.PATH_WIDTH // 2

        # Alternate routes first (drawn underneath, lighter)
        alt_edge  = (90,  65, 32)
        alt_mid   = (130, 100, 55)
        for pts in C.PATH_VARIANTS[1:]:
            for i in range(len(pts) - 1):
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                pygame.draw.line(s, alt_edge, (x0, y0), (x1, y1), C.PATH_WIDTH + 8)
                pygame.draw.line(s, alt_mid,  (x0, y0), (x1, y1), C.PATH_WIDTH - 4)
            for pt in pts:
                pygame.draw.circle(s, alt_mid, pt, hw - 2)

        # Main path (Variant A) on top
        pts = C.PATH_VARIANTS[0]
        for edge, color, width in [
            (hw + 6, C.PATH_EDGE, C.PATH_WIDTH + 12),
            (hw,     C.PATH_MID,  C.PATH_WIDTH),
        ]:
            for i in range(len(pts) - 1):
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                pygame.draw.line(s, color, (x0, y0), (x1, y1), width)

        for pt in pts:
            pygame.draw.circle(s, C.PATH_MID, pt, hw)
            pygame.draw.circle(s, C.PATH_EDGE, pt, hw + 5, 4)

        # Wheel-rut detail on main path
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            dx, dy = x1 - x0, y1 - y0
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            nx, ny = -dy / dist, dx / dist
            off = 10
            pygame.draw.line(s, C.PATH_EDGE,
                (int(x0 + nx * off), int(y0 + ny * off)),
                (int(x1 + nx * off), int(y1 + ny * off)), 2)
            pygame.draw.line(s, C.PATH_EDGE,
                (int(x0 - nx * off), int(y0 - ny * off)),
                (int(x1 - nx * off), int(y1 - ny * off)), 2)

    # ══════════════════════════════════════════════════════════════════════
    # Spawn area
    # ══════════════════════════════════════════════════════════════════════

    def _draw_spawn_area(self, phase: str) -> None:
        s = self.screen
        # Dark background
        pygame.draw.rect(s, C.SPAWN_BG, (0, 0, 90, C.SCREEN_HEIGHT))

        # Animated glow in night phase
        if phase == "NIGHT":
            glow_alpha = int(60 + 40 * math.sin(self._time * 2))
            glow_surf = pygame.Surface((90, C.SCREEN_HEIGHT), pygame.SRCALPHA)
            glow_surf.fill((*C.SPAWN_GLOW, glow_alpha))
            s.blit(glow_surf, (0, 0))

        # Vertical stone border
        for i in range(0, C.SCREEN_HEIGHT, 30):
            shade = C.STONE_DARK if i % 60 == 0 else C.STONE_MID
            pygame.draw.rect(s, shade, (82, i, 8, 28))

        # Portal gate arch
        gate_cx, gate_cy = 45, 360
        pygame.draw.rect(s, C.SPAWN_GATE, (gate_cx - 20, gate_cy - 35, 40, 60))
        pygame.draw.ellipse(s, (80, 5, 5), (gate_cx - 20, gate_cy - 50, 40, 32))
        # Glowing portal interior
        pulse = int(80 + 60 * math.sin(self._time * 3))
        pygame.draw.ellipse(s, (pulse, 0, 0), (gate_cx - 14, gate_cy - 45, 28, 24))
        # Skull decorations
        self._draw_skull(s, gate_cx - 22, gate_cy - 65, 7)
        self._draw_skull(s, gate_cx + 15, gate_cy - 65, 7)

        # Label
        if not hasattr(self, "_font_sm"):
            self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
        lbl = self._font_sm.render("SPAWN", True, (180, 60, 60))
        s.blit(lbl, (5, 8))

    def _draw_skull(self, s, cx, cy, r):
        pygame.draw.circle(s, C.SPAWN_BONE, (cx, cy), r)
        eye_r = max(1, r // 3)
        pygame.draw.circle(s, C.SPAWN_BG, (cx - eye_r, cy - 1), eye_r)
        pygame.draw.circle(s, C.SPAWN_BG, (cx + eye_r, cy - 1), eye_r)
        pygame.draw.rect(s, C.SPAWN_BG, (cx - eye_r, cy + eye_r - 1, eye_r * 2, eye_r + 1))

    # ══════════════════════════════════════════════════════════════════════
    # Interaction range rings (pond / shop / castle safe zone)
    # ══════════════════════════════════════════════════════════════════════

    def _draw_interact_rings(self, hero, pond, shop, castle) -> None:
        """Draw proximity rings around interactable objects based on hero distance."""
        s = self.screen

        def _ring(cx, cy, radius, near_color, far_color, label):
            dist = math.hypot(hero.x - cx, hero.y - cy)
            in_range = dist <= radius
            # Fade the ring in as hero approaches (visible from 1.6× range)
            vis_range = radius * 1.6
            if dist > vis_range:
                return
            if label == "Safe zone — HP regen": hero.healing(castle)
            t = max(0.0, 1.0 - dist / vis_range)   # 0→1 as hero gets closer
            alpha = int(t * (160 if in_range else 80))
            color  = near_color if in_range else far_color

            surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, alpha // 3),
                               (radius + 2, radius + 2), radius)
            pygame.draw.circle(surf, (*color, alpha),
                               (radius + 2, radius + 2), radius, 2)
            s.blit(surf, (int(cx) - radius - 2, int(cy) - radius - 2))

            if in_range and not hasattr(self, "_font_sm"):
                self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
            if in_range:
                lbl = self._font_sm.render(label, True, color)
                s.blit(lbl, (int(cx) - lbl.get_width() // 2, int(cy) - radius - 18))

        _ring(pond.cx, pond.cy,
              C.POND_INTERACT_RANGE,
              (80, 200, 255), (80, 160, 200),
              "E — Fish")
        _ring(shop.cx, shop.cy,
              C.SHOP_INTERACT_RANGE,
              (255, 210, 60), (180, 150, 40),
              "E — Buy/Sell")
        _ring(int(castle.cx), int(castle.cy),
              C.CASTLE_SAFE_RANGE,
              (120, 200, 120), (80, 140, 80),
              "Safe zone — HP regen")

    # ══════════════════════════════════════════════════════════════════════
    # Fishing pond
    # ══════════════════════════════════════════════════════════════════════

    def _draw_pond(self, pond: FishPond) -> None:
        """Draw the pond using the 4-frame animated lake sprite."""
        s = self.screen
        x, y, w, h = pond.x, pond.y, pond.w, pond.h

        frame = Assets.lake_frame(self._time)
        if frame is not None:
            s.blit(frame, (x, y))
        else:
            # Fallback: simple blue ellipse
            pygame.draw.ellipse(s, C.WATER_MID, (x, y, w, h))

        # Label
        if not hasattr(self, "_font_sm"):
            self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
        lbl = self._font_sm.render("Fishing Pond", True, C.WATER_LIGHT)
        s.blit(lbl, (pond.cx - lbl.get_width() // 2, pond.y + pond.h + 4))

    def _draw_cast_button(self, pond) -> None:
        """Draw the world-space "Cast" button shown when the hero is near the pond."""
        s = self.screen
        bx, by, bw, bh = C.FISH_BUTTON_RECT

        # Subtle pulsing glow so the button reads as interactive
        pulse = int(80 + 60 * abs(math.sin(self._time * 3)))
        glow_surf = pygame.Surface((bw + 16, bh + 16), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (180, 230, 255, pulse),
                         glow_surf.get_rect(), border_radius=10)
        s.blit(glow_surf, (bx - 8, by - 8))

        pygame.draw.rect(s, (40, 90, 130), (bx, by, bw, bh), border_radius=6)
        pygame.draw.rect(s, (160, 220, 255), (bx, by, bw, bh), 2, border_radius=6)

        if not hasattr(self, "_font_cast"):
            self._font_cast = pygame.font.SysFont("consolas", 14, bold=True)
        lbl = self._font_cast.render("CAST", True, (220, 245, 255))
        s.blit(lbl, (bx + (bw - lbl.get_width()) // 2,
                     by + (bh - lbl.get_height()) // 2))

        # Tiny rate readout under the button so the player sees current odds
        rate_pct = f"{int(pond.current_rate * 100)}%"
        if not hasattr(self, "_font_castsm"):
            self._font_castsm = pygame.font.SysFont("consolas", 11)
        rl = self._font_castsm.render(rate_pct, True, (200, 230, 255))
        s.blit(rl, (bx + (bw - rl.get_width()) // 2, by + bh + 2))

    def _draw_fishing_waiting(self, pond) -> None:
        """Subtle world-space indicator that the hero is currently fishing.

        No big overlay, no 'Casting...' message — per spec, the player simply
        enters fishing state and waits until a fish bites.
        """
        s = self.screen
        # Pulsing dot above the pond
        pulse_alpha = int(140 + 80 * abs(math.sin(self._time * 4)))
        ring = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 230, 100, pulse_alpha), (18, 18), 10)
        pygame.draw.circle(ring, (255, 230, 100, 220), (18, 18), 10, 2)
        s.blit(ring, (pond.cx - 18, pond.y - 36))

        # Animated three-dot bait indicator
        if not hasattr(self, "_font_waitsm"):
            self._font_waitsm = pygame.font.SysFont("consolas", 12, bold=True)
        dots = "." * (1 + int(self._time * 3) % 3)
        lbl = self._font_waitsm.render(dots, True, (255, 230, 100))
        s.blit(lbl, (pond.cx - lbl.get_width() // 2, pond.y - 60))

    def _draw_fishing_minigame(self, fishing) -> None:
        """Draw the click-timing minigame overlay (red bar + green zone + slider)."""
        s = self.screen

        # Dim background
        veil = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 110))
        s.blit(veil, (0, 0))

        if not hasattr(self, "_font_minititle"):
            self._font_minititle = pygame.font.SysFont("consolas", 18, bold=True)
            self._font_minihint  = pygame.font.SysFont("consolas", 12)

        # Centered bar
        bw = C.FISHING_BAR_W
        bh = C.FISHING_BAR_H
        bx = (C.GAME_WIDTH - bw) // 2
        by = (C.SCREEN_HEIGHT - bh) // 2

        # Hits counter (concise, no "Casting..." or "Fishing —" prefix)
        title = f"{fishing.hits} / {C.FISHING_HITS_REQUIRED}"
        tlbl = self._font_minititle.render(title, True, (255, 230, 140))
        s.blit(tlbl, (bx + (bw - tlbl.get_width()) // 2, by - 32))

        # Red bar (background)
        pygame.draw.rect(s, (40, 10, 12),
                         (bx - 2, by - 2, bw + 4, bh + 4), border_radius=8)
        pygame.draw.rect(s, (180, 50, 50), (bx, by, bw, bh), border_radius=6)

        # Green zone
        gx = bx + int(fishing.green_start * bw)
        gw = max(2, int(fishing.green_width * bw))
        pygame.draw.rect(s, (60, 200, 90), (gx, by, gw, bh), border_radius=6)
        pygame.draw.rect(s, (20, 90, 40), (gx, by, gw, bh), 2, border_radius=6)

        # White slider (vertical line + small triangle markers)
        sx = bx + int(fishing.slider_pos * bw)
        pygame.draw.line(s, (255, 255, 255), (sx, by - 4), (sx, by + bh + 4), 3)
        pygame.draw.polygon(s, (255, 255, 255), [
            (sx - 6, by - 12), (sx + 6, by - 12), (sx, by - 4),
        ])
        pygame.draw.polygon(s, (255, 255, 255), [
            (sx - 6, by + bh + 12), (sx + 6, by + bh + 12), (sx, by + bh + 4),
        ])

        # Border
        pygame.draw.rect(s, (255, 220, 140), (bx, by, bw, bh), 2, border_radius=6)

        # Hint
        hint = self._font_minihint.render(
            "Click while the slider is on green!  ESC to stop.",
            True, (220, 220, 240),
        )
        s.blit(hint, (bx + (bw - hint.get_width()) // 2, by + bh + 18))

    # ══════════════════════════════════════════════════════════════════════
    # Drag-and-drop preview
    # ══════════════════════════════════════════════════════════════════════

    def _draw_drag_preview(self, drag_state: dict, game_state) -> None:
        """Render a ghost icon at the cursor + highlight valid drop targets."""
        s = self.screen
        item_id = drag_state.get("item_id")
        if item_id is None:
            return
        defn   = C.ITEM_DEFS.get(item_id, {})
        target = defn.get("drag_target")

        mx, my = pygame.mouse.get_pos()

        # Highlight valid drop targets in the world
        if mx < C.GAME_WIDTH:
            if target == "POND":
                # Glow ring around the pond interaction radius
                pond  = game_state.pond
                pulse = int(80 + 80 * abs(math.sin(self._time * 4)))
                ring  = pygame.Surface(
                    (C.POND_INTERACT_RANGE * 2 + 8,
                     C.POND_INTERACT_RANGE * 2 + 8),
                    pygame.SRCALPHA,
                )
                pygame.draw.circle(ring, (140, 220, 255, pulse),
                                   ring.get_rect().center,
                                   C.POND_INTERACT_RANGE, 4)
                s.blit(ring,
                       (pond.cx - C.POND_INTERACT_RANGE - 4,
                        pond.cy - C.POND_INTERACT_RANGE - 4))
            elif target == "GRID":
                # Highlight the cell under the cursor: green if placeable, red otherwise
                col = mx // C.CELL_SIZE
                row = my // C.CELL_SIZE
                if 0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS:
                    placeable = game_state.grid[row][col] in ("EMPTY", "PATH")
                    color = (80, 255, 80, 90) if placeable else (255, 60, 60, 90)
                    cell  = pygame.Surface((C.CELL_SIZE, C.CELL_SIZE),
                                           pygame.SRCALPHA)
                    cell.fill(color)
                    s.blit(cell,
                           (col * C.CELL_SIZE, row * C.CELL_SIZE))

        # Ghost icon following the cursor
        color = defn.get("color", (200, 200, 220))
        ghost = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.rect(ghost, (*color, 200), (4, 4, 32, 32), border_radius=6)
        pygame.draw.rect(ghost, (255, 255, 255, 220),
                         (4, 4, 32, 32), 2, border_radius=6)
        s.blit(ghost, (mx - 20, my - 20))

    # ══════════════════════════════════════════════════════════════════════
    # Shop
    # ══════════════════════════════════════════════════════════════════════

    def _draw_shop(self, shop: Shop) -> None:
        """Draw the shop using the shop.png sprite, anchored over its footprint."""
        s = self.screen
        x, y, w, h = shop.x, shop.y, shop.w, shop.h

        sprite = Assets.shop()
        if sprite is not None:
            sw, sh = sprite.get_size()
            # Centre horizontally on the shop footprint; align bottom with
            # the bottom of the configured rect so the building sits flush
            # on the ground.
            sx = shop.cx - sw // 2
            sy = (y + h) - sh
            s.blit(sprite, (sx, sy))
        else:
            # Vector fallback (kept compact)
            pygame.draw.rect(s, C.SHOP_WALL, (x, y, w, h), border_radius=4)

        ''' Sign above the shop
        sign_rect = (x + 10, y - 50, w - 20, 22)
        pygame.draw.rect(s, C.SHOP_SIGN, sign_rect, border_radius=3)
        pygame.draw.rect(s, (160, 120, 40), sign_rect, 2, border_radius=3)
        if not hasattr(self, "_font_sm"):
            self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
        #lbl = self._font_sm.render("SHOP", True, (80, 40, 0))
        #s.blit(lbl, (x + w // 2 - lbl.get_width() // 2, y - 46))'''

    # ══════════════════════════════════════════════════════════════════════
    # Castle
    # ══════════════════════════════════════════════════════════════════════

    def _draw_castle(self, castle: Castle) -> None:
        """Blit the castle sprite anchored at the castle centre, plus HP bar + label."""
        s      = self.screen
        cx     = int(castle.cx)
        cy     = int(castle.cy)
        sprite = Assets.castle(self._time)

        if sprite is not None:
            sw, sh = sprite.get_size()
            # Anchor: bottom of castle sprite roughly at cy + 50 so it sits
            # over the building footprint that game.py reserves around the gate.
            # Clamp X so the wide sprite never overflows under the HUD panel.
            sx = max(0, min(cx - sw // 2, C.GAME_WIDTH - sw - 4))
            sy = cy + 50 - sh
            s.blit(sprite, (sx, sy))

            # Soft warm window glow on top so the castle feels alive
            glow_alpha = int(80 + 40 * math.sin(self._time * 1.5))
            glow_surf  = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.rect(
                glow_surf,
                (*C.WINDOW_GLOW, glow_alpha // 4),
                (sw // 4, sh // 3, sw // 2, sh // 3),
            )
            s.blit(glow_surf, (sx, sy))
        else:
            # Fallback: minimal stone block so the game is still playable
            pygame.draw.rect(s, C.STONE_MID, (cx - 42, cy - 56, 84, 100),
                             border_radius=4)

        # HP bar (above the castle sprite)
        self._draw_hp_bar(s, cx, cy - 90, 90, 9, castle.hp, castle.max_hp)

        # Label
        if not hasattr(self, "_font_sm"):
            self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
        lbl = self._font_sm.render("Castle", True, C.STONE_LIGHT)
        s.blit(lbl, (cx - lbl.get_width() // 2, cy - 106))

    def _draw_tower_keep(self, s, x, cy, w, h):
        r = pygame.Rect(x, cy - h // 2, w, h)
        pygame.draw.rect(s, C.STONE_DARK, r.inflate(3, 3), border_radius=3)
        pygame.draw.rect(s, C.STONE_MID,  r, border_radius=3)
        # Cone roof
        roof_pts = [(x - 2, cy - h // 2), (x + w + 2, cy - h // 2),
                    (x + w // 2, cy - h // 2 - 18)]
        pygame.draw.polygon(s, (100, 20, 20), roof_pts)
        # Battlements
        for bx in range(x, x + w, 8):
            pygame.draw.rect(s, C.STONE_LIGHT, (bx, cy - h // 2 - 8, 6, 8))

    # ══════════════════════════════════════════════════════════════════════
    # Towers
    # ══════════════════════════════════════════════════════════════════════

    def _draw_towers(self, towers) -> None:
        for t in towers:
            self._draw_single_tower(t)

    def _draw_single_tower(self, t: Tower) -> None:
        """Blit tower sprite anchored over its grid cell, plus per-type effect overlays."""
        s  = self.screen
        cx = int(t.x)
        cy = int(t.y)
        tt = t.tower_type

        # Shadow
        pygame.draw.ellipse(s, (20, 40, 20), (cx - 16, cy + 16, 32, 10))

        # Walls/fences/spikes/barricades use the original hand-drawn vector
        # graphics; only combat towers use sprite assets.
        non_combat = ("WALL", "FENCE", "SPIKE", "BARRICADE")
        if tt in non_combat:
            if tt == "WALL":      self._draw_wall(s, cx, cy, t)
            elif tt == "FENCE":   self._draw_fence(s, cx, cy, t)
            elif tt == "SPIKE":   self._draw_spike(s, cx, cy, t)
            elif tt == "BARRICADE": self._draw_barricade(s, cx, cy, t)
        else:
            sprite = Assets.tower(tt)
            if sprite is not None:
                sw, sh = sprite.get_size()
                # Anchor: bottom of sprite sits at the bottom of its grid cell
                sx = cx - sw // 2
                sy = cy + C.CELL_SIZE // 2 - sh
                s.blit(sprite, (sx, sy))
            else:
                pygame.draw.rect(s, C.STONE_MID, (cx - 14, cy - 14, 28, 28))

        # Per-type animated effects on top of the static sprite
        if tt == "TESLA":
            self._draw_tesla_arc(s, cx, cy)
        elif tt == "FLAME":
            self._draw_flame_glow(s, cx, cy)
        elif tt == "ICE":
            self._draw_ice_glow(s, cx, cy)

        # HP bar for damaged defensive items so the player can see condition
        if getattr(t, "category", "TOWER") == "DEFENSE" and t.hp < t.max_hp:
            self._draw_hp_bar(s, cx, cy - 24, 38, 4, t.hp, t.max_hp)

        # Level badge
        if t.level > 1:
            if not hasattr(self, "_font_xs"):
                self._font_xs = pygame.font.SysFont("consolas", 10, bold=True)
            lbl = self._font_xs.render(f"Lv{t.level}", True, C.UI_GOLD)
            s.blit(lbl, (cx - lbl.get_width() // 2, cy - 32))

    def _draw_tesla_arc(self, s, cx: int, cy: int) -> None:
        """Animated electrical arc on top of the tesla sprite."""
        arc_phase = self._time * 8
        top_y = cy - 30
        mid_y = top_y - 6 + int(4 * math.sin(arc_phase))
        pygame.draw.line(s, C.TOWER_TESLA_GLOW,
                         (cx - 6, top_y), (cx, mid_y), 2)
        pygame.draw.line(s, C.TOWER_TESLA_GLOW,
                         (cx, mid_y), (cx + 6, top_y), 2)
        pygame.draw.circle(s, C.TOWER_TESLA_GLOW, (cx, mid_y), 3)

    def _draw_flame_glow(self, s, cx: int, cy: int) -> None:
        """Animated fire ring above the flame tower sprite."""
        t_phase = self._time * 5
        for fi in range(5):
            fx = cx + int(8 * math.sin(t_phase + fi * 1.2))
            fy = cy - 32 - int(6 * abs(math.cos(t_phase + fi * 0.9)))
            r  = max(2, 5 - fi)
            pygame.draw.circle(s, C.TOWER_FLAME_FIRE, (fx, fy), r)
        pygame.draw.circle(s, (255, 220, 80), (cx, cy - 36), 3)

    def _draw_ice_glow(self, s, cx: int, cy: int) -> None:
        """Subtle pulsing snowflake glow on top of the ice tower sprite."""
        pulse = int(80 + 60 * abs(math.sin(self._time * 2)))
        glow = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(glow, (180, 230, 255, pulse), (14, 14), 12)
        s.blit(glow, (cx - 14, cy - 38))

    def _draw_ballista(self, s, cx, cy, t):
        # Wooden base
        pygame.draw.rect(s, C.TOWER_BALLISTA_BASE, (cx - 14, cy - 16, 28, 30), border_radius=3)
        pygame.draw.rect(s, C.TOWER_BALLISTA_TOP,  (cx - 10, cy - 22, 20, 10), border_radius=2)
        # Battlements
        for bx in [-10, -3, 4]:
            pygame.draw.rect(s, C.TOWER_BALLISTA_BASE, (cx + bx, cy - 30, 6, 8))
        # Crossbow arm
        ax = math.cos(t.firing_angle)
        ay = math.sin(t.firing_angle)
        arm_len = 20
        pygame.draw.line(s, (50, 35, 15),
                         (cx - int(ay * 10), cy + int(ax * 10)),
                         (cx + int(ay * 10), cy - int(ax * 10)), 4)
        pygame.draw.line(s, (80, 55, 25),
                         (cx, cy),
                         (int(cx + ax * arm_len), int(cy + ay * arm_len)), 3)

    def _draw_cannon(self, s, cx, cy, t):
        # Stone base
        pygame.draw.circle(s, C.TOWER_CANNON_BASE, (cx, cy + 6), 17)
        pygame.draw.circle(s, C.STONE_LIGHT, (cx, cy + 6), 15, 2)
        # Drum
        pygame.draw.circle(s, C.TOWER_CANNON_TOP, (cx, cy - 6), 12)
        # Barrel (rotates with firing_angle)
        bx = math.cos(t.firing_angle)
        by = math.sin(t.firing_angle)
        barrel_len = 22
        pygame.draw.line(s, (40, 40, 45),
                         (cx, cy - 6),
                         (int(cx + bx * barrel_len), int(cy - 6 + by * barrel_len)), 7)
        pygame.draw.line(s, (80, 80, 85),
                         (cx, cy - 6),
                         (int(cx + bx * barrel_len), int(cy - 6 + by * barrel_len)), 4)
        pygame.draw.circle(s, (50, 50, 55),
                           (int(cx + bx * barrel_len), int(cy - 6 + by * barrel_len)), 4)

    def _draw_tesla(self, s, cx, cy, t):
        # Dark base
        pygame.draw.rect(s, C.TOWER_TESLA_BASE, (cx - 12, cy - 14, 24, 28), border_radius=3)
        pygame.draw.rect(s, C.TOWER_TESLA_TOP,  (cx - 8,  cy - 22, 16, 10), border_radius=2)
        # Lightning coils (two antennas)
        pygame.draw.line(s, C.TOWER_TESLA_TOP, (cx - 6, cy - 22), (cx - 6, cy - 36), 3)
        pygame.draw.line(s, C.TOWER_TESLA_TOP, (cx + 6, cy - 22), (cx + 6, cy - 36), 3)
        pygame.draw.circle(s, C.TOWER_TESLA_GLOW, (cx - 6, cy - 37), 5)
        pygame.draw.circle(s, C.TOWER_TESLA_GLOW, (cx + 6, cy - 37), 5)
        # Animated electrical arc
        arc_phase = self._time * 8
        mid_y = cy - 37 + int(4 * math.sin(arc_phase))
        pygame.draw.line(s, C.TOWER_TESLA_GLOW, (cx - 6, cy - 37),
                         (cx, mid_y), 2)
        pygame.draw.line(s, C.TOWER_TESLA_GLOW, (cx, mid_y),
                         (cx + 6, cy - 37), 2)

    def _draw_ice(self, s, cx, cy, t):
        # Crystal base
        pygame.draw.rect(s, C.TOWER_ICE_BASE, (cx - 12, cy - 14, 24, 28), border_radius=4)
        # Crystal spires
        for off, h in [(-8, 20), (0, 28), (8, 20)]:
            pts = [(cx + off - 5, cy - 14),
                   (cx + off + 5, cy - 14),
                   (cx + off,     cy - 14 - h)]
            pygame.draw.polygon(s, C.TOWER_ICE_CRYSTAL, pts)
            pygame.draw.polygon(s, C.TOWER_ICE_TOP,     pts, 1)
        # Snowflake glow
        for angle in range(0, 360, 60):
            rad = math.radians(angle)
            ex = cx + int(10 * math.cos(rad))
            ey = cy - 30 + int(10 * math.sin(rad))
            pygame.draw.line(s, (200, 240, 255), (cx, cy - 30), (ex, ey), 1)

    def _draw_flame(self, s, cx, cy, t):
        # Brick base
        pygame.draw.rect(s, C.TOWER_FLAME_BASE, (cx - 12, cy - 14, 24, 28), border_radius=2)
        # Brick pattern lines
        for ry in range(cy - 14, cy + 14, 8):
            pygame.draw.line(s, (110, 30, 10), (cx - 12, ry), (cx + 12, ry), 1)
        # Flame top (animated)
        t_phase = self._time * 5
        for fi in range(5):
            fx = cx + int(8 * math.sin(t_phase + fi * 1.2))
            fy = cy - 18 - int(6 * abs(math.cos(t_phase + fi * 0.9)))
            r  = max(2, 5 - fi)
            color_lerp = fi / 4
            color = (
                255,
                int(C.TOWER_FLAME_FIRE[1] * (1 - color_lerp)),
                0,
            )
            pygame.draw.circle(s, color, (fx, fy), r)

    # ── Defensive structures ──────────────────────────────────────────────────

    def _draw_wall(self, s, cx, cy, t):
        """Stone-block wall."""
        # Base shadow
        pygame.draw.rect(s, C.WALL_DARK, (cx - 18, cy - 16, 36, 32), border_radius=2)
        # Brick pattern (3 rows × 2 columns, alternating)
        brick_w, brick_h = 16, 9
        for ri in range(3):
            offset = (ri % 2) * (brick_w // 2 - 2)
            ry = cy - 14 + ri * (brick_h + 1)
            for ci in range(-1, 2):
                bx = cx - brick_w // 2 + ci * brick_w + offset
                pygame.draw.rect(s, C.WALL_STONE,
                                 (bx, ry, brick_w - 1, brick_h),
                                 border_radius=1)
                pygame.draw.rect(s, C.WALL_LIGHT,
                                 (bx + 1, ry + 1, brick_w - 5, 2))
        # Outer mortar border
        pygame.draw.rect(s, C.WALL_MORTAR, (cx - 18, cy - 16, 36, 32), 1, border_radius=2)

    def _draw_fence(self, s, cx, cy, t):
        """Wooden picket fence."""
        # Bottom base shadow
        pygame.draw.rect(s, C.FENCE_DARK, (cx - 18, cy + 8, 36, 4))
        # 4 vertical posts with pointed tops
        post_w = 6
        positions = [-15, -6, 3, 12]
        for px in positions:
            pts = [
                (cx + px, cy - 16),
                (cx + px + post_w // 2, cy - 20),
                (cx + px + post_w, cy - 16),
                (cx + px + post_w, cy + 12),
                (cx + px,          cy + 12),
            ]
            pygame.draw.polygon(s, C.FENCE_WOOD, pts)
            pygame.draw.polygon(s, C.FENCE_DARK, pts, 1)
            # Wood grain stripe
            pygame.draw.line(s, C.FENCE_LIGHT,
                             (cx + px + 1, cy - 13),
                             (cx + px + 1, cy + 10), 1)
        # Two horizontal cross-beams
        for by in (cy - 8, cy + 4):
            pygame.draw.rect(s, C.FENCE_DARK, (cx - 18, by, 36, 3))
            pygame.draw.line(s, C.FENCE_LIGHT, (cx - 18, by + 1), (cx + 18, by + 1), 1)

    def _draw_spike(self, s, cx, cy, t):
        """Spike trap with animated pulse."""
        # Base plate
        pygame.draw.rect(s, C.WALL_DARK, (cx - 18, cy + 6, 36, 10), border_radius=2)
        pygame.draw.rect(s, C.SPIKE_BASE, (cx - 16, cy + 4, 32, 8), border_radius=2)
        # Pulse alpha for "ready to hit" feel
        pulse = 0.5 + 0.5 * math.sin(self._time * 4)

        # 5 metal spikes
        for i, sx_off in enumerate((-14, -7, 0, 7, 14)):
            tip_y = cy - 14 - int(2 * pulse * (i % 2))
            base_l = (cx + sx_off - 4, cy + 4)
            base_r = (cx + sx_off + 4, cy + 4)
            tip    = (cx + sx_off, tip_y)
            pygame.draw.polygon(s, C.SPIKE_BASE, [base_l, base_r, tip])
            # Sharp highlight on left edge
            pygame.draw.line(s, C.SPIKE_TIP, base_l, tip, 1)
            # Tiny blood tip
            pygame.draw.circle(s, C.SPIKE_BLOOD, tip, 1)

        # Pulsing red ring shows the damage radius when about to strike
        if pulse > 0.7:
            r = int(t.range * 0.5)
            ring = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            alpha = int((pulse - 0.7) * 220)
            pygame.draw.circle(ring, (255, 80, 80, alpha),
                               (r + 2, r + 2), r, 2)
            s.blit(ring, (cx - r - 2, cy - r - 2))

    def _draw_barricade(self, s, cx, cy, t):
        """Iron-banded barricade."""
        # Outer iron casing
        pygame.draw.rect(s, C.BARRICADE_BAND, (cx - 19, cy - 18, 38, 36), border_radius=3)
        # Inner steel
        pygame.draw.rect(s, C.BARRICADE_STEEL, (cx - 16, cy - 15, 32, 30), border_radius=2)
        # Vertical reinforcement bands
        for bx in (cx - 8, cx + 4):
            pygame.draw.rect(s, C.BARRICADE_BAND, (bx, cy - 15, 4, 30))
            pygame.draw.line(s, C.BARRICADE_LIGHT, (bx + 1, cy - 14), (bx + 1, cy + 14), 1)
        # Horizontal cross-beam
        pygame.draw.rect(s, C.BARRICADE_BAND, (cx - 16, cy - 2, 32, 5))
        pygame.draw.line(s, C.BARRICADE_LIGHT, (cx - 15, cy - 1), (cx + 15, cy - 1), 1)
        # Corner rivets
        for rx, ry in [(cx - 14, cy - 13), (cx + 13, cy - 13),
                       (cx - 14, cy + 12), (cx + 13, cy + 12)]:
            pygame.draw.circle(s, C.BARRICADE_RIVET, (rx, ry), 2)
            pygame.draw.circle(s, C.BARRICADE_BAND,  (rx, ry), 2, 1)

    # ══════════════════════════════════════════════════════════════════════
    # Enemies
    # ══════════════════════════════════════════════════════════════════════

    def _draw_enemies(self, enemies) -> None:
        for e in enemies:
            if not e.dead:
                self._draw_single_enemy(e)

    def _draw_single_enemy(self, e: Enemy) -> None:
        """Blit the enemy's animated sprite, plus shadow / status effects / HP bar."""
        s  = self.screen
        cx = int(e.x)
        cy = int(e.y)
        r  = e.size
        et = e.enemy_type

        # Shadow
        pygame.draw.ellipse(s, (10, 30, 10), (cx - r, cy + r - 4, r * 2, 8))

        # Bosses use their own sprite/state pipeline
        if getattr(e, "boss_id", None):
            self._draw_boss(e)
            return

        # Sprite — pick the current animation frame.  Anim_t is offset per
        # enemy so a swarm doesn't pulse in lockstep.
        anim_t = self._time + (id(e) % 1000) * 0.001
        sprite = Assets.enemy_frame(et, anim_t)
        if sprite is not None:
            sw, sh = sprite.get_size()
            s.blit(sprite, (cx - sw // 2, cy - sh // 2))
        else:
            # Fallback: simple coloured circle
            pygame.draw.circle(s, e.color, (cx, cy), r)
            pygame.draw.circle(s, e.accent, (cx, cy), r, 2)

        # Status effects (painted as glow rings)
        if e.slow_timer > 0:
            pygame.draw.circle(s, (150, 210, 255), (cx, cy), r + 4, 2)
        if e.burn_timer > 0:
            pygame.draw.circle(s, (255, 140, 0), (cx, cy), r + 4, 2)

        # HP bar
        self._draw_hp_bar(s, cx, cy - r - 10, r * 2 + 8, 5, e.hp, e.max_hp)

    def _draw_goblin(self, s, cx, cy, r, e):
        # Body
        pygame.draw.circle(s, e.color,  (cx, cy), r)
        pygame.draw.circle(s, e.accent, (cx, cy), r, 2)
        # Eyes
        pygame.draw.circle(s, (255, 50, 50), (cx - 4, cy - 4), 3)
        pygame.draw.circle(s, (255, 50, 50), (cx + 4, cy - 4), 3)
        pygame.draw.circle(s, C.BLACK, (cx - 4, cy - 4), 1)
        pygame.draw.circle(s, C.BLACK, (cx + 4, cy - 4), 1)
        # Ears
        pygame.draw.polygon(s, e.color, [(cx - r, cy - 4), (cx - r - 8, cy - 10),
                                          (cx - r + 2, cy + 2)])
        pygame.draw.polygon(s, e.color, [(cx + r, cy - 4), (cx + r + 8, cy - 10),
                                          (cx + r - 2, cy + 2)])

    def _draw_skeleton(self, s, cx, cy, r, e):
        # Skull
        pygame.draw.circle(s, e.color, (cx, cy - 4), r - 2)
        # Eye sockets
        pygame.draw.circle(s, (30, 30, 30), (cx - 4, cy - 6), 3)
        pygame.draw.circle(s, (30, 30, 30), (cx + 4, cy - 6), 3)
        # Ribcage suggestion
        for ri in range(3):
            ry = cy + ri * 5
            pygame.draw.arc(s, e.accent, (cx - r + 2, ry, (r - 2) * 2, 8),
                            0, math.pi, 2)
        # Jaw
        pygame.draw.rect(s, e.color, (cx - 5, cy + 2, 10, 5))
        for tx in range(cx - 4, cx + 5, 3):
            pygame.draw.rect(s, (30, 30, 30), (tx, cy + 2, 2, 5))

    def _draw_orc(self, s, cx, cy, r, e):
        # Body
        pygame.draw.circle(s, e.color,  (cx, cy), r)
        pygame.draw.circle(s, e.accent, (cx, cy), r, 3)
        # Eyes (angry)
        pygame.draw.circle(s, (220, 180, 0), (cx - 5, cy - 5), 4)
        pygame.draw.circle(s, (220, 180, 0), (cx + 5, cy - 5), 4)
        pygame.draw.circle(s, C.BLACK, (cx - 4, cy - 5), 2)
        pygame.draw.circle(s, C.BLACK, (cx + 5, cy - 5), 2)
        # Tusks
        pygame.draw.line(s, (230, 220, 200), (cx - 6, cy + 4), (cx - 10, cy + 12), 3)
        pygame.draw.line(s, (230, 220, 200), (cx + 6, cy + 4), (cx + 10, cy + 12), 3)
        # Horns
        pygame.draw.polygon(s, (50, 40, 30),
                            [(cx - r + 2, cy - r + 4), (cx - r - 4, cy - r - 8),
                             (cx - r + 8, cy - r)])
        pygame.draw.polygon(s, (50, 40, 30),
                            [(cx + r - 2, cy - r + 4), (cx + r + 4, cy - r - 8),
                             (cx + r - 8, cy - r)])

    def _draw_troll(self, s, cx, cy, r, e):
        # Massive body
        pygame.draw.ellipse(s, e.color,  (cx - r, cy - r + 4, r * 2, r * 2 - 6))
        pygame.draw.ellipse(s, e.accent, (cx - r, cy - r + 4, r * 2, r * 2 - 6), 3)
        # Head
        pygame.draw.circle(s, e.color, (cx, cy - r + 4), r - 6)
        # Tiny eyes
        pygame.draw.circle(s, (180, 40, 0), (cx - 5, cy - r + 2), 4)
        pygame.draw.circle(s, (180, 40, 0), (cx + 5, cy - r + 2), 4)
        # Club
        pygame.draw.line(s, (100, 70, 40),
                         (cx + r - 4, cy - 4), (cx + r + 12, cy - 20), 5)
        pygame.draw.circle(s, (80, 55, 30), (cx + r + 12, cy - 20), 8)

    # ══════════════════════════════════════════════════════════════════════
    # Projectiles
    # ══════════════════════════════════════════════════════════════════════

    def _draw_projectiles(self, projectiles) -> None:
        """Blit each projectile sprite (oriented towards its target) at its position."""
        s = self.screen
        for p in projectiles:
            if p.dead:
                continue
            sprite = Assets.projectile(p.proj_type)
            px, py = int(p.x), int(p.y)
            if sprite is None:
                # Fallback dot
                pygame.draw.circle(s, (220, 200, 120), (px, py), 4)
                continue
            # Rotate sprite to face the target so arrows look right
            if getattr(p, "target", None) is not None and not p.target.dead:
                angle = math.degrees(
                    math.atan2(-(p.target.y - p.y), p.target.x - p.x)
                ) - 90.0
                rotated = pygame.transform.rotate(sprite, angle)
            else:
                rotated = sprite
            rw, rh = rotated.get_size()
            s.blit(rotated, (px - rw // 2, py - rh // 2))

    # ══════════════════════════════════════════════════════════════════════
    # Hero
    # ══════════════════════════════════════════════════════════════════════

    def _draw_hero(self, hero: Hero) -> None:
        """Render the hero from sprite assets, picking the right animation state.

        State machine (priority high→low):
            DIE     — hero.alive is False
            HURT    — hero just took damage (hp dropped this frame)
            ATTACK  — hero just attacked (attack-cooldown reset spike)
            WALK    — hero moved this frame
            IDLE    — otherwise
        """
        s  = self.screen
        cx = int(hero.x)
        cy = int(hero.y)

        # ── Update animation state from physical change ───────────────────
        dx = hero.x - self._hero_last_x
        dy = hero.y - self._hero_last_y
        moving = (dx * dx + dy * dy) > 0.5

        if abs(dx) > 0.15:
            self._hero_facing_left = dx < 0

        # While blocking the hero is frozen in place — derive facing from the
        # cursor so the player still gets visual feedback when aiming.  We
        # also record the start time so the Take Hit sheet plays once and
        # holds on the final frame instead of looping.
        if getattr(hero, "block_active", False):
            mx, _my = pygame.mouse.get_pos()
            self._hero_facing_left = (mx < cx)
            if getattr(self, "_hero_block_started_at", None) is None:
                self._hero_block_started_at = self._time
        else:
            self._hero_block_started_at = None

        # Detect attack pulse — Hero._attack_cd is reset to (1/HERO_ATTACK_RATE)
        # whenever the hero swings; spotting that spike lets us trigger ATTACK.
        cur_cd = float(getattr(hero, "_attack_cd", 0.0))
        if cur_cd > self._hero_last_attack_cd + 0.1:
            self._hero_attack_until = self._time + 0.55
        self._hero_last_attack_cd = cur_cd

        # Detect HP drop → trigger HURT for ~0.4s
        if hero.hp < self._hero_last_hp - 0.01:
            self._hero_hurt_until = self._time + 0.4
        self._hero_last_hp = float(hero.hp)

        # Resolve current animation state.  Note: HURT (Take Hit) is
        # intentionally skipped per design — Attack2 charge / release uses
        # the dedicated ATTACK2 sheet, and sprinting uses RUN at higher fps.
        anim_fps = 10.0
        if not hero.alive:
            state = "DEATH"
        elif getattr(hero, "block_active", False):
            state = "TAKE_HIT"
            anim_fps = 8.0
        elif (getattr(hero, "attack2_charging", False)
              or getattr(hero, "attack2_anim_t", 0.0) > 0.0):
            state = "ATTACK2"
            anim_fps = 12.0
        elif self._time < self._hero_attack_until:
            state = "ATTACK1"
            anim_fps = 14.0
        elif moving:
            state = "RUN"
            # Sprinting plays the run cycle faster
            anim_fps = 14.0 if getattr(hero, "sprinting", False) else 9.0
        else:
            state = "IDLE"
            anim_fps = 8.0

        # ── Render ─────────────────────────────────────────────────────────
        # Attack-range aura (only while alive and idle/active)
        if hero.alive:
            r = C.HERO_ATTACK_RANGE
            aura = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(aura, (255, 255, 100, 18), (r + 2, r + 2), r)
            pygame.draw.circle(aura, (255, 255, 100, 55), (r + 2, r + 2), r, 2)
            s.blit(aura, (cx - r - 2, cy - r - 2))

        # Shadow under feet
        pygame.draw.ellipse(s, (10, 30, 10), (cx - 14, cy + 18, 28, 8))

        # Sprite frame — anim_t offset per-state so transitions don't snap
        # Attack2 has special framing: pin the wind-up while charging, then
        # play the swing portion (frames 3..6) over the post-release window.
        sprite = None
        if state == "TAKE_HIT":
            # Play the 4-frame sheet once, then hold on the final frame for
            # as long as the player keeps E held.  Frame count is auto-
            # detected from the sheet width (Take Hit.png is 720×180 → 4
            # frames), but we resolve it dynamically so the cap survives
            # any sprite-sheet swap later.
            from src.assets import Assets as _A
            _A.init()
            bank = (_A._hero_frames_flipped if self._hero_facing_left
                    else _A._hero_frames)
            n_frames = max(1, len(bank.get("TAKE_HIT") or [None]))
            start    = float(self._hero_block_started_at or self._time)
            elapsed  = max(0.0, self._time - start)
            idx      = min(n_frames - 1, int(elapsed * anim_fps))
            sprite = Assets.hero_frame_at(
                "TAKE_HIT", idx, self._hero_facing_left,
            )
        elif state == "ATTACK2":
            if getattr(hero, "attack2_charging", False):
                sprite = Assets.hero_frame_at(
                    "ATTACK2", 2, self._hero_facing_left,
                )
            else:
                # Post-release swing: read the countdown timer maintained by
                # Hero.update — clock-source independent.  At t = window the
                # swing has just started (frame 3); at t = 0 the swing ends
                # (frame 6) and the state machine falls back to IDLE/RUN.
                remaining = float(getattr(hero, "attack2_anim_t", 0.0))
                window    = float(getattr(hero, "attack2_anim_window",
                                          C.HERO_ATK2_SWING_WINDOW))
                if window > 0.0:
                    progress = max(0.0, min(1.0, 1.0 - remaining / window))
                else:
                    progress = 1.0
                idx = 3 + int(progress * 4)   # frames 3..6
                sprite = Assets.hero_frame_at(
                    "ATTACK2", idx, self._hero_facing_left,
                )
        if sprite is None:
            sprite = Assets.hero_frame(state, self._time,
                                       self._hero_facing_left, fps=anim_fps)
        if sprite is not None:
            sw, sh = sprite.get_size()
            # Sprite frames have ~70 % transparent padding around the actual
            # character, so a naive "feet at cy" anchor pushes the visible
            # body way above the hitbox aura.  We centre the *body* of the
            # sprite on (cx, cy) instead — the body sits roughly at frame
            # row 88/180, so a frame centre offset is close enough.
            sx = cx - sw // 2
            sy = cy - sh // 2
            s.blit(sprite, (sx, sy))
        else:
            # Fallback: simple golden circle if sprites failed to load
            pygame.draw.circle(s, (220, 180, 40), (cx, cy), 10)

        # HP bar (only while alive — die animation handles its own visual)
        if hero.alive:
            self._draw_hp_bar(s, cx, cy - 42, 48, 5, hero.hp, hero.max_hp)

        # Label
        if not hasattr(self, "_font_sm"):
            self._font_sm = pygame.font.SysFont("consolas", 13, bold=True)
        lbl = self._font_sm.render("Hero", True, (255, 220, 120))
        s.blit(lbl, (cx - lbl.get_width() // 2, cy - 56))

        # Cache position for next frame's motion detection
        self._hero_last_x = float(hero.x)
        self._hero_last_y = float(hero.y)

        # Attack2 cooldown badge / charge ring (shown on the hero)
        self._draw_attack2_badge(hero, cx, cy)
        # Block (E) badge — sits on the opposite side so the two never overlap
        self._draw_block_badge(hero, cx, cy)

    def _draw_attack2_badge(self, hero, cx: int, cy: int) -> None:
        """Small disc + sweep arc near the hero showing Attack2 cooldown.

        While charging, the arc fills clockwise toward 100 % at the
        tier-2 hold threshold so the player can read how strong the
        release will be.  When the cooldown is ticking the same arc
        fills back up as the ability becomes available again.
        """
        import math as _math
        s = self.screen

        cd = float(getattr(hero, "attack2_cd", 0.0))
        charging = bool(getattr(hero, "attack2_charging", False))
        if cd <= 0.0 and not charging:
            return

        bx = cx + 30
        by = cy + 30
        radius = 14
        # Background disc
        bg = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(bg, (0, 0, 0, 160),
                           (radius + 2, radius + 2), radius + 2)
        s.blit(bg, (bx - radius - 2, by - radius - 2))
        pygame.draw.circle(s, (40, 40, 60), (bx, by), radius)
        pygame.draw.circle(s, (200, 200, 240), (bx, by), radius, 2)

        if charging:
            # Fill ratio = how close to tier2 hold the player is
            held  = float(getattr(hero, "attack2_charge_t", 0.0))
            ratio = max(0.0, min(1.0, held / max(0.001, C.HERO_ATK2_HOLD_TIER2_S)))
            # Three colour tiers so the player can read at a glance which
            # damage band they're in:
            #   tier 1 ( < HOLD_TIER1_S )      → yellow
            #   tier 2 ( HOLD_TIER1..TIER2_S ) → orange
            #   tier 3 ( ≥ HOLD_TIER2_S )      → red
            if held >= C.HERO_ATK2_HOLD_TIER2_S:
                ring_col = (235, 60, 60)
            elif held >= C.HERO_ATK2_HOLD_TIER1_S:
                ring_col = (245, 150, 40)
            else:
                ring_col = (255, 220, 80)
        else:
            # Cooldown ticking → ratio of remaining time, scaled by the
            # variable cooldown actually applied for the latest cast.
            cd_max = max(0.001, getattr(hero, "attack2_cd_max",
                                        C.HERO_ATK2_COOLDOWN_MAX))
            ratio = max(0.0, min(1.0, 1.0 - cd / cd_max))
            ring_col = (140, 200, 255)

        # While charging, mark the tier boundaries on the ring so the
        # player can see exactly when they cross from yellow → orange and
        # orange → red.
        if charging:
            tier1_r = C.HERO_ATK2_HOLD_TIER1_S / max(0.001, C.HERO_ATK2_HOLD_TIER2_S)
            for boundary, mark_col in (
                (tier1_r, (245, 150, 40)),
                (1.0,     (235,  60, 60)),
            ):
                ang = -_math.pi / 2.0 + boundary * 2.0 * _math.pi
                x1 = bx + int(_math.cos(ang) * (radius - 3))
                y1 = by + int(_math.sin(ang) * (radius - 3))
                x2 = bx + int(_math.cos(ang) * (radius + 3))
                y2 = by + int(_math.sin(ang) * (radius + 3))
                pygame.draw.line(s, mark_col, (x1, y1), (x2, y2), 2)

        # Sweep arc from -90° clockwise
        if ratio > 0.0:
            start = -_math.pi / 2.0
            end   = start + ratio * 2.0 * _math.pi
            pygame.draw.arc(s, ring_col,
                            (bx - radius, by - radius, radius * 2, radius * 2),
                            start, end, 4)

        # Lightning glyph in the centre
        if not hasattr(self, "_font_xs"):
            self._font_xs = pygame.font.SysFont("consolas", 11, bold=True)
        glyph = self._font_xs.render("R", True, (240, 240, 255))
        s.blit(glyph, (bx - glyph.get_width() // 2,
                       by - glyph.get_height() // 2))

    def _draw_block_badge(self, hero, cx: int, cy: int) -> None:
        """Block (E) status badge on the hero's left.

        While the guard is up, the ring fills as the absorption-break
        counter climbs toward HERO_BLOCK_RAW_BREAK and shifts from
        shield-blue to red.  During cooldown the same ring fills back up
        in blue as the ability becomes available again.
        """
        import math as _math
        s = self.screen

        active = bool(getattr(hero, "block_active", False))
        cd     = float(getattr(hero, "block_cd", 0.0))
        if not active and cd <= 0.0:
            return

        bx = cx - 30
        by = cy + 30
        radius = 14
        # Background disc
        bg = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(bg, (0, 0, 0, 160),
                           (radius + 2, radius + 2), radius + 2)
        s.blit(bg, (bx - radius - 2, by - radius - 2))
        pygame.draw.circle(s, (40, 40, 60), (bx, by), radius)
        pygame.draw.circle(s, (200, 220, 240), (bx, by), radius, 2)

        if active:
            taken = float(getattr(hero, "block_dmg_taken", 0.0))
            ratio = max(0.0, min(1.0, taken / max(0.001, C.HERO_BLOCK_RAW_BREAK)))
            # Shield-blue when fresh, red-tinted near the break threshold so
            # the player feels the guard about to shatter.
            if ratio >= 0.75:
                ring_col = (235,  60,  60)
            elif ratio >= 0.45:
                ring_col = (245, 150,  40)
            else:
                ring_col = ( 80, 200, 255)
        else:
            cd_max = max(0.001, getattr(hero, "block_cd_max",
                                        C.HERO_BLOCK_COOLDOWN_MAX))
            ratio = max(0.0, min(1.0, 1.0 - cd / cd_max))
            ring_col = (80, 200, 255)

        if ratio > 0.0:
            start = -_math.pi / 2.0
            end   = start + ratio * 2.0 * _math.pi
            pygame.draw.arc(s, ring_col,
                            (bx - radius, by - radius, radius * 2, radius * 2),
                            start, end, 4)

        if not hasattr(self, "_font_xs"):
            self._font_xs = pygame.font.SysFont("consolas", 11, bold=True)
        glyph = self._font_xs.render("E", True, (240, 240, 255))
        s.blit(glyph, (bx - glyph.get_width() // 2,
                       by - glyph.get_height() // 2))

    def _draw_attack2_charge_cone(self, hero, mouse_pos) -> None:
        """Translucent fan showing the cone of effect while Attack2 is charging.

        Centre = hero pixel pos.  Half-angle matches the existing
        `dot >= 0.2` cone used by `Game._release_hero_charge`, so what the
        player sees is exactly what will be hit on release.  Direction
        tracks `mouse_pos` live so adjusting the cursor rotates the fan.
        """
        import math as _math
        import pygame as _pg

        s = self.screen
        cx = float(hero.x)
        cy = float(hero.y)
        mx, my = mouse_pos
        dx = float(mx) - cx
        dy = float(my) - cy
        if dx * dx + dy * dy < 1.0:
            theta_aim = 0.0
        else:
            theta_aim = _math.atan2(dy, dx)

        radius = float(C.HERO_ATK2_RANGE)
        # Match the gameplay cone exactly — half-angle = acos(HERO_ATK2_CONE_DOT)
        half_angle = _math.acos(C.HERO_ATK2_CONE_DOT)
        steps = 24

        # Generate sector polygon
        pts: list[tuple[int, int]] = [(int(cx), int(cy))]
        for i in range(steps + 1):
            t = i / steps
            ang = theta_aim - half_angle + t * (2.0 * half_angle)
            pts.append((int(cx + _math.cos(ang) * radius),
                        int(cy + _math.sin(ang) * radius)))

        # Render to a transparent overlay so we can use alpha
        bbox_pad = 4
        ox = min(p[0] for p in pts) - bbox_pad
        oy = min(p[1] for p in pts) - bbox_pad
        ow = max(p[0] for p in pts) - ox + bbox_pad * 2
        oh = max(p[1] for p in pts) - oy + bbox_pad * 2
        if ow <= 0 or oh <= 0:
            return
        layer = _pg.Surface((ow, oh), _pg.SRCALPHA)
        local = [(p[0] - ox, p[1] - oy) for p in pts]
        _pg.draw.polygon(layer, (110, 200, 255, 60), local)
        _pg.draw.polygon(layer, (160, 220, 255, 140), local, 2)
        s.blit(layer, (ox, oy))

    # ══════════════════════════════════════════════════════════════════════
    # Grid overlay
    # ══════════════════════════════════════════════════════════════════════

    def _draw_grid_overlay(
        self,
        grid: list[list[str]],
        selected_type: str,
        hovered_cell: tuple[int, int] | None,
    ) -> None:
        if not selected_type:
            return
        s    = self.screen
        surf = self._overlay_surf
        surf.fill((0, 0, 0, 0))

        # Per user request: do NOT highlight invalid cells in red.  Only the
        # subtle green tint on placeable cells + a thin grid line everywhere.
        COLOR_EMPTY = (80, 255, 80, 28)
        placeable   = ("EMPTY", "PATH")  # PvZ-style: towers placeable in lanes

        for row in range(C.GRID_ROWS):
            for col in range(C.GRID_COLS):
                cell = grid[row][col]
                rx = col * C.CELL_SIZE
                ry = row * C.CELL_SIZE
                if cell in placeable:
                    pygame.draw.rect(surf, COLOR_EMPTY,
                                     (rx, ry, C.CELL_SIZE, C.CELL_SIZE))
                # Always draw a faint grid line so the lattice is visible
                pygame.draw.rect(surf, (0, 0, 0, 25),
                                 (rx, ry, C.CELL_SIZE, C.CELL_SIZE), 1)

        # Hover highlight — only draw it for placeable cells.  Invalid hovers
        # silently do nothing instead of flashing red.
        if hovered_cell:
            col, row = hovered_cell
            if 0 <= row < C.GRID_ROWS and 0 <= col < C.GRID_COLS:
                cell = grid[row][col]
                if cell in placeable:
                    rx = col * C.CELL_SIZE
                    ry = row * C.CELL_SIZE
                    pygame.draw.rect(surf, (80, 255, 80, 90),
                                     (rx, ry, C.CELL_SIZE, C.CELL_SIZE))
                    pygame.draw.rect(surf, (80, 255, 80, 200),
                                     (rx, ry, C.CELL_SIZE, C.CELL_SIZE), 2)

        s.blit(surf, (0, 0))

    # ══════════════════════════════════════════════════════════════════════
    # Night vignette
    # ══════════════════════════════════════════════════════════════════════

    def _draw_night_vignette(self) -> None:
        s = self.screen
        surf = pygame.Surface((C.GAME_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        # Dark edges
        for i in range(30):
            alpha = int(i * 2)
            pygame.draw.rect(surf, (0, 0, 20, alpha),
                             (i, i, C.GAME_WIDTH - i * 2, C.SCREEN_HEIGHT - i * 2), 1)
        s.blit(surf, (0, 0))

    # ══════════════════════════════════════════════════════════════════════
    # Helper: HP bar
    # ══════════════════════════════════════════════════════════════════════

    def _draw_hp_bar(
        self, s, cx, top, width, height, hp, max_hp
    ) -> None:
        if max_hp <= 0:
            return
        ratio = max(0.0, hp / max_hp)
        x = cx - width // 2
        pygame.draw.rect(s, C.HP_BG, (x, top, width, height), border_radius=2)
        if ratio > 0:
            bar_color = (
                C.HP_GREEN  if ratio > 0.6 else
                C.HP_YELLOW if ratio > 0.3 else
                C.HP_RED
            )
            pygame.draw.rect(s, bar_color,
                             (x, top, int(width * ratio), height), border_radius=2)
        pygame.draw.rect(s, (0, 0, 0), (x, top, width, height), 1, border_radius=2)

    # ══════════════════════════════════════════════════════════════════════
    # Boss
    # ══════════════════════════════════════════════════════════════════════

    def _draw_boss(self, boss) -> None:
        """Render a boss using its current animation state.

        State machine (driven by observable behaviour):
            target_tower set       → use first available "Attack" state
            reached_end (at castle) → "Attack" state
            dead                    → "Death" / "Get hit" fallback
            otherwise               → "Move" / "Run" / "Walk" / "Idle" fallback
        """
        s  = self.screen
        cx = int(boss.x)
        cy = int(boss.y)
        boss_id = boss.boss_id
        defn    = C.BOSS_DEFS[boss_id]

        # Choose animation state.  Boss is "in attack" when:
        #   • frozen at the castle (reached_end)
        #   • chewing through a blocking tower (target_tower set)
        #   • locked onto the hero (Boss._engaging_hero set by Boss.update)
        if boss.dead:
            state = "Death"
        elif (boss.reached_end
              or boss.target_tower is not None
              or getattr(boss, "_engaging_hero", False)):
            atk_states = defn.get("atk_states", ["Attack"])
            state = atk_states[int(self._time * 0.8) % len(atk_states)]
        else:
            # Pick the first available locomotion frame for this boss
            state = "Move"
            if not Assets.boss_frame_count(boss_id, state):
                state = "Run"
            if not Assets.boss_frame_count(boss_id, state):
                state = "Walk"
            if not Assets.boss_frame_count(boss_id, state):
                state = "Idle"

        # Face the direction the boss is moving along the lane
        facing_left = False
        if boss._wp_index < len(boss.waypoints):
            tx, _ = boss.waypoints[boss._wp_index]
            facing_left = (tx < boss.x)

        anim_t = self._time + (id(boss) % 1000) * 0.001
        sprite = Assets.boss_frame(boss_id, state, anim_t, facing_left)
        if sprite is not None:
            sw, sh = sprite.get_size()
            s.blit(sprite, (cx - sw // 2, cy - sh // 2))
        else:
            # Fallback: large red circle
            pygame.draw.circle(s, (220, 60, 60), (cx, cy), boss.size)

        # Boss name banner above the HP bar
        if not hasattr(self, "_font_md"):
            self._font_md = pygame.font.SysFont("consolas", 16, bold=True)
        name_lbl = self._font_md.render(defn["name"], True, (255, 200, 200))
        s.blit(name_lbl,
               (cx - name_lbl.get_width() // 2, cy - boss.size - 50))

        # Wide HP bar so the player can read boss health at a glance.
        bar_w = max(120, int(boss.size * 2.8))
        bar_h = 8
        bar_x = cx - bar_w // 2
        bar_y = cy - boss.size - 30
        ratio = max(0.0, boss.hp / max(1.0, float(boss.max_hp)))
        # Frame
        pygame.draw.rect(s, (20, 5, 5),
                         (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4),
                         border_radius=3)
        pygame.draw.rect(s, (60, 10, 10),
                         (bar_x, bar_y, bar_w, bar_h),
                         border_radius=2)
        # Fill — colour shifts from green → yellow → red as HP drains
        if ratio > 0.6:
            fill_col = (80, 220, 80)
        elif ratio > 0.3:
            fill_col = (240, 200, 60)
        else:
            fill_col = (230, 70, 70)
        if ratio > 0:
            pygame.draw.rect(s, fill_col,
                             (bar_x, bar_y, int(bar_w * ratio), bar_h),
                             border_radius=2)
        pygame.draw.rect(s, (200, 50, 50),
                         (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)
        # Numeric readout (e.g. "1500 / 1500")
        if not hasattr(self, "_font_xs"):
            self._font_xs = pygame.font.SysFont("consolas", 11, bold=True)
        hp_lbl = self._font_xs.render(
            f"{int(boss.hp)} / {int(boss.max_hp)}", True, (255, 240, 240),
        )
        s.blit(hp_lbl, (cx - hp_lbl.get_width() // 2, bar_y + bar_h + 1))

    # ══════════════════════════════════════════════════════════════════════
    # Boss VFX (ranged-cast explosions)
    # ══════════════════════════════════════════════════════════════════════

    def _draw_boss_vfx(self, vfx_list) -> None:
        """Render every active explosion at its remembered (x, y) location."""
        if not vfx_list:
            return
        s = self.screen
        n_frames = max(1, Assets.evil3_explode_frame_count())
        EXPLODE_DURATION = 0.65
        for fx in vfx_list:
            ratio = max(0.0, min(0.999, fx["t"] / EXPLODE_DURATION))
            idx   = int(ratio * n_frames)
            frame = Assets.evil3_explode_frame(idx)
            if frame is None:
                continue
            fw, fh = frame.get_size()
            s.blit(frame, (int(fx["x"]) - fw // 2, int(fx["y"]) - fh // 2))

    # ══════════════════════════════════════════════════════════════════════
    # Farm scene
    # ══════════════════════════════════════════════════════════════════════

    def _draw_farm_terrain(self) -> None:
        """Draw the farm map: same grass background + a tilled-soil rectangle."""
        s = self.screen

        # Reuse the grass tiling (same as main map)
        if not hasattr(self, "_grass_pattern"):
            import random as _r
            rng = _r.Random(1337)
            self._grass_pattern = [
                [rng.randint(1, 2) for _ in range(C.GRID_COLS)]
                for _ in range(C.GRID_ROWS)
            ]
        tile_a = Assets.grass_tile(1)
        tile_b = Assets.grass_tile(2)
        cell = C.CELL_SIZE
        if tile_a is not None and tile_b is not None:
            if tile_a.get_width() != cell:
                tile_a = pygame.transform.scale(tile_a, (cell, cell))
            if tile_b.get_width() != cell:
                tile_b = pygame.transform.scale(tile_b, (cell, cell))
            for row in range(C.GRID_ROWS):
                for col in range(C.GRID_COLS):
                    tile = tile_a if self._grass_pattern[row][col] == 1 else tile_b
                    s.blit(tile, (col * cell, row * cell))

        # Tilled-soil block where plants live
        c0, r0, w, h = C.FARM_PLOT_RECT
        soil_rect = pygame.Rect(c0 * cell, r0 * cell, w * cell, h * cell)
        pygame.draw.rect(s, (110, 75, 45), soil_rect)
        # Plot grid lines
        for col in range(c0, c0 + w + 1):
            x = col * cell
            pygame.draw.line(s, (80, 50, 30),
                             (x, r0 * cell), (x, (r0 + h) * cell), 1)
        for row in range(r0, r0 + h + 1):
            y = row * cell
            pygame.draw.line(s, (80, 50, 30),
                             (c0 * cell, y), ((c0 + w) * cell, y), 1)

        # Scatter trees / rocks / mushrooms around the soil for atmosphere.
        self._draw_farm_decorations()

        # Friendly farm sign in the corner
        if not hasattr(self, "_font_med"):
            self._font_med = pygame.font.SysFont("consolas", 18, bold=True)
        title = self._font_med.render("FARM", True, (180, 230, 120))
        s.blit(title, (cell + 8, 12))

    def _draw_farm_decorations(self) -> None:
        """Sparse hand-placed trees / rocks / mushrooms around the soil plot.

        Matches the main-map style (fixed spots, same sprite helpers and
        scale) instead of a dense procedurally-scattered ring.  Spots are
        chosen to sit in the grass strips around the soil and to clear the
        back-portal door on the left edge.
        """
        # Trees — (foot_x, foot_y, tree_idx).  Sprite is anchored so its
        # base sits at (cx, cy), same as main-map _draw_tree.  Soil plot
        # occupies roughly x=144..816, y=192..576; portal door covers
        # x=4..44, y=312..408.
        tree_spots = [
            ( 70, 175, 0), (210, 150, 2), (560, 140, 1),
            (705, 175, 3), (905, 180, 0),
            (920, 540, 4), ( 65, 240, 1),
            (110, 670, 2), (270, 710, 3), (480, 715, 0),
            (690, 705, 4), (905, 695, 1),
        ]
        for tx, ty, idx in tree_spots:
            self._draw_tree(tx, ty, idx)

        # Rocks — (cx, cy, idx); blit centred on (cx, cy).
        rock_spots = [
            (110, 470, 0), (845, 240, 2),
            (400,  90, 1), (590, 660, 0),
            ( 50, 590, 1),
        ]
        for rx, ry, idx in rock_spots:
            rock = Assets.rock(idx)
            if rock is None:
                continue
            rw, rh = rock.get_size()
            self.screen.blit(rock, (rx - rw // 2, ry - rh // 2))

        # Mushrooms — a few small accents to break up the grass.
        mush_spots = [
            (300, 115, 0), (760, 115, 1), (360, 695, 0),
        ]
        for mx, my, idx in mush_spots:
            mush = Assets.mushroom(idx)
            if mush is None:
                continue
            mw, mh = mush.get_size()
            self.screen.blit(mush, (mx - mw // 2, my - mh // 2))

    def _draw_farm_portal_back(self) -> None:
        """Draw the portal that returns the hero to the main map."""
        s = self.screen
        x, y, w, h = C.FARM_PORTAL_RECT_FARM
        # Wooden door frame
        pygame.draw.rect(s, (90, 60, 30), (x, y, w, h), border_radius=4)
        pygame.draw.rect(s, (40, 25, 12), (x, y, w, h), 3, border_radius=4)
        # Diagonal planks
        pygame.draw.line(s, (60, 40, 20), (x + 4, y + 6),
                         (x + w - 4, y + h - 6), 2)
        pygame.draw.line(s, (60, 40, 20), (x + 4, y + h - 6),
                         (x + w - 4, y + 6), 2)
        # Pulse
        pulse = int(80 + 60 * abs(math.sin(self._time * 2)))
        glow = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
        pygame.draw.rect(glow, (180, 220, 255, pulse),
                         glow.get_rect(), border_radius=10)
        s.blit(glow, (x - 6, y - 6))

        if not hasattr(self, "_font_xs"):
            self._font_xs = pygame.font.SysFont("consolas", 11, bold=True)
        lbl = self._font_xs.render("← Back", True, (220, 240, 255))
        s.blit(lbl, (x, y + h + 4))

    def _draw_farm_portal_main(self) -> None:
        """Draw the portal that leads from main map → farm (behind castle)."""
        s = self.screen
        x, y, w, h = C.FARM_PORTAL_RECT_MAIN
        # Stone arch
        pygame.draw.rect(s, (90, 90, 100), (x, y, w, h), border_radius=4)
        pygame.draw.rect(s, (40, 40, 50), (x, y, w, h), 3, border_radius=4)
        # Mossy interior
        pygame.draw.rect(s, (40, 70, 40), (x + 4, y + 4, w - 8, h - 8))
        # Pulse glow
        pulse = int(60 + 50 * abs(math.sin(self._time * 2)))
        glow = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
        pygame.draw.rect(glow, (180, 240, 160, pulse),
                         glow.get_rect(), border_radius=10)
        s.blit(glow, (x - 8, y - 8))

        if not hasattr(self, "_font_xs"):
            self._font_xs = pygame.font.SysFont("consolas", 11, bold=True)
        lbl = self._font_xs.render("FARM", True, (200, 240, 180))
        s.blit(lbl, (x + (w - lbl.get_width()) // 2, y - 14))

    def _draw_farm_plants(self, farm) -> None:
        """Render every plant on the farm with its current growth-stage sprite."""
        s = self.screen
        cell = C.CELL_SIZE
        for plant in farm:
            sprite = Assets.plant_frame(plant.plant_type, plant.stage)
            cx = plant.col * cell + cell // 2
            cy = plant.row * cell + cell // 2 + 4
            if sprite is not None:
                sw, sh = sprite.get_size()
                s.blit(sprite, (cx - sw // 2, cy - sh + 4))
            else:
                pygame.draw.rect(s, (140, 200, 120),
                                 (plant.col * cell + 6, plant.row * cell + 6,
                                  cell - 12, cell - 12),
                                 border_radius=4)

            # Growth bar — mini progress on top of the cell
            if not plant.ripe:
                bar_x = plant.col * cell + 6
                bar_y = plant.row * cell + 4
                bar_w = cell - 12
                pygame.draw.rect(s, (40, 30, 15), (bar_x, bar_y, bar_w, 4))
                pygame.draw.rect(s, (140, 220, 90),
                                 (bar_x, bar_y, int(bar_w * plant.progress), 4))
            else:
                # Ripe glow
                pulse = int(120 + 80 * abs(math.sin(self._time * 4)))
                glow = pygame.Surface((cell, cell), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 230, 80, pulse),
                                   (cell // 2, cell // 2), cell // 2 - 4, 3)
                s.blit(glow, (plant.col * cell, plant.row * cell))

    def _draw_farm_plot_overlay(self, drag_state) -> None:
        """While dragging a plant, highlight valid plots green and occupied red."""
        if drag_state is None:
            return
        item_id = drag_state.get("item_id")
        if item_id not in C.PLANT_DEFS:
            return
        s = self.screen
        c0, r0, w, h = C.FARM_PLOT_RECT
        cell = C.CELL_SIZE
        surf = pygame.Surface((C.GAME_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        for col in range(c0, c0 + w):
            for row in range(r0, r0 + h):
                tint = (80, 220, 80, 50)
                pygame.draw.rect(surf, tint,
                                 (col * cell, row * cell, cell, cell))
                pygame.draw.rect(surf, (60, 200, 60, 110),
                                 (col * cell, row * cell, cell, cell), 1)
        s.blit(surf, (0, 0))
