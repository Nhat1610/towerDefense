"""
src/entities.py
===============
All game entity classes: Castle, Enemy, Tower (5 types), Projectile,
FishPond, Shop.

These classes hold *state* only — no pygame drawing here.
All rendering lives in renderer.py / hud.py.
"""

from __future__ import annotations
import math
import pygame
from typing import Optional, TYPE_CHECKING

import config as C

if TYPE_CHECKING:
    pass   # avoid circular imports


# ══════════════════════════════════════════════════════════════════════════════
# Castle
# ══════════════════════════════════════════════════════════════════════════════

class Castle:
    def __init__(self) -> None:
        self.cx: float = C.CASTLE_CX
        self.cy: float = C.CASTLE_CY
        self.upgrade_level: int = 0
        self.max_hp: int = C.CASTLE_HP_MAX + self.upgrade_bonus()
        self.hp: int   = self.max_hp
        self._node = None  # linked-list node reference (set by game)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)

    def scale_for_wave(self, wave: int) -> None:
        """Increase max HP each wave; also keep upgrade bonus baked in."""
        self.max_hp = C.CASTLE_HP_MAX + wave * 100 + self.upgrade_bonus()
        self.hp = self.max_hp

    # ── Upgrade ──────────────────────────────────────────────────────────

    def upgrade_bonus(self) -> int:
        """Return the total HP bonus granted by all castle upgrades so far."""
        return self.upgrade_level * C.CASTLE_HP_UPGRADE_AMOUNT

    def next_upgrade_cost(self) -> int:
        """Return the gold cost for the next castle upgrade (exponential scaling)."""
        return int(
            C.CASTLE_HP_UPGRADE_BASE_COST
            * (C.CASTLE_HP_UPGRADE_GROWTH ** self.upgrade_level)
        )

    def apply_upgrade(self) -> None:
        """Bump max HP and heal the player by the upgrade amount."""
        self.upgrade_level += 1
        self.max_hp += C.CASTLE_HP_UPGRADE_AMOUNT
        self.hp = min(self.max_hp, self.hp + C.CASTLE_HP_UPGRADE_AMOUNT)


# ══════════════════════════════════════════════════════════════════════════════
# Enemy
# ══════════════════════════════════════════════════════════════════════════════

