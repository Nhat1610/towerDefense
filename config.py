"""
config.py — All constants and configuration for the Tower Defense game.
Read context.md for full design rationale.
"""

# ── Screen ─────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1280
SCREEN_HEIGHT = 720
GAME_WIDTH    = 960   # Left portion: game world
UI_WIDTH      = 320   # Right portion: UI panel
FPS           = 60

# ── Grid ───────────────────────────────────────────────────────────────────
CELL_SIZE  = 48
GRID_COLS  = GAME_WIDTH  // CELL_SIZE   # 20
GRID_ROWS  = SCREEN_HEIGHT // CELL_SIZE  # 15

# ── Colors ─────────────────────────────────────────────────────────────────
BLACK   = (0,   0,   0)
WHITE   = (255, 255, 255)

# Terrain
GRASS_LIGHT  = (58,  148, 58)
GRASS_DARK   = (46,  120, 46)
PATH_MID     = (160, 120, 68)
PATH_EDGE    = (160, 120, 68)
TREE_GREEN   = (20,   90, 20)
TREE_DARK    = (10,   60, 10)
TREE_TRUNK   = (100,  60, 20)

# Water
WATER_LIGHT  = (80,  180, 230)
WATER_MID    = (50,  140, 200)
WATER_DEEP   = (30,  100, 170)
WATER_SHINE  = (160, 220, 255)
DOCK_WOOD    = (139,  90,  40)

# Castle
STONE_LIGHT  = (160, 160, 165)
STONE_MID    = (120, 118, 122)
STONE_DARK   = ( 80,  78,  84)
GATE_DARK    = ( 30,  20,  20)
WINDOW_GLOW  = (255, 200,  80)

# Spawn area
SPAWN_BG     = ( 25,   0,   0)
SPAWN_GLOW   = ( 90,  10,  10)
SPAWN_GATE   = ( 50,   0,   0)
SPAWN_BONE   = (210, 200, 180)

# Shop
SHOP_WALL    = (180, 130,  70)
SHOP_ROOF    = ( 90,  50,  20)
SHOP_SIGN    = (220, 180,  80)
SHOP_DOOR    = ( 60,  30,  10)

# Tower colors (per type)
TOWER_BALLISTA_BASE = (100,  70,  35)
TOWER_BALLISTA_TOP  = ( 70,  45,  20)
TOWER_CANNON_BASE   = ( 90,  90,  90)
TOWER_CANNON_TOP    = ( 55,  55,  60)
TOWER_TESLA_BASE    = ( 55,   0, 110)
TOWER_TESLA_TOP     = (120,  40, 200)
TOWER_TESLA_GLOW    = ( 80, 120, 255)
TOWER_ICE_BASE      = (100, 170, 230)
TOWER_ICE_TOP       = (200, 230, 255)
TOWER_ICE_CRYSTAL   = (220, 245, 255)
TOWER_FLAME_BASE    = (140,  45,  15)
TOWER_FLAME_TOP     = (200,  80,   0)
TOWER_FLAME_FIRE    = (255, 180,  30)

# Defense colors
WALL_STONE          = (135, 135, 140)
WALL_DARK           = ( 95,  95, 100)
WALL_LIGHT          = (170, 170, 175)
WALL_MORTAR         = ( 70,  70,  75)
FENCE_WOOD          = (150, 110,  60)
FENCE_DARK          = (100,  70,  35)
FENCE_LIGHT         = (190, 150,  90)
SPIKE_BASE          = ( 80,  80,  85)
SPIKE_TIP           = (220, 220, 225)
SPIKE_BLOOD         = (150,  30,  30)
BARRICADE_STEEL     = (110, 105, 100)
BARRICADE_LIGHT     = (170, 165, 155)
BARRICADE_BAND      = ( 60,  55,  45)
BARRICADE_RIVET     = (210, 200, 180)

