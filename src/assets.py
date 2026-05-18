"""
src/assets.py
=============
Centralised sprite loader for the Tower Defense game.

The /assets folder ships pixel-art PNGs at native resolution (8-48 px wide).
This module loads them once, offers cached scaling and frame-slicing, and
exposes the canonical name → file mapping the renderer needs.

Usage:
    from src.assets import Assets
    Assets.init(screen)               # call once after pygame.display.set_mode
    surf = Assets.tower("BALLISTA")   # already scaled for the grid
    frame = Assets.enemy_frame("GOBLIN", anim_t)
"""

from __future__ import annotations
import os
import pygame
from typing import Optional

import config as C


# ── Project-relative asset root ───────────────────────────────────────────────
ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets")
)


# ── Logical name → file mapping ───────────────────────────────────────────────
# Combat towers — point each game tower type at the sprite that fits it best.
TOWER_FILES: dict[str, str] = {
    "BALLISTA":  "Towers/Combat Towers/spr_tower_crossbow.png",
    "CANNON":    "Towers/Combat Towers/spr_tower_cannon.png",
    "TESLA":     "Towers/Combat Towers/spr_tower_lightning_tower.png",
    "ICE":       "Towers/Combat Towers/spr_tower_ice_wizard.png",
    "FLAME":     "Towers/Combat Towers/spr_tower_poison_wizard.png",
    # Non-combat towers used for the defence-only structures
    "WALL":      "Towers/Non-Combat Towers/spr_normal_tower_01_blue.png",
    "FENCE":     "Towers/Non-Combat Towers/spr_normal_tower_02_green.png",
    "SPIKE":     "Towers/Non-Combat Towers/spr_normal_tower_01_red.png",
    "BARRICADE": "Towers/Non-Combat Towers/spr_normal_tower_02_red.png",
}

# Each projectile bullet style
PROJECTILE_FILES: dict[str, str] = {
    "ARROW":    "Towers/Combat Towers Projectiles/spr_tower_crossbow_projectile.png",
    "SHELL":    "Towers/Combat Towers Projectiles/spr_tower_cannon_projectile.png",
    "BOLT":     "Towers/Combat Towers Projectiles/spr_tower_lightning_tower_projectile.png",
    "SHARD":    "Towers/Combat Towers Projectiles/spr_tower_ice_wizard_projectile.png",
    "FIREBALL": "Towers/Combat Towers Projectiles/spr_tower_poison_wizard_projectile.png",
}

# Enemies — sprite-sheets are horizontal strips with N square-ish frames
# (file, num_frames).  Frame width is computed at load time as W / num_frames.
ENEMY_FILES: dict[str, tuple[str, int]] = {
    "GOBLIN":   ("Enemies/spr_goblin.png",        4),
    "SKELETON": ("Enemies/spr_skeleton.png",      4),
    "ORC":      ("Enemies/spr_demon.png",         4),
    "TROLL":    ("Enemies/spr_king_slime.png",    4),
}

CASTLE_FILE = "Towers/Castle/spr_castle_blue.png"
GROUND_TILE = "Environment/Tile Set/spr_tile_set_ground.png"
LAKE_FILE   = "Environment/Tile Set/lake.png"
SHOP_FILE   = "Shop/shop.png"