class Enemy:
    """
    An enemy that walks along the path waypoints toward the castle.

    Path following:
        self.waypoints is a list of (x, y) pixel positions.
        self._wp_index is the index of the NEXT waypoint to reach.
        On each update, the enemy moves toward waypoints[_wp_index].
        When it arrives, _wp_index increments.
        When _wp_index >= len(waypoints), the enemy has reached the castle.
    """

    def __init__(
        self,
        enemy_type: str,
        waypoints: list[tuple[float, float]],
        wave: int = 1,
    ) -> None:
        defn = C.ENEMY_DEFS[enemy_type]
        self.enemy_type: str   = enemy_type
        self.name:       str   = defn["name"]
        self.wave:       int   = wave

        # HP scales with wave so later waves are tougher
        scale = self._wave_hp_scale(wave)
        self.hp:         float = defn["hp"] * scale
        self.max_hp:     float = defn["hp"] * scale
        self.speed:      float = defn["speed"]
        self.damage:     int   = defn["damage"]
        self.reward:     int   = defn["reward"] + max(0, (wave - 1) * 2)
        self.size:       int   = defn["size"]
        self.color             = defn["color"]
        self.accent            = defn["accent"]

        self.waypoints  = waypoints
        self._wp_index  = 0

        # Start at first waypoint (spawn position)
        self.x: float = float(waypoints[0][0])
        self.y: float = float(waypoints[0][1])

        # Status effects
        self.slow_timer:  float = 0.0   # seconds remaining of slow
        self.slow_factor: float = 1.0   # multiplier (0.5 = half speed)
        self.burn_timer:  float = 0.0   # seconds of burn remaining
        self.burn_dps:    float = 0.0   # damage per second from burn

        self.dead:        bool  = False
        self.reached_end: bool  = False
        self._node = None  # linked-list node reference
        self._hero_attack_timer: float = 0.0  # cooldown between hits on hero

        self.target_tower = None          # Tower this enemy is chewing through
        self._tower_atk_timer: float = 0.0
        self._castle_atk_timer: float = 0.0  # cooldown between hits on castle

        # ── Hero Attack 2 status effects ──────────────────────────────────
        # Stun freezes movement.  Knockback overrides waypoint motion with
        # a linear slide (vx, vy) for `knock_t` seconds.  When the slide
        # ends Game schedules an A* repath back to the original lane.
        self.stun_timer: float = 0.0
        self.knock_vx:  float = 0.0
        self.knock_vy:  float = 0.0
        self.knock_t:   float = 0.0
        self._needs_repath: bool = False
        # Original lane the enemy spawned with — used by A* repath after
        # being knocked off the path.
        self._original_lane: list[tuple[float, float]] = list(waypoints)

    # ── Movement ───────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Advance enemy toward the next waypoint."""
        if self.dead or self.reached_end:
            return

        # Status effects (apply before movement so they freeze / replace it)
        if self.stun_timer > 0.0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            # Burn still ticks while stunned
            if self.burn_timer > 0:
                self.burn_timer -= dt
                self.hp -= self.burn_dps * dt
            if self.hp <= 0:
                self.dead = True
            return

        if self.knock_t > 0.0:
            # Slide in the knockback direction; clamp to game bounds
            self.x += self.knock_vx * dt
            self.y += self.knock_vy * dt
            self.x = max(8.0, min(C.GAME_WIDTH - 8.0, self.x))
            self.y = max(8.0, min(C.SCREEN_HEIGHT - 8.0, self.y))
            self.knock_t -= dt
            if self.knock_t <= 0.0:
                self.knock_t  = 0.0
                self.knock_vx = 0.0
                self.knock_vy = 0.0
                self._needs_repath = True   # game will run A* on next tick
            # Burn still ticks while flying
            if self.burn_timer > 0:
                self.burn_timer -= dt
                self.hp -= self.burn_dps * dt
            if self.hp <= 0:
                self.dead = True
            return

        # Tower-attack mode (PvZ: chew through the blocking tower)
        if self.target_tower is not None:
            if not self.target_tower.alive:
                self.target_tower = None   # tower gone, resume walking
            else:
                self._tower_atk_timer -= dt
                if self._tower_atk_timer <= 0:
                    self._tower_atk_timer = 1.0   # one attack per second
                    self.target_tower.take_damage(self.damage)
                return  # stay frozen while attacking

        # Burn damage
        if self.burn_timer > 0:
            self.burn_timer -= dt
            self.hp -= self.burn_dps * dt

        # Slow decay
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_factor = 1.0

        if self.hp <= 0:
            self.dead = True
            return

        if self._wp_index >= len(self.waypoints):
            self.reached_end = True
            return

        tx, ty = self.waypoints[self._wp_index]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        effective_speed = self.speed * self.slow_factor
        step = effective_speed * dt

        if dist <= step:
            self.x, self.y = tx, ty
            self._wp_index += 1
        else:
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step

    def take_damage(self, amount: float) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self.dead = True

    def apply_slow(self, factor: float, duration: float) -> None:
        self.slow_factor = factor
        self.slow_timer  = duration

    def apply_burn(self, dps: float, duration: float) -> None:
        self.burn_dps   = dps
        self.burn_timer = duration

    @property
    def progress(self) -> float:
        """0.0 (just spawned) → 1.0 (reached castle).  Used for priority sorting."""
        if not self.waypoints:
            return 0.0
        return self._wp_index / len(self.waypoints)

    @staticmethod
    def _wave_hp_scale(wave: int) -> float:
        """Return the HP multiplier for a given wave (>= 1).

        Linear : 1 + (wave-1) * scale     → wave 1×, wave 2 1.25×, wave 5 2.0×
        Compound: (1 + scale) ** (wave-1) → snowballs faster on late waves
        """
        if wave <= 1:
            return 1.0
        scale = max(0.0, C.ENEMY_HP_SCALE)
        if C.ENEMY_HP_GROWTH == "compound":
            return (1.0 + scale) ** (wave - 1)
        return 1.0 + (wave - 1) * scale


# ══════════════════════════════════════════════════════════════════════════════
# Boss — heavy single-spawn appearing every 10 waves
# ══════════════════════════════════════════════════════════════════════════════