# UI
UI_BG        = ( 22,  22,  35)
UI_PANEL     = ( 32,  32,  50)
UI_BORDER    = ( 60,  60,  85)
UI_HIGHLIGHT = ( 70,  70, 105)
UI_SELECTED  = ( 50,  80, 140)
UI_TEXT      = (215, 215, 225)
UI_DIM       = (120, 120, 140)
UI_GOLD      = (255, 215,   0)
UI_GREEN     = ( 80, 210,  80)
UI_RED       = (220,  60,  60)
UI_BLUE      = ( 80, 160, 255)

# Health bars
HP_BG        = ( 40,  10,  10)
HP_GREEN     = ( 60, 200,  60)
HP_YELLOW    = (230, 190,  20)
HP_RED       = (210,  40,  40)

# Grid overlay
GRID_LINE    = (0, 0, 0, 40)       # semi-transparent — drawn via Surface
CELL_HOVER   = (255, 255, 100, 60)
CELL_VALID   = (80,  255,  80, 60)
CELL_INVALID = (255,  60,  60, 60)

# ── Path variants (5 diverse lanes; enemies pick one per spawn) ─────────────
PATH_VARIANTS = [
    # Lane 1 — Top Express: northern highway, turns south at x=720
    [(  0,  96), (720,  96), (720, 300), (864, 300)],
    # Lane 2 — Upper Zigzag: weaves between y=48 and y=200
    [(  0,  48), (280,  48), (280, 200), (520, 200), (520,  96), (720,  96), (720, 300), (864, 300)],
    # Lane 3 — Center Direct: straight shot at castle height
    [(  0, 300), (864, 300)],
    # Lane 4 — Lower S-Curve: descends then rises back up
    [(  0, 380), (300, 380), (300, 260), (580, 260), (580, 330), (720, 330), (720, 300), (864, 300)],
    # Lane 5 — Wide Loop: long arc across the battlefield
    [(  0, 200), (180, 200), (180, 360), (400, 360), (400, 140), (680, 140), (680, 300), (864, 300)],
]
PATH_WAYPOINTS   = PATH_VARIANTS[0]   # primary lane alias; used by A* integration
PATH_WIDTH       = 36                 # px — visual width of the dirt road
CASTLE_GOAL_CELL = (15, 6)            # last walkable cell before castle building zone

# ── Castle ─────────────────────────────────────────────────────────────────
CASTLE_CX     = 892
CASTLE_CY     = 300
CASTLE_HP_MAX = 300
# Enemies / bosses can strike the castle once they enter this radius around
# the castle centre — represents the visible footprint of the building so
# attackers don't have to march to the exact pixel centre.
CASTLE_HIT_RANGE = 90

# ── Buildings ──────────────────────────────────────────────────────────────
# Pond starts past the spawn-area band (which occupies 0..90 px) so the
# water sprite sits inside the playable map, not under the spawn portal.
# Width/height tuned to roughly preserve the lake-frame 93×80 aspect.
POND_RECT  = (110, 540, 140, 80)    # (x, y, w, h)
SHOP_RECT  = (270, 520, 110, 90)

# ── Spawn ──────────────────────────────────────────────────────────────────
# Enemies spawn at the first waypoint of their randomly chosen PATH_VARIANTS lane
SPAWN_X    = 0    # left edge; actual y varies per lane (96, 192, 336, 384, 480)

# ── Tower definitions ──────────────────────────────────────────────────────
TOWER_DEFS = {
    "BALLISTA": {
        "name":        "Ballista",
        "cost":        100,
        "hp":          100,
        "damage":      40,
        "range":       200,
        "fire_rate":   1.0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 80,
        "description": "Long range\nHigh single dmg",
        "hotkey":      "1",
    },
    "CANNON": {
        "name":        "Cannon",
        "cost":        150,
        "hp":          100,
        "damage":      80,
        "range":       150,
        "fire_rate":   0.5,
        "splash":      60,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 120,
        "description": "AoE explosion\nSplash 60px",
        "hotkey":      "2",
    },
    "TESLA": {
        "name":        "Tesla",
        "cost":        200,
        "hp":          100,
        "damage":      30,
        "range":       160,
        "fire_rate":   2.0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       3,
        "upgrade_cost": 160,
        "description": "Chain lightning\nHits 3 enemies",
        "hotkey":      "3",
    },
    "ICE": {
        "name":        "Ice Tower",
        "cost":        120,
        "hp":          100,
        "damage":      15,
        "range":       140,
        "fire_rate":   1.5,
        "splash":      0,
        "slow":        0.5,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 100,
        "description": "Slows 50%\nfor 2 seconds",
        "hotkey":      "4",
    },
    "FLAME": {
        "name":        "Flame Tower",
        "cost":        130,
        "hp":          100,
        "damage":      25,
        "range":       120,
        "fire_rate":   3.0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    10,
        "chain":       0,
        "upgrade_cost": 110,
        "description": "Burns enemies\n+10 dmg/s x 3s",
        "hotkey":      "5",
    },
}