# Hero animations — single sheet per state under Hero/Sprites/.
# Each sheet is a horizontal strip of square 180×180 frames; frame count
# = sheet_width / 180.  TAKE_HIT drives the new active-block (E) pose.
HERO_ANIM_SHEETS: dict[str, str] = {
    "IDLE":     "Hero/Sprites/Idle.png",
    "RUN":      "Hero/Sprites/Run.png",
    "ATTACK1":  "Hero/Sprites/Attack1.png",
    "ATTACK2":  "Hero/Sprites/Attack2.png",
    "DEATH":    "Hero/Sprites/Death.png",
    "JUMP":     "Hero/Sprites/Jump.png",
    "FALL":     "Hero/Sprites/Fall.png",
    "TAKE_HIT": "Hero/Sprites/Take Hit.png",
}
HERO_FRAME_PX      = 180
# Sprite frames have ~70 % transparent padding around the actual character,
# so we scale to a larger target than the visible body to compensate.
HERO_TARGET_HEIGHT = 260         # frame height after scaling (≈75 px char)
GRASS_TILES = [
    "Environment/Grass/spr_grass_01.png",
    "Environment/Grass/spr_grass_02.png",
    "Environment/Grass/spr_grass_03.png",
]
TREE_FILES  = [
    "Environment/Decoration/spr_tree_01_normal.png",
    "Environment/Decoration/spr_tree_02_normal.png",
    "Environment/Decoration/spr_tree_01_autumn.png",
    "Environment/Decoration/spr_tree_01_cherry_blossom.png",
    "Environment/Decoration/spr_tree_02_spruce.png",
]
ROCK_FILES  = [
    "Environment/Decoration/spr_rock_01.png",
    "Environment/Decoration/spr_rock_02.png",
    "Environment/Decoration/spr_rock_03.png",
]
MUSHROOM_FILES = [
    "Environment/Decoration/spr_mushroom_01.png",
    "Environment/Decoration/spr_mushroom_02.png",
]


# ── Per-category scale factors (pixel-art → screen pixels) ────────────────────
TOWER_SCALE      = 2.5
ENEMY_SCALE      = 3.5
PROJECTILE_SCALE = 2.5
CASTLE_SCALE     = 1.6
DECOR_SCALE      = 2.5
TREE_SCALE       = 3.0

# Per-tower scale overrides — non-combat sprites are 4-frame sheets where
# each frame is ~22-24 px wide.  Once we slice frames they need a slightly
# larger scale to fill a 48-px cell.
TOWER_SCALE_OVERRIDE: dict[str, float] = {
    "WALL":      2.0,    # 22×28 → 44×56
    "FENCE":     2.0,    # 24×34 → 48×68
    "SPIKE":     2.0,
    "BARRICADE": 2.0,
}

# Non-combat tower sprites are 4-frame horizontal strips (idle animation)
NONCOMBAT_TOWER_FRAMES = 4

# Castle sprite is a 4-frame horizontal strip (208×38 → 4 × 52×38)
CASTLE_FRAMES = 4

# Lake water tile is a 4-frame horizontal animation (256×80 → 4 × 64×80)
LAKE_FRAMES = 4


