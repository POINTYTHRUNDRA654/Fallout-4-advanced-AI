"""
Radiant Quest Generation
========================
Models the *Radiant* quest director from Fallout 4, which procedurally
assembles repeatable side-quests by filling template slots with context-aware
game-state data:

* **Target Location** – an uncleared dungeon appropriate for the player's level.
* **Hostile Faction** – enemy type spawned at the destination.
* **Kidnapped Target** – a settler chosen from the player's established bases.

The :class:`RadiantQuestDirector` exposes a single :meth:`generate_quest` entry
point that returns a fully populated :class:`RadiantQuest` instance.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class HostileFaction(Enum):
    """Enemy factions that can be assigned to a radiant quest site."""
    RAIDERS = auto()
    SUPER_MUTANTS = auto()
    GHOULS = auto()
    GUNNERS = auto()
    INSTITUTE = auto()


class QuestType(Enum):
    """The high-level goal template for a radiant quest."""
    RESCUE_SETTLER = auto()    # Recover a kidnapped settler
    CLEAR_LOCATION = auto()    # Wipe out enemies at a dungeon
    SUPPLY_RUN = auto()        # Retrieve a resource from a hostile site


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Location:
    """A game-world location usable as a quest target.

    Parameters
    ----------
    name:
        Human-readable location name (e.g. "Corvega Assembly Plant").
    min_level:
        Minimum recommended player level.
    max_level:
        Maximum recommended player level (inclusive).
    is_cleared:
        *True* once the player has already completed this location.
    """

    name: str
    min_level: int
    max_level: int
    is_cleared: bool = False


@dataclass
class Settler:
    """Represents a settler living in one of the player's settlements."""

    name: str
    settlement: str
    is_available: bool = True


@dataclass
class RadiantQuest:
    """A fully resolved radiant quest instance.

    All slots are populated by :class:`RadiantQuestDirector`.
    """

    quest_type: QuestType
    target_location: Location
    hostile_faction: HostileFaction
    kidnapped_settler: Optional[Settler] = None
    description: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.description = self._build_description()

    def _build_description(self) -> str:
        if self.quest_type == QuestType.RESCUE_SETTLER:
            settler_name = self.kidnapped_settler.name if self.kidnapped_settler else "a settler"
            return (
                f"{self.hostile_faction.name.replace('_', ' ').title()} have kidnapped "
                f"{settler_name} and are holding them at {self.target_location.name}. "
                f"Rescue them!"
            )
        if self.quest_type == QuestType.CLEAR_LOCATION:
            return (
                f"A group of {self.hostile_faction.name.replace('_', ' ').title()} "
                f"has taken over {self.target_location.name}. Clear them out."
            )
        return (
            f"Retrieve supplies from {self.target_location.name}, "
            f"currently occupied by {self.hostile_faction.name.replace('_', ' ').title()}."
        )


# ---------------------------------------------------------------------------
# Director
# ---------------------------------------------------------------------------


class RadiantQuestDirector:
    """Generates radiant quests by analysing game state and filling template
    slots with contextually appropriate values.

    Parameters
    ----------
    locations:
        Pool of available world locations.
    settlers:
        All settlers across the player's settlements.
    player_level:
        Current player level, used to filter appropriate locations.
    faction_weights:
        Optional mapping of :class:`HostileFaction` → relative spawn weight.
        Defaults to equal weighting across all factions.
    """

    def __init__(
        self,
        locations: List[Location],
        settlers: List[Settler],
        player_level: int,
        faction_weights: Optional[Dict[HostileFaction, float]] = None,
    ) -> None:
        if player_level < 1:
            raise ValueError("player_level must be at least 1.")
        self.locations = locations
        self.settlers = settlers
        self.player_level = player_level
        self._faction_weights: Dict[HostileFaction, float] = faction_weights or {
            f: 1.0 for f in HostileFaction
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_quest(self, quest_type: Optional[QuestType] = None) -> RadiantQuest:
        """Build and return a :class:`RadiantQuest`.

        Parameters
        ----------
        quest_type:
            Force a specific quest template.  If *None*, one is chosen at
            random weighted by available game state (e.g. ``RESCUE_SETTLER``
            requires available settlers).

        Raises
        ------
        RuntimeError
            When no eligible location exists for the player's current level.
        """
        target = self._pick_location()
        faction = self._pick_faction()
        resolved_type = quest_type or self._pick_quest_type()
        settler: Optional[Settler] = None

        if resolved_type == QuestType.RESCUE_SETTLER:
            settler = self._pick_settler()
            if settler is not None:
                settler.is_available = False
            else:
                # No available settler → fall back to clear quest
                resolved_type = QuestType.CLEAR_LOCATION

        return RadiantQuest(
            quest_type=resolved_type,
            target_location=target,
            hostile_faction=faction,
            kidnapped_settler=settler,
        )

    # ------------------------------------------------------------------
    # Slot-filler helpers
    # ------------------------------------------------------------------

    def _pick_location(self) -> Location:
        """Return an uncleared location suited to *player_level*."""
        eligible = [
            loc for loc in self.locations
            if not loc.is_cleared
            and loc.min_level <= self.player_level <= loc.max_level
        ]
        if not eligible:
            raise RuntimeError(
                f"No eligible locations found for player level {self.player_level}. "
                "Add more locations or adjust player_level."
            )
        return random.choice(eligible)

    def _pick_faction(self) -> HostileFaction:
        """Weighted-random selection of a hostile faction."""
        factions = list(self._faction_weights.keys())
        weights = [self._faction_weights[f] for f in factions]
        return random.choices(factions, weights=weights, k=1)[0]

    def _pick_quest_type(self) -> QuestType:
        """Choose a quest type, favouring rescue when settlers are available."""
        available_settlers = [s for s in self.settlers if s.is_available]
        if available_settlers:
            return random.choice([QuestType.RESCUE_SETTLER, QuestType.CLEAR_LOCATION, QuestType.SUPPLY_RUN])
        return random.choice([QuestType.CLEAR_LOCATION, QuestType.SUPPLY_RUN])

    def _pick_settler(self) -> Optional[Settler]:
        """Return a random available settler, or *None*."""
        candidates = [s for s in self.settlers if s.is_available]
        return random.choice(candidates) if candidates else None

    # ------------------------------------------------------------------
    # Convenience factory
    # ------------------------------------------------------------------

    @classmethod
    def default_commonwealth(cls, player_level: int) -> "RadiantQuestDirector":
        """Create a director pre-populated with Commonwealth locations and
        a handful of settlers – useful for quick testing and demonstrations.
        """
        locations = [
            Location("Corvega Assembly Plant",  5,  20),
            Location("Dunwich Borers",          20, 50),
            Location("Fort Hagen",              10, 30),
            Location("Mass Fusion Building",    15, 40),
            Location("Medford Memorial Hospital", 10, 35),
            Location("Quincy Ruins",            25, 50),
            Location("Revere Satellite Array",  15, 35),
            Location("Satellite Station Olivia", 1, 10),
            Location("Libertalia",              20, 45),
            Location("Rotten Landfill",          5, 25),
        ]
        settlers = [
            Settler("Jun Long",    "Sanctuary Hills"),
            Settler("Marcy Long",  "Sanctuary Hills"),
            Settler("Sturges",     "Sanctuary Hills"),
            Settler("Codsworth",   "Sanctuary Hills"),
            Settler("Gracie",      "Abernathy Farm"),
            Settler("Blake",       "Abernathy Farm"),
        ]
        return cls(locations=locations, settlers=settlers, player_level=player_level)