TOWER_TYPES = list(TOWER_DEFS.keys())   # ordered list for hotkey mapping

# ── Defensive structure definitions ────────────────────────────────────────
# Walls / fences / spikes / barricades. Cannot shoot, but block enemies.
# Enemies will attack and destroy them just like towers.
DEFENSE_DEFS = {
    "WALL": {
        "name":        "Stone Wall",
        "category":    "DEFENSE",
        "cost":        30,
        "hp":          120,
        "damage":      0,
        "range":       0,
        "fire_rate":   0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 25,
        "description": "Sturdy barrier\nBlocks enemies",
        "hotkey":      "6",
    },
    "FENCE": {
        "name":        "Wood Fence",
        "category":    "DEFENSE",
        "cost":        15,
        "hp":          50,
        "damage":      0,
        "range":       0,
        "fire_rate":   0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 10,
        "description": "Cheap barrier\nLow HP",
        "hotkey":      "7",
    },
    "SPIKE": {
        "name":        "Spike Trap",
        "category":    "DEFENSE",
        "cost":        60,
        "hp":          100,
        "damage":      12,
        "range":       55,
        "fire_rate":   0,    # passive damage, no projectile
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 50,
        "description": "Damages adjacent\nenemies / sec",
        "hotkey":      "8",
    },
    "BARRICADE": {
        "name":        "Iron Barricade",
        "category":    "DEFENSE",
        "cost":        80,
        "hp":          250,
        "damage":      0,
        "range":       0,
        "fire_rate":   0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 60,
        "description": "Heavy iron wall\nHigh durability",
        "hotkey":      "9",
    },
}

DEFENSE_TYPES = list(DEFENSE_DEFS.keys())

# ── Shop / consumable items ────────────────────────────────────────────────
# Items that aren't tower/defense but still sit alongside them in the HUD
# "ITEMS" section.  Buying any item in this section deducts gold immediately
# and drops the item into the inventory; the player then drags it onto the
# world to use (e.g. fish food onto the pond).
SHOP_ITEM_DEFS = {
    "FISH_FOOD": {
        "name":        "Fish Food",
        "category":    "ITEM",
        "cost":        40,         # FISH_FOOD_COST kept here in sync
        "hp":          0,
        "damage":      0,
        "range":       0,
        "fire_rate":   0,
        "splash":      0,
        "slow":        0.0,
        "burn_dps":    0,
        "chain":       0,
        "upgrade_cost": 0,
        "description": "Drag to pond\n+5% catch rate",
        "hotkey":      "0",
    },
}

# ── Farming ─────────────────────────────────────────────────────────────────
# 5 plant species — each is bought in the shop, planted on a farm tile, grows
# through 4 stages over `growth_seconds` seconds, then can be harvested for
# the matching supplier item.  Suppliers are sold through the shop SELL slot.
PLANT_DEFS: dict[str, dict] = {
    "PLANT_1": {  # small bushy plant
        "name":        "Sprout",
        "cost":        20,
        "growth_seconds": 30.0,
        "supplier":    "SUPPLIER_1",
        "description": "Cheap and fast.\nDrag onto a farm plot.",
    },
    "PLANT_2": {
        "name":        "Saplings",
        "cost":        40,
        "growth_seconds": 60.0,
        "supplier":    "SUPPLIER_2",
        "description": "Steady payoff.\nDrag onto a farm plot.",
    },
    "PLANT_3": {  # apple tree
        "name":        "Apple Tree",
        "cost":        80,
        "growth_seconds": 120.0,
        "supplier":    "SUPPLIER_3",
        "description": "Slow grower\nwith juicy yield.",
    },
    "PLANT_4": {
        "name":        "Berry Bush",
        "cost":        130,
        "growth_seconds": 180.0,
        "supplier":    "SUPPLIER_4",
        "description": "Patient profit.\nDrag onto a plot.",
    },
    "PLANT_5": {
        "name":        "Grand Tree",
        "cost":        200,
        "growth_seconds": 240.0,
        "supplier":    "SUPPLIER_5",
        "description": "Highest payoff.\nLong wait, big rewards.",
    },
}