class Boss(Enemy):
    """A boss enemy with greatly amplified stats and animation states.

    Inherits Enemy movement so it walks the same waypoints, but uses
    BOSS_DEFS instead of ENEMY_DEFS for its base stats.  The current
    animation state (`anim_state`) is updated every frame by the renderer
    based on observable behaviour — IDLE / Move / Attack / Hit / Death —
    and the matching frame is sourced from Assets.
    """

    def __init__(
        self,
        boss_id: str,
        waypoints: list[tuple[float, float]],
        wave: int = 1,
    ) -> None:
        defn = C.BOSS_DEFS[boss_id]
        # We deliberately bypass Enemy.__init__ because BOSS_DEFS has a
        # different shape and we don't want wave HP-scaling (bosses are
        # already heavy hitters).  Instead, fill in the Enemy contract.
        self.boss_id:    str   = boss_id
        self.enemy_type: str   = "BOSS"
        self.name:       str   = defn["name"]
        self.wave:       int   = wave

        self.hp:         float = float(defn["hp"])
        self.max_hp:     float = float(defn["hp"])
        self.speed:      float = float(defn["speed"])
        self.damage:     int   = int(defn["damage"])
        self.reward:     int   = int(defn["reward"])
        self.size:       int   = int(defn["size"])
        self.color             = (220, 60, 60)
        self.accent            = (255, 120, 120)

        self.waypoints  = waypoints
        self._wp_index  = 0
        self.x: float = float(waypoints[0][0])
        self.y: float = float(waypoints[0][1])

        # Status effects
        self.slow_timer:  float = 0.0
        self.slow_factor: float = 1.0
        self.burn_timer:  float = 0.0
        self.burn_dps:    float = 0.0

        self.dead:        bool  = False
        self.reached_end: bool  = False
        self._node = None
        self._hero_attack_timer: float = 0.0

        self.target_tower = None
        self._tower_atk_timer: float = 0.0
        self._castle_atk_timer: float = 0.0

        # Hero Attack 2 status fields (mirror Enemy.__init__).  Bosses
        # ignore stun via the override below but still slide on knockback.
        self.stun_timer: float = 0.0
        self.knock_vx:  float = 0.0
        self.knock_vy:  float = 0.0
        self.knock_t:   float = 0.0
        self._needs_repath: bool = False
        self._original_lane: list[tuple[float, float]] = list(waypoints)

        # Boss-specific animation/attack tracking
        self.anim_state: str = "Idle"
        self._attack_swing_idx: int = 0    # for bosses with multiple Attack states
        self._attack_anim_until: float = 0.0  # walltime in seconds; renderer compares
        self._hit_anim_until:    float = 0.0
        self._death_anim_started_at: float = 0.0
        self._removal_delay: float = 1.4   # how long Death animation plays before removal

        # Hero-priority attack: when the hero comes within HERO_ATK_RANGE the
        # boss stops moving and pummels the hero on a `HERO_ATK_PERIOD` cycle.
        # Game.py sets `hero_target` each frame before update.
        self.hero_target = None
        self._hero_atk_timer: float = 0.0
        # Ranged bosses (e.g. Evil3) reach further before locking onto the hero.
        if defn.get("is_ranged"):
            self.HERO_ATK_RANGE = float(defn.get("atk_range", 250))
        else:
            self.HERO_ATK_RANGE = float(self.size) + 40.0
        self.HERO_ATK_PERIOD: float = float(defn.get("atk_period", 1.0))
        self._engaging_hero:  bool  = False  # exposed for the renderer

        # VFX queue — points where this boss landed an attack this frame
        # (game.py drains and spawns visual effects from these).
        self.is_ranged: bool = bool(defn.get("is_ranged", False))
        self._pending_vfx: list[tuple[float, float]] = []

    def is_boss(self) -> bool:
        return True

    def update(self, dt: float) -> None:
        """Boss update — prioritise smashing the hero before walking to castle."""
        if self.dead or self.reached_end:
            return

        # Hero priority — if a hero reference was assigned and the hero is
        # alive + within reach, freeze movement and bash on a fixed cadence.
        ht = self.hero_target
        if ht is not None and ht.alive:
            dx = ht.x - self.x
            dy = ht.y - self.y
            if (dx * dx + dy * dy) <= self.HERO_ATK_RANGE * self.HERO_ATK_RANGE:
                self._engaging_hero = True
                # Apply burn / slow even while engaging the hero
                if self.burn_timer > 0:
                    self.burn_timer -= dt
                    self.hp -= self.burn_dps * dt
                if self.slow_timer > 0:
                    self.slow_timer -= dt
                    if self.slow_timer <= 0:
                        self.slow_factor = 1.0
                if self.hp <= 0:
                    self.dead = True
                    return

                self._hero_atk_timer -= dt
                if self._hero_atk_timer <= 0.0:
                    self._hero_atk_timer = self.HERO_ATK_PERIOD
                    # Bosses hit the hero with a fraction of their full damage
                    ht.take_damage(self.damage * 0.5)
                    # Ranged bosses leave a VFX at the impact point so the
                    # renderer can show an explosion on top of the hero.
                    if self.is_ranged:
                        self._pending_vfx.append((float(ht.x), float(ht.y)))
                return  # skip movement while engaging

        # Hero out of range → resume normal movement / castle attack
        self._engaging_hero = False
        super().update(dt)


