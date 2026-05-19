"""
Combat AI – Tactics, Detection, and Morale
==========================================
Models the NavMesh-based combat logic used by Fallout 4's Radiant AI engine:

* **Detection States** – Hidden → Caution → Danger, driven by visibility,
  light level, and noise.
* **Tactical decisions** – Cover-seeking, flanking, and high-ground preference
  using a simple grid-based NavMesh representation.
* **Morale system** – Faction cohesion tracking; triggers a flee package when
  group health drops below a threshold or the leader is killed.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DetectionState(Enum):
    """Awareness levels tracked by the engine for each NPC."""
    HIDDEN = auto()
    CAUTION = auto()
    DANGER = auto()


class CoverType(Enum):
    """Classification of a NavMesh node as a tactical position."""
    OPEN = auto()       # No protection
    LOW_COVER = auto()  # Partial protection (crouching)
    HIGH_COVER = auto() # Full protection while standing
    HIGH_GROUND = auto()# Elevation advantage


# ---------------------------------------------------------------------------
# NavMesh primitives
# ---------------------------------------------------------------------------


@dataclass
class NavNode:
    """A single node in the navigable mesh grid.

    Parameters
    ----------
    x, y:
        Grid coordinates.
    elevation:
        Height in arbitrary units; higher = elevated advantage.
    cover_type:
        Tactical classification of this node.
    is_walkable:
        *False* for geometry-blocked tiles.
    """

    x: int
    y: int
    elevation: float = 0.0
    cover_type: CoverType = CoverType.OPEN
    is_walkable: bool = True


@dataclass
class NavMesh:
    """A simple grid-based navigable mesh.

    In Fallout 4 the engine bakes a NavMesh into each cell at authoring time.
    This class simulates that structure with a dictionary of :class:`NavNode`
    objects keyed by ``(x, y)`` grid coordinates.
    """

    nodes: Dict[Tuple[int, int], NavNode] = field(default_factory=dict)

    def add_node(self, node: NavNode) -> None:
        self.nodes[(node.x, node.y)] = node

    def get_node(self, x: int, y: int) -> Optional[NavNode]:
        return self.nodes.get((x, y))

    def neighbors(self, x: int, y: int) -> List[NavNode]:
        """Return walkable adjacent nodes (4-directional)."""
        result = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            node = self.nodes.get((x + dx, y + dy))
            if node and node.is_walkable:
                result.append(node)
        return result

    def find_cover_nodes(self) -> List[NavNode]:
        """Return all nodes that offer any cover."""
        return [n for n in self.nodes.values() if n.cover_type != CoverType.OPEN]

    def find_high_ground(self) -> List[NavNode]:
        """Return nodes classified as elevated positions."""
        return [n for n in self.nodes.values() if n.cover_type == CoverType.HIGH_GROUND]


# ---------------------------------------------------------------------------
# NPC combat representation
# ---------------------------------------------------------------------------


@dataclass
class CombatantNPC:
    """An NPC involved in a firefight.

    Parameters
    ----------
    npc_id:
        Unique identifier (e.g. editor ID).
    faction:
        Faction name used for morale grouping.
    max_health:
        Total health points.
    health:
        Current health points.
    position:
        Current ``(x, y)`` grid position on the NavMesh.
    is_leader:
        *True* for the faction's named leader; killing them impacts morale.
    detection_state:
        Current awareness of the player/enemy.
    """

    npc_id: str
    faction: str
    max_health: float
    health: float
    position: Tuple[int, int] = (0, 0)
    is_leader: bool = False
    detection_state: DetectionState = DetectionState.HIDDEN
    is_fleeing: bool = field(default=False, init=False)

    @property
    def health_fraction(self) -> float:
        return self.health / self.max_health if self.max_health > 0 else 0.0

    @property
    def is_alive(self) -> bool:
        return self.health > 0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class DetectionSystem:
    """Simulates Fallout 4's layered NPC awareness system.

    The engine advances awareness toward *Danger* as visibility and noise
    increase, and retreats toward *Hidden* as both factors decrease.

    Parameters
    ----------
    visibility_threshold:
        Visibility score (0–1) above which NPC transitions to CAUTION.
    danger_threshold:
        Combined score above which NPC escalates to DANGER.
    """

    def __init__(
        self,
        visibility_threshold: float = 0.3,
        danger_threshold: float = 0.6,
    ) -> None:
        self.visibility_threshold = visibility_threshold
        self.danger_threshold = danger_threshold

    def evaluate(
        self,
        npc: CombatantNPC,
        visibility: float,
        light_level: float,
        noise: float,
    ) -> DetectionState:
        """Compute and set the new :class:`DetectionState` for *npc*.

        Parameters
        ----------
        visibility:
            Line-of-sight score in [0, 1]; 1.0 = fully in the open.
        light_level:
            Ambient brightness in [0, 1]; 1.0 = broad daylight.
        noise:
            Noise contribution in [0, 1]; 1.0 = extremely loud.

        Returns
        -------
        DetectionState
            The resulting awareness level (also stored on *npc*).
        """
        if not (0.0 <= visibility <= 1.0 and 0.0 <= light_level <= 1.0 and 0.0 <= noise <= 1.0):
            raise ValueError("visibility, light_level, and noise must be in [0, 1].")

        combined_score = visibility * light_level + noise * 0.5

        if combined_score >= self.danger_threshold:
            new_state = DetectionState.DANGER
        elif combined_score >= self.visibility_threshold:
            new_state = DetectionState.CAUTION
        else:
            new_state = DetectionState.HIDDEN

        npc.detection_state = new_state
        return new_state


# ---------------------------------------------------------------------------
# Morale
# ---------------------------------------------------------------------------


class MoraleSystem:
    """Tracks faction-wide morale and triggers flee behaviour.

    Parameters
    ----------
    flee_health_threshold:
        Faction average health fraction below which survivors flee.
    """

    def __init__(self, flee_health_threshold: float = 0.25) -> None:
        self.flee_health_threshold = flee_health_threshold

    def evaluate_faction(self, combatants: List[CombatantNPC]) -> bool:
        """Check morale for a group sharing the same faction.

        Returns *True* (flee triggered) when either:

        * The faction's **leader** has been killed, or
        * The **average health fraction** of survivors drops below the
          configured threshold.

        All surviving members are flagged ``is_fleeing = True`` when the
        condition is met.
        """
        alive = [c for c in combatants if c.is_alive]
        if not alive:
            return False

        leader_dead = any(c.is_leader and not c.is_alive for c in combatants)

        avg_health = sum(c.health_fraction for c in alive) / len(alive)
        low_health = avg_health < self.flee_health_threshold

        should_flee = leader_dead or low_health
        if should_flee:
            for c in alive:
                c.is_fleeing = True

        return should_flee


# ---------------------------------------------------------------------------
# Main Combat AI controller
# ---------------------------------------------------------------------------


class CombatAI:
    """High-level combat AI controller.

    Combines the :class:`DetectionSystem`, :class:`MoraleSystem`, and
    NavMesh-aware tactical positioning into a single per-tick API.

    Usage
    -----
    >>> mesh = NavMesh()
    >>> mesh.add_node(NavNode(0, 0))
    >>> mesh.add_node(NavNode(1, 0, cover_type=CoverType.HIGH_COVER))
    >>> ai = CombatAI(mesh)
    >>> npc = CombatantNPC("raider_01", "Raiders", 100, 80, position=(0, 0))
    >>> cover_node = ai.seek_cover(npc)
    >>> cover_node.cover_type
    <CoverType.HIGH_COVER: 3>
    """

    def __init__(
        self,
        navmesh: NavMesh,
        flee_health_threshold: float = 0.25,
        visibility_threshold: float = 0.3,
        danger_threshold: float = 0.6,
    ) -> None:
        self.navmesh = navmesh
        self._detection = DetectionSystem(visibility_threshold, danger_threshold)
        self._morale = MoraleSystem(flee_health_threshold)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def update_detection(
        self,
        npc: CombatantNPC,
        visibility: float,
        light_level: float,
        noise: float,
    ) -> DetectionState:
        """Delegate to :class:`DetectionSystem` and return the new state."""
        return self._detection.evaluate(npc, visibility, light_level, noise)

    # ------------------------------------------------------------------
    # Tactical positioning
    # ------------------------------------------------------------------

    def seek_cover(self, npc: CombatantNPC) -> Optional[NavNode]:
        """Return the nearest reachable cover node from the NPC's position.

        Prefers ``HIGH_COVER`` over ``LOW_COVER``; falls back to any cover
        node reachable via the NavMesh.  Returns *None* if no cover exists.
        """
        cover_nodes = self.navmesh.find_cover_nodes()
        if not cover_nodes:
            return None

        def _distance(node: NavNode) -> float:
            nx, ny = npc.position
            return math.hypot(node.x - nx, node.y - ny)

        # Sort by cover quality first, then proximity
        cover_priority = {
            CoverType.HIGH_COVER: 0,
            CoverType.LOW_COVER:  1,
            CoverType.HIGH_GROUND: 0,
            CoverType.OPEN: 99,
        }
        cover_nodes.sort(key=lambda n: (cover_priority[n.cover_type], _distance(n)))
        best = cover_nodes[0]
        npc.position = (best.x, best.y)
        return best

    def attempt_flank(
        self,
        attacker: CombatantNPC,
        target_position: Tuple[int, int],
    ) -> Optional[NavNode]:
        """Move *attacker* to a node that is neither visible nor adjacent to
        *target_position* (simulating a flanking manoeuvre).

        Returns the chosen flanking node, or *None* if none is available.
        """
        tx, ty = target_position
        candidates = [
            n for n in self.navmesh.nodes.values()
            if n.is_walkable
            and (abs(n.x - tx) > 1 or abs(n.y - ty) > 1)
        ]
        if not candidates:
            return None

        # Prefer nodes that provide cover while flanking
        cover_candidates = [n for n in candidates if n.cover_type != CoverType.OPEN]
        pool = cover_candidates if cover_candidates else candidates
        chosen = random.choice(pool)
        attacker.position = (chosen.x, chosen.y)
        return chosen

    # ------------------------------------------------------------------
    # Morale
    # ------------------------------------------------------------------

    def evaluate_morale(self, combatants: List[CombatantNPC]) -> bool:
        """Delegate to :class:`MoraleSystem`.

        Returns *True* when the faction breaks and starts fleeing.
        """
        return self._morale.evaluate_faction(combatants)