SUPPLIER_DEFS: dict[str, dict] = {
    "SUPPLIER_1": {"name": "Greens",     "sell_price":  50},
    "SUPPLIER_2": {"name": "Saplings",   "sell_price": 110},
    "SUPPLIER_3": {"name": "Apples",     "sell_price": 220},
    "SUPPLIER_4": {"name": "Berries",    "sell_price": 380},
    "SUPPLIER_5": {"name": "Grand Crop", "sell_price": 550},
}

# Reverse lookup: SUPPLIER_X → PLANT_X.  Used by the inventory and shop
# renderers to draw a harvested supplier with the matured plant sprite
# (so the item icon visually matches the crop it came from) instead of a
# generic coloured block.
SUPPLIER_TO_PLANT: dict[str, str] = {
    _pd["supplier"]: _pid for _pid, _pd in PLANT_DEFS.items()
}

PLANT_GROWTH_STAGES = 4   # number of frames in each plant sprite-sheet

# ── Farm map layout ─────────────────────────────────────────────────────────
# Farm uses the same 1280×720 screen and 48-px grid as the main map but
# with a different cell type ("PLOT") on a fixed rectangular block.
FARM_PLOT_RECT = (3, 4, 14, 8)   # (col0, row0, w, h) on the grid

# Portal between maps:
#   Main map → farm:  rectangle just past the castle on the right edge
#   Farm map → main:  rectangle on the left edge of the farm map
# Portal sits high up on the right edge so it doesn't overlap the castle
# (which is centred at y≈300).  Hero walks into it to enter the farm.
FARM_PORTAL_RECT_MAIN = (924, 100, 32, 96)
FARM_PORTAL_RECT_FARM = (4,   312, 40, 96)

# Combined dict — used by Tower class and item placement logic
ALL_DEFS  = {**TOWER_DEFS, **DEFENSE_DEFS, **SHOP_ITEM_DEFS}

# HUD ITEMS panel only shows defensive items (towers + walls).  Consumables
# (Fish Food) and farming plants are bought via the in-world Shop building.
HUD_BUYABLE_TYPES  = list(TOWER_DEFS.keys()) + list(DEFENSE_DEFS.keys())  # hotkeys 1..9
SHOP_BUYABLE_TYPES = list(SHOP_ITEM_DEFS.keys()) + list(PLANT_DEFS.keys())

# Backwards-compat alias for callers that still iterate every type
ALL_TYPES = HUD_BUYABLE_TYPES + SHOP_BUYABLE_TYPES

# ── Enemy definitions ──────────────────────────────────────────────────────
ENEMY_DEFS = {
    "GOBLIN": {
        "name":   "Goblin",
        "hp":     60,
        "speed":  80,
        "damage": 10,
        "reward": 15,
        "size":   14,
        "color":  ( 60, 200,  60),
        "accent": (100, 255, 100),
    },
    "SKELETON": {
        "name":   "Skeleton",
        "hp":     80,
        "speed":  90,
        "damage": 15,
        "reward": 20,
        "size":   16,
        "color":  (210, 200, 180),
        "accent": (240, 240, 220),
    },
    "ORC": {
        "name":   "Orc",
        "hp":     200,
        "speed":  50,
        "damage": 25,
        "reward": 30,
        "size":   22,
        "color":  ( 40, 120,  40),
        "accent": ( 60, 160,  60),
    },
    "TROLL": {
        "name":   "Troll",
        "hp":     500,
        "speed":  30,
        "damage": 50,
        "reward": 80,
        "size":   30,
        "color":  (110,  85,  60),
        "accent": (150, 110,  80),
    },
}