# ══════════════════════════════════════════════════════════════════════════════
# Projectile
# ══════════════════════════════════════════════════════════════════════════════

class Projectile:
    """A bullet / bolt / orb fired by a tower."""

    def __init__(
        self,
        x: float, y: float,
        target: Enemy,
        damage: float,
        speed:  float,
        proj_type: str,
        splash: float = 0,
        chain:  int   = 0,
    ) -> None:
        self.x, self.y   = x, y
        self.target      = target
        self.damage      = damage
        self.speed       = speed
        self.proj_type   = proj_type   # "ARROW","SHELL","BOLT","SHARD","FIREBALL"
        self.splash      = splash
        self.chain       = chain
        self.dead        = False
        self._node       = None

    def update(self, dt: float, all_enemies) -> None:
        """Move toward target; apply damage on contact."""
        if self.dead or self.target.dead:
            self.dead = True
            return

        dx = self.target.x - self.x
        dy = self.target.y - self.y
        dist = math.hypot(dx, dy)
        step = self.speed * dt

        if dist <= step + self.target.size:
            self._on_hit(all_enemies)
        else:
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step

    def _on_hit(self, all_enemies) -> None:
        self.dead = True
        if self.splash > 0:
            for e in all_enemies:
                if not e.dead:
                    if math.hypot(e.x - self.target.x, e.y - self.target.y) <= self.splash:
                        e.take_damage(self.damage)
        else:
            if not self.target.dead:
                self.target.take_damage(self.damage)


# ══════════════════════════════════════════════════════════════════════════════
# Tower base + 5 types
# ══════════════════════════════════════════════════════════════════════════════

class Tower:
    """Base class for all tower types."""

    def __init__(self, col: int, row: int, tower_type: str) -> None:
        defn = C.ALL_DEFS[tower_type]
        self.col:        int   = col
        self.row:        int   = row
        self.tower_type: str   = tower_type
        self.name:       str   = defn["name"]
        self.category:   str   = defn.get("category", "TOWER")
        self.damage:     float = defn["damage"]
        self.range:      float = defn["range"]
        self.fire_rate:  float = defn["fire_rate"]
        self.splash:     float = defn["splash"]
        self.slow:       float = defn["slow"]
        self.burn_dps:   float = defn["burn_dps"]
        self.chain:      int   = defn["chain"]
        self.cost:       int   = defn["cost"]
        self.upgrade_cost: int = defn["upgrade_cost"]
        self.level:      int   = 1
        self.hp:         float = defn["hp"]
        self.max_hp:     float = defn["hp"]

        # pixel center
        self.x: float = col * C.CELL_SIZE + C.CELL_SIZE // 2
        self.y: float = row * C.CELL_SIZE + C.CELL_SIZE // 2

        # fire cooldown
        self._cooldown: float  = 0.0
        self.target: Optional[Enemy] = None
        self.firing_angle: float = 0.0   # radians, for visual barrel direction

        # Targeting priority — switched by the player via the HUD upgrade panel.
        # Valid values: "CLOSEST", "WEAKEST", "STRONGEST".
        self.target_mode: str = "CLOSEST"

    def update(self, dt: float, enemies, projectiles_out: list) -> None:
        """
        Called each frame.  Counts down cooldown; fires when ready.
        Subclasses may override _fire() for special behaviour.
        Defensive structures (fire_rate == 0) skip targeting and use
        _update_defense() for any passive effects.
        """
        # Defensive structures — no targeting, no projectiles
        if self.fire_rate <= 0:
            self._update_defense(dt, enemies)
            return

        self._cooldown = max(0.0, self._cooldown - dt)

        # Select target via priority queue (stub: falls back to first in range)
        self.target = self._select_target(enemies)

        if self.target and self._cooldown <= 0:
            self.firing_angle = math.atan2(
                self.target.y - self.y, self.target.x - self.x
            )
            proj = self._fire(self.target)
            if proj:
                projectiles_out.append(proj)
            self._cooldown = 1.0 / (self.fire_rate * self.level)

    def _update_defense(self, dt: float, enemies) -> None:
        """Hook for defensive structures (walls, spikes, fences)."""
        return

    def _select_target(self, enemies) -> Optional[Enemy]:
        """
        Select the best target from *enemies* within range.

        Integrates with TowerTargetQueue when it is implemented.
        Falls back to a simple linear scan until then.
        """
        # --- TowerTargetQueue integration point ---
        from src.algorithms import TowerTargetQueue
        q = TowerTargetQueue(mode=self.target_mode)
        for e in enemies:
            if not e.dead and self._in_range(e):
                q.enqueue_enemy(e, self.x, self.y)
        return q.dequeue()
        # -------------------------------------------
        '''best: Optional[Enemy] = None
        best_dist = float("inf")
        for e in enemies:
            if e.dead:
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d <= self.range and d < best_dist:
                best_dist = d
                best = e
        return best'''

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: float) -> None:
        self.hp = max(0.0, self.hp - amount)

    def _in_range(self, enemy: Enemy) -> bool:
        return math.hypot(enemy.x - self.x, enemy.y - self.y) <= self.range

    def _fire(self, target: Enemy) -> Optional[Projectile]:
        """Override in subclasses for special projectile types."""
        return Projectile(
            self.x, self.y, target,
            self.damage * self.level,
            C.PROJECTILE_SPD,
            "ARROW",
        )

    def upgrade(self) -> None:
        self.level += 1
        self.damage      = C.TOWER_DEFS[self.tower_type]["damage"]      * self.level
        self.range       = C.TOWER_DEFS[self.tower_type]["range"]       * (1 + (self.level - 1) * 0.1)
        self.upgrade_cost = int(C.TOWER_DEFS[self.tower_type]["upgrade_cost"] * self.level * 1.5)