class Assets:
    """Static sprite cache.  Call Assets.init() after pygame.display.set_mode()."""

    _initialised: bool = False
    _raw_cache:   dict[str, pygame.Surface] = {}
    _scaled:      dict[tuple[str, float], pygame.Surface] = {}
    _enemy_frames: dict[str, list[pygame.Surface]] = {}
    _tower_cache:  dict[str, pygame.Surface] = {}                   # combat towers (1 frame)
    _tower_frames: dict[str, list[pygame.Surface]] = {}             # non-combat (4 frames)
    _proj_cache:   dict[str, pygame.Surface] = {}
    _castle_frames: list[pygame.Surface] = []
    _lake_frames:   list[pygame.Surface] = []
    _shop_sprite:   Optional[pygame.Surface] = None
    # Hero animation frames keyed by state ("IDLE", "WALK", ...) — right-facing
    # plus a parallel left-flipped copy for cheap horizontal-flip rendering.
    _hero_frames:        dict[str, list[pygame.Surface]] = {}
    _hero_frames_flipped: dict[str, list[pygame.Surface]] = {}
    # Bosses: keyed by (boss_id, state).  Each value is a list of frames.
    # `_boss_frames_flipped` mirrors them horizontally for left-facing.
    _boss_frames:        dict[tuple[str, str], list[pygame.Surface]] = {}
    _boss_frames_flipped: dict[tuple[str, str], list[pygame.Surface]] = {}
    # Evil3 ranged caster effects (sprite-sheet of square frames).
    _evil3_explode_frames: list[pygame.Surface] = []
    _evil3_moving_frames:  list[pygame.Surface] = []
    # Farming
    _plant_frames:    dict[str, list[pygame.Surface]] = {}   # 4 growth stages each
    _supplier_sprite: dict[str, pygame.Surface] = {}

    # ── Bootstrap ──────────────────────────────────────────────────────────

    @classmethod
    def init(cls) -> None:
        """Pre-load and pre-scale every sprite the renderer will use."""
        if cls._initialised:
            return
        cls._initialised = True

        # Towers — combat towers are single frames; non-combat are 4-frame
        # horizontal sprite-sheets that need to be sliced and animated.
        non_combat = {"WALL", "FENCE", "SPIKE", "BARRICADE"}
        for ttype, rel in TOWER_FILES.items():
            base = cls._load_raw(rel)
            if base is None:
                continue
            scale = TOWER_SCALE_OVERRIDE.get(ttype, TOWER_SCALE)
            if ttype in non_combat:
                w, h = base.get_size()
                fw   = max(1, w // NONCOMBAT_TOWER_FRAMES)
                frames = []
                for i in range(NONCOMBAT_TOWER_FRAMES):
                    rect  = pygame.Rect(i * fw, 0, fw, h)
                    frame = base.subsurface(rect).copy()
                    frames.append(cls._scale(frame, scale))
                cls._tower_frames[ttype] = frames
                # Also keep frame-0 in the static cache as a fallback
                cls._tower_cache[ttype] = frames[0]
            else:
                cls._tower_cache[ttype] = cls._scale(base, scale)

        # Castle — 4-frame sheet (208×38 → 4 × 52×38)
        castle_base = cls._load_raw(CASTLE_FILE)
        if castle_base is not None:
            w, h = castle_base.get_size()
            fw   = max(1, w // CASTLE_FRAMES)
            for i in range(CASTLE_FRAMES):
                rect  = pygame.Rect(i * fw, 0, fw, h)
                frame = castle_base.subsurface(rect).copy()
                cls._castle_frames.append(cls._scale(frame, CASTLE_SCALE * 1.8))

        # Lake — 4-frame water animation (256×80 → 4 × 64×80).  Each frame is
        # scaled to roughly fit POND_RECT (170×100 in config).
        lake_base = cls._load_raw(LAKE_FILE)
        if lake_base is not None:
            w, h = lake_base.get_size()
            fw   = max(1, w // LAKE_FRAMES)
            target_w, target_h = C.POND_RECT[2], C.POND_RECT[3]
            for i in range(LAKE_FRAMES):
                rect  = pygame.Rect(i * fw, 0, fw, h)
                frame = lake_base.subsurface(rect).copy()
                # Scale lake frame to fit POND_RECT
                scaled = pygame.transform.scale(frame, (target_w, target_h))
                cls._lake_frames.append(scaled)

        # Shop — single large pixel-art sprite, scaled down to fit SHOP_RECT.
        shop_base = cls._load_raw(SHOP_FILE)
        if shop_base is not None:
            sw, sh = shop_base.get_size()
            # Target footprint: a bit larger than SHOP_RECT so the shop reads
            # nicely; aspect-fit by the longer dimension.
            target = max(C.SHOP_RECT[2], C.SHOP_RECT[3]) + 50
            scale  = target / max(sw, sh)
            tw, th = max(1, int(sw * scale)), max(1, int(sh * scale))
            cls._shop_sprite = pygame.transform.smoothscale(shop_base, (tw, th))

        # Plant growth sheets — frames are NOT evenly spaced and the count
        # varies per plant (4 or 5 stages).  Detect frame boundaries by
        # looking for vertical transparent gaps in the sprite sheet.
        plant_target_h = 48
        for pid in C.PLANT_DEFS.keys():
            digit = pid.split("_")[1]
            rel   = f"Environment/Farm/Plants/{digit}.png"
            base  = cls._load_raw(rel)
            if base is None:
                continue
            stages = cls._slice_by_alpha_gaps(base, plant_target_h)
            if stages:
                cls._plant_frames[pid] = stages

        # Supplier sprites — single-frame products shown in inventory + shop
        supplier_target_h = 32
        for sid in C.SUPPLIER_DEFS.keys():
            digit = sid.split("_")[1]
            rel   = f"Environment/Farm/Supplier/{digit}.png"
            base  = cls._load_raw(rel)
            if base is None:
                continue
            w, h = base.get_size()
            scale = supplier_target_h / h
            tw = max(1, int(w * scale))
            th = max(1, int(h * scale))
            cls._supplier_sprite[sid] = pygame.transform.smoothscale(base, (tw, th))

        # NOTE: Farm decorations reuse the main-map helpers Assets.tree() /
        # rock() / mushroom() so they render at the same scale and visual
        # style.  No extra preload pass needed here.

        # Boss animations — each boss has multiple states.  Sheets are pure
        # horizontal grids where the frame width equals the sheet height
        # (square frames), so we slice by `frame_w = h, count = w // h`.
        # Each boss species is rendered with its own target render-height to
        # match its in-game `size`.
        for boss_id, defn in C.BOSS_DEFS.items():
            asset_dir = defn["asset"]
            # Render bosses noticeably larger than their collision size so
            # they read as "boss-tier" threats on screen.
            target_h  = int(defn["size"] * 3.8)
            states_listing = cls._scan_boss_states(asset_dir)
            for state_name, rel_path in states_listing.items():
                sheet = cls._load_raw(rel_path)
                if sheet is None:
                    continue
                w, h = sheet.get_size()
                fw   = h                         # square frames
                count = max(1, w // fw)
                frames: list[pygame.Surface] = []
                flipped: list[pygame.Surface] = []
                scale = target_h / h
                for i in range(count):
                    rect  = pygame.Rect(i * fw, 0, fw, h)
                    frame = sheet.subsurface(rect).copy()
                    tw = max(1, int(fw * scale))
                    th = max(1, int(h * scale))
                    f  = pygame.transform.smoothscale(frame, (tw, th))
                    frames.append(f)
                    flipped.append(pygame.transform.flip(f, True, False))
                cls._boss_frames[(boss_id, state_name)]         = frames
                cls._boss_frames_flipped[(boss_id, state_name)] = flipped

        # Evil3 projectile VFX — Explode (impact splash) + Moving (bullet).
        # Both are 50-px-tall horizontal strips of square frames.
        for spec_name, sheet_rel, target_h, store in (
            ("Explode", "Bosses/Evil3/Sprites/Projectile/Explode.png",
             140, cls._evil3_explode_frames),
            ("Moving",  "Bosses/Evil3/Sprites/Projectile/Moving.png",
             64,  cls._evil3_moving_frames),
        ):
            sheet = cls._load_raw(sheet_rel)
            if sheet is None:
                continue
            sw, sh = sheet.get_size()
            fw = sh                          # square frames
            count = max(1, sw // fw)
            scale = target_h / sh
            for i in range(count):
                rect  = pygame.Rect(i * fw, 0, fw, sh)
                frame = sheet.subsurface(rect).copy()
                tw = max(1, int(fw * scale))
                th = max(1, int(sh * scale))
                store.append(pygame.transform.smoothscale(frame, (tw, th)))

        # Hero animations — single horizontal sprite-sheet per state.  Each
        # frame is a square block of HERO_FRAME_PX (180) px; count is
        # sheet_width // 180.  After slicing we smoothscale every frame so
        # height equals HERO_TARGET_HEIGHT and store both right-facing and
        # left-flipped copies.
        for state, rel in HERO_ANIM_SHEETS.items():
            sheet = cls._load_raw(rel)
            if sheet is None:
                continue
            sw, sh = sheet.get_size()
            fw = HERO_FRAME_PX
            count = max(1, sw // fw)
            scale = HERO_TARGET_HEIGHT / sh
            frames: list[pygame.Surface] = []
            flipped: list[pygame.Surface] = []
            for i in range(count):
                rect  = pygame.Rect(i * fw, 0, fw, sh)
                frame = sheet.subsurface(rect).copy()
                tw = max(1, int(fw * scale))
                th = max(1, int(sh * scale))
                f  = pygame.transform.smoothscale(frame, (tw, th))
                frames.append(f)
                flipped.append(pygame.transform.flip(f, True, False))
            cls._hero_frames[state]         = frames
            cls._hero_frames_flipped[state] = flipped

        # Projectiles
        for ptype, rel in PROJECTILE_FILES.items():
            base = cls._load_raw(rel)
            if base is None:
                continue
            cls._proj_cache[ptype] = cls._scale(base, PROJECTILE_SCALE)

        # Enemies — slice horizontally, scale each frame
        for etype, (rel, n_frames) in ENEMY_FILES.items():
            base = cls._load_raw(rel)
            if base is None:
                cls._enemy_frames[etype] = []
                continue
            w, h = base.get_size()
            fw = max(1, w // max(1, n_frames))
            frames: list[pygame.Surface] = []
            for i in range(n_frames):
                rect = pygame.Rect(i * fw, 0, fw, h)
                frame = base.subsurface(rect).copy()
                frames.append(cls._scale(frame, ENEMY_SCALE))
            cls._enemy_frames[etype] = frames

    # ── Public accessors ──────────────────────────────────────────────────

    @classmethod
    def tower(cls, tower_type: str, anim_t: float = 0.0) -> Optional[pygame.Surface]:
        """Return the right tower frame.

        Combat towers are static (single sprite).  Non-combat towers
        (walls/fences/spikes/barricades) are 4-frame sheets — pick a frame
        based on `anim_t` for a slow idle animation.
        """
        cls.init()
        frames = cls._tower_frames.get(tower_type)
        if frames:
            idx = int(anim_t * 3) % len(frames)   # ~3 fps idle animation
            return frames[idx]
        return cls._tower_cache.get(tower_type)

    @classmethod
    def projectile(cls, proj_type: str) -> Optional[pygame.Surface]:
        cls.init()
        return cls._proj_cache.get(proj_type)

    @classmethod
    def enemy_frame(cls, enemy_type: str, anim_t: float) -> Optional[pygame.Surface]:
        """Return the current animation frame for `enemy_type` at time `anim_t`."""
        cls.init()
        frames = cls._enemy_frames.get(enemy_type)
        if not frames:
            return None
        idx = int(anim_t * 8) % len(frames)   # ~8 fps animation
        return frames[idx]

    @classmethod
    def castle(cls, anim_t: float = 0.0) -> Optional[pygame.Surface]:
        """Return the current castle frame for slow idle animation."""
        cls.init()
        if cls._castle_frames:
            idx = int(anim_t * 2) % len(cls._castle_frames)   # ~2 fps idle
            return cls._castle_frames[idx]
        return cls._scaled_load(CASTLE_FILE, CASTLE_SCALE)

    @classmethod
    def ground_tile(cls) -> Optional[pygame.Surface]:
        cls.init()
        return cls._scaled_load(GROUND_TILE, 1.0)

    @classmethod
    def lake_frame(cls, anim_t: float = 0.0) -> Optional[pygame.Surface]:
        """Return the current lake water-animation frame at time `anim_t`."""
        cls.init()
        if cls._lake_frames:
            idx = int(anim_t * 4) % len(cls._lake_frames)   # ~4 fps
            return cls._lake_frames[idx]
        return None

    @classmethod
    def shop(cls) -> Optional[pygame.Surface]:
        cls.init()
        return cls._shop_sprite

    @classmethod
    def hero_frame_at(
        cls,
        state: str,
        frame_idx: int,
        facing_left: bool = False,
    ) -> Optional[pygame.Surface]:
        """Return a specific frame of a hero animation by index.

        Used by the renderer to pin the wind-up frame while the player is
        charging Attack2 (no fps cycling) and to play the swing portion
        on release.  Index is clamped to [0, len-1].
        """
        cls.init()
        bank = cls._hero_frames_flipped if facing_left else cls._hero_frames
        frames = bank.get(state) or bank.get("IDLE")
        if not frames:
            return None
        idx = max(0, min(int(frame_idx), len(frames) - 1))
        return frames[idx]

    @classmethod
    def plant_frame(cls, plant_type: str, stage: int) -> Optional[pygame.Surface]:
        """Return the sprite for a given growth stage (0..3) of a plant."""
        cls.init()
        frames = cls._plant_frames.get(plant_type)
        if not frames:
            return None
        idx = max(0, min(stage, len(frames) - 1))
        return frames[idx]

    @classmethod
    def supplier(cls, supplier_id: str) -> Optional[pygame.Surface]:
        cls.init()
        return cls._supplier_sprite.get(supplier_id)

    @classmethod
    def hero_frame(
        cls,
        state: str,
        anim_t: float,
        facing_left: bool = False,
        fps: float = 10.0,
    ) -> Optional[pygame.Surface]:
        """Return the hero frame for a given animation state at time `anim_t`.

        States (matching new sheet layout): IDLE, RUN, ATTACK1, ATTACK2,
        DEATH, JUMP, FALL.  Older callers asking for "ATTACK" / "WALK" /
        "DIE" are routed to the closest equivalent so legacy code paths
        still get something sensible while the renderer migrates.
        """
        cls.init()
        bank = cls._hero_frames_flipped if facing_left else cls._hero_frames

        # Compatibility aliases for legacy state names
        alias = {
            "WALK":   "RUN",
            "ATTACK": "ATTACK1",
            "DIE":    "DEATH",
            "HURT":   "TAKE_HIT",   # block / damage pose
        }
        key = alias.get(state, state)

        frames = bank.get(key) or bank.get("IDLE")
        if not frames:
            return None
        idx = int(anim_t * fps) % len(frames)
        return frames[idx]

    @classmethod
    def grass_tile(cls, idx: int) -> Optional[pygame.Surface]:
        cls.init()
        path = GRASS_TILES[idx % len(GRASS_TILES)]
        return cls._scaled_load(path, 1.5)

    @classmethod
    def tree(cls, idx: int) -> Optional[pygame.Surface]:
        cls.init()
        path = TREE_FILES[idx % len(TREE_FILES)]
        return cls._scaled_load(path, TREE_SCALE)

    @classmethod
    def rock(cls, idx: int) -> Optional[pygame.Surface]:
        cls.init()
        path = ROCK_FILES[idx % len(ROCK_FILES)]
        return cls._scaled_load(path, DECOR_SCALE)

    @classmethod
    def mushroom(cls, idx: int) -> Optional[pygame.Surface]:
        cls.init()
        path = MUSHROOM_FILES[idx % len(MUSHROOM_FILES)]
        return cls._scaled_load(path, DECOR_SCALE)

    # ── Internals ──────────────────────────────────────────────────────────

    @classmethod
    def _load_raw(cls, rel_path: str) -> Optional[pygame.Surface]:
        if rel_path in cls._raw_cache:
            return cls._raw_cache[rel_path]
        full = os.path.join(ASSETS_DIR, rel_path)
        if not os.path.exists(full):
            return None
        try:
            img = pygame.image.load(full).convert_alpha()
        except pygame.error:
            return None
        cls._raw_cache[rel_path] = img
        return img

    @classmethod
    def _scale(cls, surf: pygame.Surface, factor: float) -> pygame.Surface:
        """Nearest-neighbour scale (pixel art stays crisp)."""
        if abs(factor - 1.0) < 1e-3:
            return surf
        new_size = (max(1, int(surf.get_width() * factor)),
                    max(1, int(surf.get_height() * factor)))
        return pygame.transform.scale(surf, new_size)

    @classmethod
    def _scan_boss_states(cls, asset_dir: str) -> dict[str, str]:
        """Map state-name → relative-path for every PNG in a boss's Sprites folder."""
        full_dir = os.path.join(ASSETS_DIR, "Bosses", asset_dir, "Sprites")
        out: dict[str, str] = {}
        if not os.path.isdir(full_dir):
            return out
        for fn in os.listdir(full_dir):
            if not fn.lower().endswith(".png"):
                continue
            # Use the file name (without extension) as the state key,
            # preserving original capitalisation.
            state = os.path.splitext(fn)[0]
            rel   = f"Bosses/{asset_dir}/Sprites/{fn}"
            out[state] = rel
        return out

    @classmethod
    def boss_frame(
        cls,
        boss_id: str,
        state: str,
        anim_t: float,
        facing_left: bool = False,
    ) -> Optional[pygame.Surface]:
        """Return the right animation frame for a boss in a given state."""
        cls.init()
        bank = cls._boss_frames_flipped if facing_left else cls._boss_frames
        frames = bank.get((boss_id, state))
        if not frames:
            # Fall back to the boss's idle if requested state didn't load
            for fallback in ("Idle", "idle", "Move", "Run", "Walk"):
                frames = bank.get((boss_id, fallback))
                if frames:
                    break
        if not frames:
            return None
        idx = int(anim_t * 10) % len(frames)
        return frames[idx]

    @classmethod
    def boss_frame_count(cls, boss_id: str, state: str) -> int:
        cls.init()
        return len(cls._boss_frames.get((boss_id, state), []))

    @classmethod
    def evil3_explode_frame(cls, frame_idx: int) -> Optional[pygame.Surface]:
        """Return one frame of Evil3's explosion sheet, or None if missing."""
        cls.init()
        frames = cls._evil3_explode_frames
        if not frames:
            return None
        return frames[max(0, min(frame_idx, len(frames) - 1))]

    @classmethod
    def evil3_explode_frame_count(cls) -> int:
        cls.init()
        return len(cls._evil3_explode_frames)

    @classmethod
    def evil3_moving_frame(cls, anim_t: float) -> Optional[pygame.Surface]:
        cls.init()
        if not cls._evil3_moving_frames:
            return None
        idx = int(anim_t * 12) % len(cls._evil3_moving_frames)
        return cls._evil3_moving_frames[idx]

    @classmethod
    def _slice_by_alpha_gaps(
        cls,
        sheet: pygame.Surface,
        target_height: int,
        min_gap: int = 3,
    ) -> list[pygame.Surface]:
        """Detect frame boundaries via fully-transparent column gaps.

        Returns a list of frames, each scaled so its height matches
        `target_height` while preserving aspect ratio.  Useful for sprite
        sheets where frames are NOT evenly spaced.
        """
        w, h = sheet.get_size()
        try:
            arr = pygame.surfarray.array_alpha(sheet)   # shape (W, H)
        except (ValueError, pygame.error):
            return []

        is_zero = [int(arr[c].sum()) == 0 for c in range(w)]

        # Locate runs of fully-transparent columns of width ≥ min_gap
        gaps: list[tuple[int, int]] = []
        i = 0
        while i < w:
            if is_zero[i]:
                j = i
                while j < w and is_zero[j]:
                    j += 1
                if j - i >= min_gap:
                    gaps.append((i, j))
                i = j
            else:
                i += 1

        # Frame regions sit between consecutive gaps (skip leading/trailing)
        regions: list[tuple[int, int]] = []
        cursor = 0
        for gs, ge in gaps:
            if gs > cursor:
                regions.append((cursor, gs))
            cursor = ge
        if cursor < w:
            regions.append((cursor, w))

        # Convert each region to a height-normalised surface
        scale = target_height / h
        out: list[pygame.Surface] = []
        for s_start, s_end in regions:
            fw = s_end - s_start
            if fw <= 0:
                continue
            frame = sheet.subsurface(pygame.Rect(s_start, 0, fw, h)).copy()
            tw = max(1, int(fw * scale))
            th = max(1, int(h * scale))
            out.append(pygame.transform.smoothscale(frame, (tw, th)))
        return out

    @classmethod
    def _scaled_load(cls, rel: str, factor: float) -> Optional[pygame.Surface]:
        key = (rel, factor)
        if key in cls._scaled:
            return cls._scaled[key]
        base = cls._load_raw(rel)
        if base is None:
            return None
        scaled = cls._scale(base, factor)
        cls._scaled[key] = scaled
        return scaled


# Re-export tile size used by the ground tile drawer
TILE_PX = C.CELL_SIZE