# Wave composition: list of (enemy_type, count, interval_s)
# ── Wave + Boss configuration ─────────────────────────────────────────────
# 30 waves total.  Every 10th wave (10, 20, 30) is a boss wave.  Defeating
# the wave-30 boss is the win condition.
MAX_WAVE = 30
BOSS_WAVE_INTERVAL = 10
BOSS_WAVES = (10, 20, 30)
FINAL_WAVE = 30

# 3 boss species — each maps to one of the assets/Bosses/Evil{1,2,3} folders.
BOSS_DEFS = {
    "EVIL1": {  # Wave 10 boss
        "name":         "Evil Knight",
        "asset":        "Evil1",
        "hp":           1500,
        "speed":        35,
        "damage":       100,    # damage dealt to castle on attack
        "reward":       300,
        "size":         50,     # rendered size + collision radius
        "atk_period":   1.2,    # seconds between strikes when adjacent to castle
        "atk_states":   ["Attack"],   # which animation(s) to cycle for swings
    },
    "EVIL2": {  # Wave 20 boss
        "name":         "Evil Brute",
        "asset":        "Evil2",
        "hp":           3500,
        "speed":        40,
        "damage":       200,
        "reward":       600,
        "size":         70,
        "atk_period":   1.0,
        "atk_states":   ["Attack1", "Attack2"],   # alternates two strikes
    },
    "EVIL3": {  # Wave 30 final boss — RANGED caster
        "name":         "Evil Reaper",
        "asset":        "Evil3",
        "hp":           7000,
        "speed":        45,
        "damage":       400,
        "reward":       1200,
        "size":         60,
        "atk_period":   1.4,         # slower cadence — ranged casts
        "atk_states":   ["Attack"],
        "is_ranged":    True,
        "atk_range":    260,         # casts at this distance from target
    },
}

# Wave 10/20/30 spawn entries: a single boss + small minion escort
WAVE_CONFIGS = [
    # Waves 1..9 — escalating regular waves
    [("GOBLIN",   8, 1.5)],
    [("GOBLIN",  10, 1.2), ("SKELETON",  4, 2.0)],
    [("ORC",      5, 2.5), ("GOBLIN",   12, 1.0)],
    [("SKELETON",10, 1.5), ("ORC",       6, 2.0)],
    [("TROLL",    2, 5.0), ("ORC",       6, 2.0), ("SKELETON",  8, 1.5)],
    [("GOBLIN",  20, 0.8), ("SKELETON", 10, 1.5)],
    [("ORC",     10, 1.8), ("TROLL",     2, 4.0)],
    [("SKELETON",14, 1.2), ("ORC",       8, 1.8), ("TROLL",     1, 5.0)],
    [("ORC",     12, 1.5), ("TROLL",     3, 4.0), ("SKELETON", 12, 1.0)],
    # Wave 10 — first boss (Evil1) + minions
    [("BOSS_EVIL1", 1, 0.5), ("GOBLIN",   8, 1.0), ("SKELETON",  4, 1.5)],
    # Waves 11..19 — escalation tier 2
    [("ORC",     14, 1.5), ("TROLL",     3, 3.5)],
    [("SKELETON",18, 1.0), ("ORC",      10, 1.5)],
    [("TROLL",    4, 3.0), ("ORC",      12, 1.5)],
    [("GOBLIN",  30, 0.6), ("SKELETON", 14, 1.0)],
    [("ORC",     16, 1.2), ("TROLL",     5, 3.0)],
    [("SKELETON",22, 0.9), ("ORC",      14, 1.2)],
    [("TROLL",    6, 2.5), ("ORC",      14, 1.4)],
    [("ORC",     20, 1.0), ("TROLL",     6, 2.5), ("SKELETON", 16, 0.8)],
    [("TROLL",    8, 2.2), ("ORC",      18, 1.0), ("GOBLIN",   30, 0.5)],
    # Wave 20 — second boss (Evil2) + minions
    [("BOSS_EVIL2", 1, 0.5), ("ORC",     10, 1.0), ("TROLL",     3, 3.0)],
    # Waves 21..29 — escalation tier 3
    [("ORC",     22, 1.0), ("TROLL",     8, 2.0)],
    [("TROLL",   10, 2.0), ("SKELETON", 24, 0.8)],
    [("ORC",     28, 0.9), ("TROLL",    10, 2.0)],
    [("TROLL",   12, 1.8), ("ORC",      24, 0.9)],
    [("SKELETON",32, 0.7), ("ORC",      24, 0.8), ("TROLL",     8, 2.5)],
    [("TROLL",   14, 1.6), ("ORC",      28, 0.8)],
    [("GOBLIN",  50, 0.4), ("SKELETON", 28, 0.7), ("TROLL",    10, 2.0)],
    [("ORC",     34, 0.7), ("TROLL",    14, 1.5)],
    [("TROLL",   18, 1.4), ("ORC",      30, 0.7), ("SKELETON", 24, 0.6)],
    # Wave 30 — final boss (Evil3) + heavy escort
    [("BOSS_EVIL3", 1, 0.5), ("TROLL",   6, 2.0), ("ORC",      14, 1.0),
     ("SKELETON", 16, 0.8)],
]
assert len(WAVE_CONFIGS) == MAX_WAVE