class BallistaTower(Tower):
    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "BALLISTA")

    def _fire(self, target: Enemy) -> Projectile:
        return Projectile(
            self.x, self.y, target,
            self.damage, C.PROJECTILE_SPD * 1.5,
            "ARROW",
        )


class CannonTower(Tower):
    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "CANNON")

    def _fire(self, target: Enemy) -> Projectile:
        return Projectile(
            self.x, self.y, target,
            self.damage, C.PROJECTILE_SPD * 0.7,
            "SHELL", splash=self.splash,
        )


class TeslaTower(Tower):
    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "TESLA")

    def _fire(self, target: Enemy) -> Projectile:
        return Projectile(
            self.x, self.y, target,
            self.damage, C.PROJECTILE_SPD * 2.0,
            "BOLT", chain=self.chain,
        )


class IceTower(Tower):
    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "ICE")

    def _fire(self, target: Enemy) -> Optional[Projectile]:
        target.apply_slow(1.0 - self.slow, 2.0)
        return Projectile(
            self.x, self.y, target,
            self.damage, C.PROJECTILE_SPD,
            "SHARD",
        )


class FlameTower(Tower):
    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "FLAME")

    def _fire(self, target: Enemy) -> Projectile:
        target.apply_burn(self.burn_dps, 3.0)
        return Projectile(
            self.x, self.y, target,
            self.damage, C.PROJECTILE_SPD * 0.9,
            "FIREBALL",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Defensive structures (walls, fences, spikes, barricades)
#
# All inherit from Tower so they share placement/HP/destruction logic.
# fire_rate == 0 in their config means Tower.update() short-circuits and
# delegates to _update_defense() for any passive behaviour.
# ══════════════════════════════════════════════════════════════════════════════

class WallTower(Tower):
    """Stone wall — blocks enemies, no attack."""

    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "WALL")


class FenceTower(Tower):
    """Wooden fence — cheap, low HP barrier."""

    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "FENCE")


class SpikeTower(Tower):
    """Spike trap — passively damages adjacent enemies once per second."""

    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "SPIKE")
        self._spike_cd:    float = 0.0
        self._spike_pulse: float = 0.0

    def _update_defense(self, dt: float, enemies) -> None:
        self._spike_pulse = (self._spike_pulse + dt) % 1.0
        self._spike_cd -= dt
        if self._spike_cd > 0:
            return
        self._spike_cd = 1.0
        for e in enemies:
            if e.dead:
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d <= self.range:
                e.take_damage(self.damage)


class BarricadeTower(Tower):
    """Iron barricade — heavy, expensive, very durable."""

    def __init__(self, col: int, row: int) -> None:
        super().__init__(col, row, "BARRICADE")


TOWER_CLASSES: dict[str, type] = {
    "BALLISTA":  BallistaTower,
    "CANNON":    CannonTower,
    "TESLA":     TeslaTower,
    "ICE":       IceTower,
    "FLAME":     FlameTower,
    "WALL":      WallTower,
    "FENCE":     FenceTower,
    "SPIKE":     SpikeTower,
    "BARRICADE": BarricadeTower,
}


