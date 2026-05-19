"""
Daily Life Routines – AI Package Scheduler
==========================================
Models the NPC daily-schedule system (AI Packages) from Fallout 4's Radiant AI
engine.  Each NPC is assigned an ordered list of :class:`AIPackage` entries.
The scheduler evaluates the list every game-hour tick and activates the
highest-priority package whose time/location conditions are satisfied.

When no package matches, the NPC enters *sandbox* mode and the
:class:`SandboxBehaviour` module picks an ambient interaction from the objects
available at the NPC's current location.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PackageType(Enum):
    """The broad category of an AI Package."""
    SLEEP = auto()
    WORK = auto()
    EAT = auto()
    RELAX = auto()
    PATROL = auto()
    SANDBOX = auto()


class Location(Enum):
    """Named in-world locations an NPC or package can reference."""
    BED = auto()
    CROP_FIELD = auto()
    BAR = auto()
    WORKBENCH = auto()
    PATROL_ROUTE = auto()
    ANYWHERE = auto()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AIPackage:
    """A single AI Package entry as stored in the game's package stack.

    Parameters
    ----------
    package_type:
        What the NPC will do when this package is active.
    start_hour:
        In-game hour (0–23) at which the package becomes eligible.
    end_hour:
        In-game hour (0–23, exclusive) at which the package expires.
    location:
        Where the NPC must be (or travel to) to execute this package.
    priority:
        Lower numbers are evaluated first (0 = highest priority).
    """

    package_type: PackageType
    start_hour: int
    end_hour: int
    location: Location
    priority: int = 10

    def is_active(self, current_hour: int) -> bool:
        """Return *True* when *current_hour* falls within the package window."""
        if self.start_hour <= self.end_hour:
            return self.start_hour <= current_hour < self.end_hour
        # Wraps midnight (e.g. 22:00 – 06:00)
        return current_hour >= self.start_hour or current_hour < self.end_hour


@dataclass
class NPC:
    """Represents a non-player character with a schedule and location."""

    name: str
    packages: List[AIPackage] = field(default_factory=list)
    current_location: Location = Location.ANYWHERE
    active_package: Optional[AIPackage] = field(default=None, init=False)

    def add_package(self, package: AIPackage) -> None:
        """Append an AI Package to this NPC's stack."""
        self.packages.append(package)
        self.packages.sort(key=lambda p: p.priority)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class AIPackageScheduler:
    """Evaluates an NPC's package stack each game-hour and activates the
    highest-priority eligible package.

    Usage
    -----
    >>> scheduler = AIPackageScheduler()
    >>> npc = NPC("Settler")
    >>> npc.add_package(AIPackage(PackageType.SLEEP, 22, 6, Location.BED, priority=0))
    >>> npc.add_package(AIPackage(PackageType.WORK, 7, 18, Location.CROP_FIELD, priority=1))
    >>> result = scheduler.tick(npc, current_hour=8)
    >>> result.package_type
    <PackageType.WORK: 2>
    """

    def tick(self, npc: NPC, current_hour: int) -> Optional[AIPackage]:
        """Evaluate packages for *npc* at *current_hour*.

        Returns the activated :class:`AIPackage`, or *None* when sandbox mode
        takes over.
        """
        if not 0 <= current_hour <= 23:
            raise ValueError(f"current_hour must be 0–23, got {current_hour}")

        for pkg in npc.packages:
            if pkg.is_active(current_hour):
                npc.active_package = pkg
                npc.current_location = pkg.location
                return pkg

        # No package matched → fall through to sandbox
        npc.active_package = None
        return None

    @staticmethod
    def build_settler_schedule(name: str) -> NPC:
        """Return a pre-built :class:`NPC` with a typical settler routine."""
        npc = NPC(name)
        npc.add_package(AIPackage(PackageType.SLEEP,  22, 6,  Location.BED,          priority=0))
        npc.add_package(AIPackage(PackageType.EAT,    6,  8,  Location.BAR,          priority=1))
        npc.add_package(AIPackage(PackageType.WORK,   8,  18, Location.CROP_FIELD,   priority=2))
        npc.add_package(AIPackage(PackageType.RELAX,  18, 22, Location.BAR,          priority=3))
        return npc

    @staticmethod
    def build_guard_schedule(name: str) -> NPC:
        """Return a pre-built :class:`NPC` with a day/night guard rotation."""
        npc = NPC(name)
        npc.add_package(AIPackage(PackageType.PATROL, 6,  18, Location.PATROL_ROUTE, priority=0))
        npc.add_package(AIPackage(PackageType.SLEEP,  18, 6,  Location.BED,          priority=1))
        return npc


# ---------------------------------------------------------------------------
# Sandbox Behaviour
# ---------------------------------------------------------------------------


_AMBIENT_OBJECTS = [
    "chair",
    "sweeping_broom",
    "cooking_station",
    "workbench",
    "wall_to_lean_on",
    "barrel_to_inspect",
]


class SandboxBehaviour:
    """Picks a random ambient interaction for an NPC in sandbox mode.

    When no AI Package is active the engine lets NPCs wander inside a defined
    radius and interact with nearby objects.  This class simulates that logic.
    """

    def __init__(self, available_objects: Optional[List[str]] = None) -> None:
        self._objects = available_objects if available_objects is not None else list(_AMBIENT_OBJECTS)

    def pick_interaction(self, npc: NPC) -> str:
        """Return a string describing the ambient interaction chosen for *npc*.

        Raises ``RuntimeError`` when the NPC has no available ambient objects.
        """
        if not self._objects:
            raise RuntimeError(f"{npc.name} has no ambient objects available for sandbox.")
        chosen = random.choice(self._objects)
        return f"{npc.name} is interacting with: {chosen}"

    def add_object(self, obj: str) -> None:
        """Register an additional ambient object in this sandbox zone."""
        self._objects.append(obj)