# ── Fishing — probabilistic rate + click-timing minigame ──────────────────
# Replaces the old cooldown-based system entirely.  When the player presses
# the "Cast" button near the pond, FishPond rolls `current_rate` to decide
# whether a fish appears.  If it does, a 3-round click-timing minigame
# runs — the player must click while the moving slider is on the green
# zone three times in a row to actually land the fish.

FISH_RATE_INITIAL       = 0.5   # starting probability of a fish appearing
FISH_RATE_MIN           = 0.25
FISH_RATE_MAX           = 0.85
FISH_RATE_FEED_BONUS    = 0.05   # +5% per fish-food fed
FISH_RATE_DECAY_AMOUNT  = 0.05   # -5% per decay tick if not fed
FISH_RATE_DECAY_INTERVAL = 120.0 # seconds — every 2 minutes without feeding

# Fish products that go into the inventory after a successful catch
FISH_RARE_CHANCE        = 0.20   # chance of catching a rare fish vs common
FISH_COMMON_PRICE       = 30     # gold when sold at shop
FISH_RARE_PRICE         = 120
FISH_FOOD_COST          = 40     # gold to buy one fish food (unchanged)

# Minigame layout (overlay shown over the world)
FISHING_BAR_W           = 460
FISHING_BAR_H           = 36
FISHING_GREEN_WIDTHS    = (0.30, 0.18, 0.10)  # green zone fraction per round
FISHING_SLIDER_SPEED    = 1.6   # full sweeps per second (constant)
FISHING_HITS_REQUIRED   = 3
FISHING_TIMEOUT         = 10.0  # seconds before fish escapes if player idles

# ── Inventory ──────────────────────────────────────────────────────────────
INVENTORY_SIZE          = 20
INVENTORY_OVERLAY_W     = 560
INVENTORY_OVERLAY_H     = 480
INVENTORY_COLS          = 5
INVENTORY_SLOT_SIZE     = 64
INVENTORY_SLOT_GAP      = 12

# Item registry (everything that can sit in the inventory).  Tower/defense
# entries are auto-injected below so buying a tower puts it in the bag.
ITEM_DEFS: dict[str, dict] = {
    "FISH_FOOD": {
        "name":        "Fish Food",
        "color":       (250, 200, 80),
        "stackable":   True,
        "usable":      True,
        "drag_target": "POND",      # valid drop target during drag
        "description": "Drag onto the pond\nto feed (+5% catch rate).",
    },
    "FISH_COMMON": {
        "name":        "Common Fish",
        "color":       (150, 220, 255),
        "stackable":   True,
        "usable":      False,
        "drag_target": None,
        "sell_price":  FISH_COMMON_PRICE,
        "description": f"Sells for {FISH_COMMON_PRICE}g at the shop.",
    },
    "FISH_RARE": {
        "name":        "Rare Fish",
        "color":       (255, 180, 220),
        "stackable":   True,
        "usable":      False,
        "drag_target": None,
        "sell_price":  FISH_RARE_PRICE,
        "description": f"Sells for {FISH_RARE_PRICE}g at the shop.",
    },
}