def create_tower(col: int, row: int, tower_type: str) -> Tower:
    """Factory function — returns the correct Tower / Defense subclass."""
    return TOWER_CLASSES[tower_type](col, row)


# ══════════════════════════════════════════════════════════════════════════════
# FishPond
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# Hero  (player-controlled character)
# ══════════════════════════════════════════════════════════════════════════════

class Hero:
    """
    Player-controlled knight.

    Movement   : WASD / arrow keys.  Holding Shift sprints at
                 HERO_SPRINT_MULT× speed while stamina is available.
    Attack 1   : left-click → instant strike on the closest enemy in
                 HERO_ATTACK_RANGE; cooldown 1 / HERO_ATTACK_RATE.
    Attack 2   : right-click held → charges up; on release stuns + knocks
                 back enemies inside the cone toward the cursor.  5 s cd.
    Upgrades   : `apply_upgrade(kind)` bumps HP / armor / speed / damage.
    """

    def __init__(self) -> None:
        self.x: float    = C.HERO_START_X
        self.y: float    = C.HERO_START_Y
        self.hp: float   = float(C.HERO_HP_MAX)
        self.max_hp: float = float(C.HERO_HP_MAX)
        self.alive: bool = True
        self.facing_angle: float = 0.0
        self._attack_cd: float   = 0.0           # Attack1 cooldown
        self.last_attacked: Optional[Enemy] = None

        # ── Upgrade-driven stats (mutated by apply_upgrade) ───────────────
        self.armor:        int   = 0
        self.base_speed:   float = float(C.HERO_SPEED)
        self.atk1_damage:  float = float(C.HERO_ATK1_DAMAGE)
        # Tier counter per upgrade kind (HP/ARMOR/SPEED/DAMAGE)
        self.upgrades: dict[str, int] = {k: 0 for k in C.HERO_UPGRADE_DEFS}

        # ── Sprint / stamina ──────────────────────────────────────────────
        self.stamina: float           = float(C.HERO_STAMINA_MAX)
        self.sprinting: bool          = False    # exposed flag for renderer
        self._stamina_idle_t: float   = 0.0      # seconds since last sprint
        self._stamina_locked: bool    = False    # True until refilled

        # ── Attack2 charge state ──────────────────────────────────────────
        self.attack2_cd: float        = 0.0
        self.attack2_cd_max: float    = 0.0      # duration of latest cooldown
        self.attack2_charging: bool   = False
        self.attack2_charge_t: float  = 0.0
        # Swing-animation countdown (seconds remaining).  Game sets this on
        # release; Hero.update ticks it down so the renderer can simply
        # check `attack2_anim_t > 0` without comparing two different clocks.
        self.attack2_anim_t: float    = 0.0
        self.attack2_anim_window: float = 0.0    # original window for ratio calc

        # ── Block (E key) ────────────────────────────────────────────────
        self.block_active: bool       = False
        self.block_hold_t: float      = 0.0      # seconds the guard has been held
        self.block_dmg_taken: float   = 0.0      # raw post-armor dmg accumulated
        self.block_cd: float          = 0.0
        self.block_cd_max: float      = 0.0      # duration of latest cooldown

    # ── Update ────────────────────────────────────────────────────────────

    def update(self, dt: float, keys) -> None:
        if not self.alive:
            return

        # While blocking, freeze movement and sprint completely.
        if self.block_active:
            dx, dy = 0.0, 0.0
            self.sprinting = False
        else:
            dx, dy = 0.0, 0.0
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                dy -= 1.0
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dy += 1.0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx -= 1.0
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx += 1.0

        moving = (dx != 0.0 or dy != 0.0)

        # Sprint when Shift is held + we're moving + stamina is available.
        sprint_held = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        wants_sprint = (sprint_held and moving
                        and self.stamina > 0.0
                        and not self._stamina_locked
                        and not self.block_active)
        self.sprinting = bool(wants_sprint)
        speed = self.base_speed * (C.HERO_SPRINT_MULT if wants_sprint else 1.0)

        if moving:
            mag = math.hypot(dx, dy)
            self.x += (dx / mag) * speed * dt
            self.y += (dy / mag) * speed * dt
            self.facing_angle = math.atan2(dy, dx)

        # Stamina drain / regen
        if wants_sprint:
            self.stamina = max(0.0, self.stamina - dt)
            self._stamina_idle_t = 0.0
            if self.stamina <= 0.0:
                self._stamina_locked = True
        else:
            self._stamina_idle_t += dt
            if self._stamina_idle_t >= C.HERO_STAMINA_REGEN_DELAY:
                self.stamina = min(C.HERO_STAMINA_MAX,
                                    self.stamina + C.HERO_STAMINA_REGEN_RATE * dt)
                if self.stamina >= C.HERO_STAMINA_MAX:
                    self._stamina_locked = False

        # Stay inside the game world
        self.x = max(12.0, min(C.GAME_WIDTH - 12.0, self.x))
        self.y = max(12.0, min(C.SCREEN_HEIGHT - 12.0, self.y))

        # Attack timers
        self._attack_cd = max(0.0, self._attack_cd - dt)
        self.attack2_cd = max(0.0, self.attack2_cd - dt)
        self.attack2_anim_t = max(0.0, self.attack2_anim_t - dt)
        if self.attack2_charging:
            self.attack2_charge_t += dt

        # Block timers + auto-cancel triggers
        self.block_cd = max(0.0, self.block_cd - dt)
        if self.block_active:
            self.block_hold_t += dt
            if (self.block_hold_t >= C.HERO_BLOCK_HOLD_MAX_S
                    or self.block_dmg_taken >= C.HERO_BLOCK_RAW_BREAK
                    or not self.alive):
                self._end_block()

    # ── Attack 1 (manual left-click swing) ────────────────────────────────

    def try_attack(self, enemies: list) -> bool:
        """Single Attack1 swing.  Returns True if a hit landed."""
        if self._attack_cd > 0 or not self.alive or self.block_active:
            return False
        best: Optional[Enemy] = None
        best_dist = float("inf")
        for e in enemies:
            if e.dead:
                continue
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d <= C.HERO_ATTACK_RANGE and d < best_dist:
                best_dist = d
                best = e
        if best is not None:
            best.take_damage(self.atk1_damage)
            self.last_attacked = best
            self.facing_angle  = math.atan2(best.y - self.y, best.x - self.x)
            self._attack_cd    = 1.0 / C.HERO_ATTACK_RATE
            return True
        # Empty swing still consumes the cooldown so spam-clicking has cost
        self._attack_cd = 1.0 / C.HERO_ATTACK_RATE
        return False

    # ── Attack 2 (charged stun + knockback) ──────────────────────────────

    def begin_attack2_charge(self) -> bool:
        """Start charging the right-click attack.  Returns False if on cd."""
        if (not self.alive or self.attack2_cd > 0
                or self.attack2_charging or self.block_active):
            return False
        self.attack2_charging = True
        self.attack2_charge_t = 0.0
        return True

    def cancel_attack2_charge(self) -> None:
        self.attack2_charging = False
        self.attack2_charge_t = 0.0

    # ── Block (E key) ─────────────────────────────────────────────────────

    def begin_block(self) -> bool:
        """Try to raise the guard.  False if on cd / already up / not alive
        / mid-Attack2 charge."""
        if (not self.alive
                or self.block_cd > 0.0
                or self.block_active
                or self.attack2_charging):
            return False
        self.block_active    = True
        self.block_hold_t    = 0.0
        self.block_dmg_taken = 0.0
        return True

    def end_block(self) -> None:
        """Player-initiated release of E."""
        if self.block_active:
            self._end_block()

    def _end_block(self) -> None:
        """End-of-guard: cooldown scales linearly with how long it was held."""
        held  = self.block_hold_t
        ratio = max(0.0, min(1.0, held / max(0.001, C.HERO_BLOCK_HOLD_MAX_S)))
        cd    = C.HERO_BLOCK_COOLDOWN_MIN + ratio * (
            C.HERO_BLOCK_COOLDOWN_MAX - C.HERO_BLOCK_COOLDOWN_MIN
        )
        self.block_active = False
        self.block_hold_t = 0.0
        self.block_cd     = cd
        self.block_cd_max = cd

    def take_damage(self, amount: float) -> None:
        if not self.alive:
            return
        # Armor flat-reduces damage but a hit always lands for ≥ 1 hp
        net = max(1.0, float(amount) - float(self.armor))
        # Block absorbs a flat share of post-armor net dmg.  The raw post-armor
        # value also drives the auto-cancel threshold (user spec: 'total
        # incoming damage ≥ 200').  Auto-cancel itself fires on the next
        # update() tick if this hit pushes the counter over the limit.
        if self.block_active:
            self.block_dmg_taken += net
            net = net * (1.0 - C.HERO_BLOCK_ABSORB_FRACTION)
        self.hp -= net
        if self.hp <= 0:
            self.hp    = 0.0
            self.alive = False
            # Hero.update() early-returns on death, so the block auto-cancel
            # there never fires for a killing blow.  Clear the guard now so
            # the renderer / state machine don't get stuck in TAKE_HIT.
            if self.block_active:
                self._end_block()

    def healing(self):
        if self.hp < self.max_hp:
            self.hp += 2

    # ── Upgrades ──────────────────────────────────────────────────────────

    def apply_upgrade(self, kind: str) -> bool:
        """Bump the tier for one upgrade category and rewrite the stat.

        Returns False if `kind` is unknown or the upgrade is already at max.
        """
        defn = C.HERO_UPGRADE_DEFS.get(kind)
        if defn is None:
            return False
        cur = self.upgrades.get(kind, 0)
        if cur >= defn["max_tier"]:
            return False
        self.upgrades[kind] = cur + 1
        step  = float(defn["step"])
        stat  = defn["stat"]
        if stat == "max_hp":
            self.max_hp += step
            self.hp     += step                # bonus hp granted up-front
        elif stat == "armor":
            self.armor += int(step)
        elif stat == "base_speed":
            self.base_speed += step
        elif stat == "atk1_damage":
            self.atk1_damage += step
        return True


