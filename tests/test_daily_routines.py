"""
Tests for daily_routines.py
"""

import pytest
from src.ai.daily_routines import (
    AIPackage,
    AIPackageScheduler,
    Location,
    NPC,
    PackageType,
    SandboxBehaviour,
)


# ---------------------------------------------------------------------------
# AIPackage.is_active
# ---------------------------------------------------------------------------


class TestAIPackageIsActive:
    def test_within_window(self):
        pkg = AIPackage(PackageType.WORK, 8, 18, Location.CROP_FIELD)
        assert pkg.is_active(8) is True
        assert pkg.is_active(12) is True
        assert pkg.is_active(17) is True

    def test_outside_window(self):
        pkg = AIPackage(PackageType.WORK, 8, 18, Location.CROP_FIELD)
        assert pkg.is_active(7) is False
        assert pkg.is_active(18) is False
        assert pkg.is_active(23) is False

    def test_midnight_wrapping_package(self):
        # 22:00 – 06:00 (wraps midnight)
        pkg = AIPackage(PackageType.SLEEP, 22, 6, Location.BED)
        assert pkg.is_active(22) is True
        assert pkg.is_active(0) is True
        assert pkg.is_active(5) is True
        assert pkg.is_active(6) is False
        assert pkg.is_active(12) is False

    def test_exact_boundary_excluded(self):
        pkg = AIPackage(PackageType.EAT, 6, 8, Location.BAR)
        assert pkg.is_active(6) is True
        assert pkg.is_active(8) is False


# ---------------------------------------------------------------------------
# AIPackageScheduler.tick
# ---------------------------------------------------------------------------


class TestAIPackageSchedulerTick:
    def _make_scheduler_and_npc(self):
        scheduler = AIPackageScheduler()
        npc = NPC("TestSettler")
        npc.add_package(AIPackage(PackageType.SLEEP, 22, 6, Location.BED, priority=0))
        npc.add_package(AIPackage(PackageType.EAT, 6, 8, Location.BAR, priority=1))
        npc.add_package(AIPackage(PackageType.WORK, 8, 18, Location.CROP_FIELD, priority=2))
        npc.add_package(AIPackage(PackageType.RELAX, 18, 22, Location.BAR, priority=3))
        return scheduler, npc

    def test_returns_correct_package_morning(self):
        scheduler, npc = self._make_scheduler_and_npc()
        result = scheduler.tick(npc, current_hour=9)
        assert result is not None
        assert result.package_type == PackageType.WORK

    def test_returns_correct_package_night(self):
        scheduler, npc = self._make_scheduler_and_npc()
        result = scheduler.tick(npc, current_hour=23)
        assert result is not None
        assert result.package_type == PackageType.SLEEP

    def test_returns_none_when_no_package_matches(self):
        scheduler = AIPackageScheduler()
        npc = NPC("Idle")
        # No packages added
        result = scheduler.tick(npc, current_hour=12)
        assert result is None
        assert npc.active_package is None

    def test_sets_npc_active_package(self):
        scheduler, npc = self._make_scheduler_and_npc()
        scheduler.tick(npc, current_hour=7)
        assert npc.active_package is not None
        assert npc.active_package.package_type == PackageType.EAT

    def test_sets_npc_location(self):
        scheduler, npc = self._make_scheduler_and_npc()
        scheduler.tick(npc, current_hour=10)
        assert npc.current_location == Location.CROP_FIELD

    def test_invalid_hour_raises(self):
        scheduler, npc = self._make_scheduler_and_npc()
        with pytest.raises(ValueError):
            scheduler.tick(npc, current_hour=24)
        with pytest.raises(ValueError):
            scheduler.tick(npc, current_hour=-1)

    def test_priority_ordering(self):
        """Lower priority number wins when two packages overlap."""
        scheduler = AIPackageScheduler()
        npc = NPC("PriorityTest")
        npc.add_package(AIPackage(PackageType.RELAX, 0, 24, Location.BAR, priority=5))
        npc.add_package(AIPackage(PackageType.WORK, 0, 24, Location.CROP_FIELD, priority=2))
        result = scheduler.tick(npc, current_hour=12)
        assert result.package_type == PackageType.WORK


class TestBuiltInSchedules:
    def test_settler_schedule_complete(self):
        npc = AIPackageScheduler.build_settler_schedule("Marcy")
        assert npc.name == "Marcy"
        assert len(npc.packages) == 4

    def test_settler_sleep_at_midnight(self):
        scheduler = AIPackageScheduler()
        npc = AIPackageScheduler.build_settler_schedule("Jun")
        result = scheduler.tick(npc, current_hour=0)
        assert result.package_type == PackageType.SLEEP

    def test_guard_patrols_by_day(self):
        scheduler = AIPackageScheduler()
        npc = AIPackageScheduler.build_guard_schedule("Guard_01")
        result = scheduler.tick(npc, current_hour=12)
        assert result.package_type == PackageType.PATROL

    def test_guard_sleeps_at_night(self):
        scheduler = AIPackageScheduler()
        npc = AIPackageScheduler.build_guard_schedule("Guard_01")
        result = scheduler.tick(npc, current_hour=20)
        assert result.package_type == PackageType.SLEEP


# ---------------------------------------------------------------------------
# SandboxBehaviour
# ---------------------------------------------------------------------------


class TestSandboxBehaviour:
    def test_returns_interaction_string(self):
        sandbox = SandboxBehaviour()
        npc = NPC("Idle")
        result = sandbox.pick_interaction(npc)
        assert isinstance(result, str)
        assert "Idle" in result

    def test_raises_when_no_objects(self):
        sandbox = SandboxBehaviour(available_objects=[])
        npc = NPC("Lonely")
        with pytest.raises(RuntimeError):
            sandbox.pick_interaction(npc)

    def test_add_object_expands_pool(self):
        sandbox = SandboxBehaviour(available_objects=["chair"])
        sandbox.add_object("pool_table")
        assert "pool_table" in sandbox._objects

    def test_custom_object_pool(self):
        sandbox = SandboxBehaviour(available_objects=["unique_object"])
        npc = NPC("NPC")
        result = sandbox.pick_interaction(npc)
        assert "unique_object" in result