# Auto-register every tower/defense as an inventory item so they can sit in
# the bag after purchase.  Drag-target = GRID (drop on a free cell to place).
for _ttype, _td in {**TOWER_DEFS, **DEFENSE_DEFS}.items():
    ITEM_DEFS[_ttype] = {
        "name":        _td["name"],
        "color":       (180, 180, 210),
        "stackable":   True,
        "usable":      False,
        "drag_target": "GRID",
        "description": f"Drag onto an empty cell\nto place. Cost {_td['cost']}g.",
    }

# Farm-side items: plants (drag onto a farm plot) + suppliers (sellable harvest)
for _pid, _pd in PLANT_DEFS.items():
    ITEM_DEFS[_pid] = {
        "name":        _pd["name"],
        "color":       (140, 200, 120),
        "stackable":   True,
        "usable":      False,
        "drag_target": "FARM_PLOT",
        "cost":        _pd["cost"],          # mirror so the shop can charge
        "description": _pd["description"],
    }
for _sid, _sd in SUPPLIER_DEFS.items():
    ITEM_DEFS[_sid] = {
        "name":        _sd["name"],
        "color":       (240, 180, 80),
        "stackable":   True,
        "usable":      False,
        "drag_target": None,
        "sell_price":  _sd["sell_price"],
        "description": f"Sells for {_sd['sell_price']}g at the shop.",
    }

# Fishing-button placement — drawn just below the pond so it doesn't collide
# with the shop building to the right.
FISH_BUTTON_RECT = (POND_RECT[0] + POND_RECT[2] - 96,
                    POND_RECT[1] + POND_RECT[3] + 4,
                    96, 26)

# ── Upgrade economy ────────────────────────────────────────────────────────
CASTLE_HP_UPGRADE_BASE_COST = 120   # cost of the FIRST castle HP upgrade
CASTLE_HP_UPGRADE_AMOUNT    = 80    # max-HP gained per upgrade level
CASTLE_HP_UPGRADE_GROWTH    = 1.6   # cost multiplier per level

# ── Save game ──────────────────────────────────────────────────────────────
SAVE_FILE             = "savegame.json"
SAVE_MAX_SNAPSHOTS    = 6     # keep last N wave snapshots for rewind
SAVE_REWIND_WAVES     = 5     # rewind this many waves on game-over continue

# ── User settings (separate from savegame so "New Game" doesn't wipe them) ─
SETTINGS_FILE         = "settings.json"
DEFAULT_MUSIC_VOLUME  = 0.6              # 60 % on first launch

# ── Background music ──────────────────────────────────────────────────────
MUSIC_DAY_PATH        = "assets/Music/day.mp3"
MUSIC_NIGHT_PATH      = "assets/Music/night.mp3"
MUSIC_CROSSFADE_S     = 1.5              # day ↔ night crossfade duration

# ── Hero (playable character) ──────────────────────────────────────────────
HERO_HP_MAX       = 50
HERO_SPEED        = 190   # px/s — base movement; sprint multiplies this
HERO_ATTACK_RANGE = 85    # px — Attack1 swing radius
HERO_ATTACK_DMG   = 22    # Attack1 base damage (also HERO_ATK1_DAMAGE alias below)
HERO_ATTACK_RATE  = 1.2   # Attack1 swings per second (cooldown = 1/rate)
HERO_DETECT_RANGE = 72    # enemies notice and attack the hero within this px
HERO_ENEMY_DMG    = 0.28  # fraction of enemy.damage dealt to hero per hit
HERO_ENEMY_HIT_CD = 1.4   # seconds between enemy hits on hero
HERO_START_X      = 720.0
HERO_START_Y      = 555.0