class FishPond:
    """
    Fishing pond with a probabilistic appearance rate.

    The cooldown system is gone — instead, every time the player presses the
    "Cast" button a single roll against `current_rate` decides whether a fish
    appears.  If it does, the click-timing minigame in src/fishing.py runs to
    decide whether the player actually lands it.

    Rate management:
        feed()     — +FISH_RATE_FEED_BONUS, capped at FISH_RATE_MAX.
                     Resets the decay timer.
        update(dt) — accumulates time since the last feed; every
                     FISH_RATE_DECAY_INTERVAL seconds the rate drops by
                     FISH_RATE_DECAY_AMOUNT, floored at FISH_RATE_MIN, and
                     the timer rolls over.
    """

    def __init__(self) -> None:
        rx, ry, rw, rh = C.POND_RECT
        self.x, self.y = rx, ry
        self.w, self.h = rw, rh
        self.cx = rx + rw // 2
        self.cy = ry + rh // 2

        self.current_rate: float = C.FISH_RATE_INITIAL
        self.decay_timer: float = 0.0   # seconds since last feed (or last decay tick)

    # ── Update / interaction ─────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Tick the decay timer and apply −FISH_RATE_DECAY_AMOUNT every interval."""
        if self.current_rate <= C.FISH_RATE_MIN:
            # Already at floor; keep timer pinned so a feed re-arms cleanly.
            self.decay_timer = 0.0
            return

        self.decay_timer += dt
        while self.decay_timer >= C.FISH_RATE_DECAY_INTERVAL:
            self.decay_timer -= C.FISH_RATE_DECAY_INTERVAL
            self.current_rate = max(
                C.FISH_RATE_MIN,
                self.current_rate - C.FISH_RATE_DECAY_AMOUNT,
            )
            if self.current_rate <= C.FISH_RATE_MIN:
                self.decay_timer = 0.0
                break

    def feed(self) -> None:
        """Apply one fish-food bonus and reset the decay timer."""
        self.current_rate = min(
            C.FISH_RATE_MAX,
            self.current_rate + C.FISH_RATE_FEED_BONUS,
        )
        self.decay_timer = 0.0

    def contains(self, mx: int, my: int) -> bool:
        """Return True if the pixel coordinate (mx, my) falls inside the pond rect."""
        return self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h


# ══════════════════════════════════════════════════════════════════════════════
# Shop
# ══════════════════════════════════════════════════════════════════════════════

class Shop:
    def __init__(self) -> None:
        rx, ry, rw, rh = C.SHOP_RECT
        self.x, self.y = rx, ry
        self.w, self.h = rw, rh
        self.cx = rx + rw // 2
        self.cy = ry + rh // 2

    def sell_inventory_fish(self, inventory) -> int:
        """Sell every fish item in the inventory at its per-item price.

        Returns the total gold earned.  Empties FISH_COMMON / FISH_RARE stacks.
        """
        total = 0
        for item_id in ("FISH_COMMON", "FISH_RARE"):
            count = inventory.count(item_id)
            if count <= 0:
                continue
            price = C.ITEM_DEFS[item_id].get("sell_price", 0)
            total += count * price
            inventory.clear_item(item_id)
        return total

    def contains(self, mx: int, my: int) -> bool:
        """Return True if the pixel coordinate (mx, my) falls inside the shop rect."""
        return self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h