# Sprint (Shift + WASD) — 1.4× speed gated by stamina
HERO_SPRINT_MULT          = 1.4
HERO_STAMINA_MAX          = 5.0
HERO_STAMINA_REGEN_DELAY  = 3.0
HERO_STAMINA_REGEN_RATE   = HERO_STAMINA_MAX / 3.0  # full refill in 3 s

# Attack1 (left-click) — manual swing, replaces auto-attack
HERO_ATK1_DAMAGE          = HERO_ATTACK_DMG

# Attack2 (right-click hold) — charged stun + knockback.  Cooldown now scales
# with how long the player held the charge: a quick tap is 2.5 s, a fully
# charged release is 6.0 s.
HERO_ATK2_DAMAGE_MULT     = 1.5     # vs Attack1 damage
HERO_ATK2_COOLDOWN_MIN    = 2.5     # cooldown for an immediate-release tap
HERO_ATK2_COOLDOWN_MAX    = 6.0     # cooldown after a fully-charged release
HERO_ATK2_STUN_TIME       = 0.20    # seconds non-bosses are frozen
HERO_ATK2_HOLD_TIER1_S    = 2.0     # hold ≥ this → tier1 push
HERO_ATK2_HOLD_TIER2_S    = 4.0     # hold ≥ this → tier2 push (max)
HERO_ATK2_PUSH_TIER1_PX   = 80      # tier1 knockback distance
HERO_ATK2_PUSH_TIER2_PX   = 160     # tier2 knockback distance
HERO_ATK2_BOSS_PUSH_MULT  = 0.30    # bosses keep just 30 % of pushback
HERO_ATK2_RANGE           = 100     # cone reach from hero
HERO_ATK2_CONE_DOT        = 0.5     # cone half-angle = acos(this) ≈ ±60°
HERO_ATK2_KNOCK_DURATION  = 0.30    # seconds of slide motion after release
HERO_ATK2_SWING_WINDOW    = 0.30    # how long the post-release swing animation plays
HERO_ATK2_MAX_TARGETS     = 10      # max enemies pushed in a single release

# Hero Block (E key) ------------------------------------------------------
HERO_BLOCK_ABSORB_FRACTION = 0.30    # share of post-armor dmg eaten by the shield
HERO_BLOCK_RAW_BREAK       = 200.0   # raw post-armor dmg accumulated → auto-cancel
HERO_BLOCK_HOLD_MAX_S      = 6.0     # max guard duration before auto-cancel
HERO_BLOCK_COOLDOWN_MIN    = 1.0     # cooldown after an instant tap-release
HERO_BLOCK_COOLDOWN_MAX    = 6.0     # cooldown after a fully-held release

# Upgrade catalogue — bought from the Hero status panel
HERO_UPGRADE_DEFS = {
    "HP":     {"cost":  50, "step":  10, "max_tier": 10, "stat": "max_hp"},
    "ARMOR":  {"cost":  50, "step":   1, "max_tier": 10, "stat": "armor"},
    "SPEED":  {"cost":  80, "step":  15, "max_tier": 10, "stat": "base_speed"},
    "DAMAGE": {"cost": 100, "step":   3, "max_tier": 10, "stat": "atk1_damage"},
}

POND_INTERACT_RANGE  = 95    # hero must be within this px to fish
SHOP_INTERACT_RANGE  = 95    # hero must be within this px to buy/sell
CASTLE_SAFE_RANGE    = 115   # hero regenerates HP inside the castle perimeter
HERO_REGEN_RATE      = 5.0   # HP per second while inside castle safe zone

# ── Day / Night phase timing ───────────────────────────────────────────────
DAY_DURATION       = 330.0   # seconds — 4 minutes preparation per day
ENEMY_HP_SCALE     = 0.25    # +25% HP per wave above 1 (multiplicative growth)
ENEMY_HP_GROWTH    = "compound"  # "linear" → 1 + (w-1)*scale; "compound" → (1+scale)**(w-1)

# ── Misc ───────────────────────────────────────────────────────────────────
STARTING_GOLD  = 600
PROJECTILE_SPD = 300    # px/s for most projectiles
