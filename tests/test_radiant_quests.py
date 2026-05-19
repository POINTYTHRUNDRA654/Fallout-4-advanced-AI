"""
Tests for radiant_quests.py
"""

import pytest
from src.ai.radiant_quests import (
    HostileFaction,
    Location,
    QuestType,
    RadiantQuest,
    RadiantQuestDirector,
    Settler,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _simple_director(player_level: int = 10) -> RadiantQuestDirector:
    locations = [
        Location("Corvega Assembly Plant", 5, 20),
        Location("Fort Hagen", 10, 30),
        Location("Quincy Ruins", 25, 50),
    ]
    settlers = [
        Settler("Jun Long", "Sanctuary Hills"),
        Settler("Marcy Long", "Sanctuary Hills"),
    ]
    return RadiantQuestDirector(locations=locations, settlers=settlers, player_level=player_level)


# ---------------------------------------------------------------------------
# Location eligibility
# ---------------------------------------------------------------------------


class TestLocationEligibility:
    def test_eligible_locations_returned(self):
        director = _simple_director(player_level=10)
        quest = director.generate_quest(quest_type=QuestType.CLEAR_LOCATION)
        # Level 10 should match Corvega (5-20) or Fort Hagen (10-30), NOT Quincy (25-50)
        assert quest.target_location.name != "Quincy Ruins"

    def test_raises_when_no_eligible_location(self):
        director = _simple_director(player_level=1)
        # Only Corvega covers 5-20; level 1 is below min_level=5 → no match
        with pytest.raises(RuntimeError):
            director.generate_quest()

    def test_cleared_locations_excluded(self):
        locations = [Location("Cleared Place", 1, 50, is_cleared=True)]
        director = RadiantQuestDirector(locations=locations, settlers=[], player_level=10)
        with pytest.raises(RuntimeError):
            director.generate_quest()

    def test_high_level_area_used_at_high_level(self):
        locations = [Location("Quincy Ruins", 25, 50)]
        director = RadiantQuestDirector(locations=locations, settlers=[], player_level=30)
        quest = director.generate_quest(quest_type=QuestType.CLEAR_LOCATION)
        assert quest.target_location.name == "Quincy Ruins"


# ---------------------------------------------------------------------------
# Faction selection
# ---------------------------------------------------------------------------


class TestFactionSelection:
    def test_returns_valid_faction(self):
        director = _simple_director()
        quest = director.generate_quest(quest_type=QuestType.CLEAR_LOCATION)
        assert isinstance(quest.hostile_faction, HostileFaction)

    def test_faction_weights_respected(self):
        locations = [Location("X", 1, 50)]
        weights = {f: 0.0 for f in HostileFaction}
        weights[HostileFaction.GHOULS] = 1.0
        director = RadiantQuestDirector(locations=locations, settlers=[], player_level=10,
                                        faction_weights=weights)
        for _ in range(20):
            quest = director.generate_quest(quest_type=QuestType.CLEAR_LOCATION)
            assert quest.hostile_faction == HostileFaction.GHOULS


# ---------------------------------------------------------------------------
# Quest type: RESCUE_SETTLER
# ---------------------------------------------------------------------------


class TestRescueSettlerQuest:
    def test_settler_assigned_when_available(self):
        director = _simple_director()
        quest = director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        assert quest.quest_type == QuestType.RESCUE_SETTLER
        assert quest.kidnapped_settler is not None

    def test_settler_marked_unavailable_after_selection(self):
        director = _simple_director()
        quest = director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        assert quest.kidnapped_settler is not None
        assert quest.kidnapped_settler.is_available is False

    def test_falls_back_to_clear_when_no_settlers(self):
        locations = [Location("Loc", 1, 50)]
        director = RadiantQuestDirector(locations=locations, settlers=[], player_level=10)
        quest = director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        assert quest.quest_type == QuestType.CLEAR_LOCATION

    def test_repeated_rescue_exhausts_settlers(self):
        director = _simple_director()
        # First two quests claim both settlers
        director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        # Third should fall back
        quest = director.generate_quest(quest_type=QuestType.RESCUE_SETTLER)
        assert quest.quest_type == QuestType.CLEAR_LOCATION


# ---------------------------------------------------------------------------
# Quest descriptions
# ---------------------------------------------------------------------------


class TestQuestDescriptions:
    def test_rescue_description_contains_settler_name(self):
        settler = Settler("Jun Long", "Sanctuary Hills")
        location = Location("Corvega", 1, 50)
        quest = RadiantQuest(
            quest_type=QuestType.RESCUE_SETTLER,
            target_location=location,
            hostile_faction=HostileFaction.RAIDERS,
            kidnapped_settler=settler,
        )
        assert "Jun Long" in quest.description

    def test_clear_description_mentions_location(self):
        location = Location("Fort Hagen", 1, 50)
        quest = RadiantQuest(
            quest_type=QuestType.CLEAR_LOCATION,
            target_location=location,
            hostile_faction=HostileFaction.SUPER_MUTANTS,
        )
        assert "Fort Hagen" in quest.description

    def test_supply_run_description(self):
        location = Location("Mass Fusion", 1, 50)
        quest = RadiantQuest(
            quest_type=QuestType.SUPPLY_RUN,
            target_location=location,
            hostile_faction=HostileFaction.GUNNERS,
        )
        assert "Mass Fusion" in quest.description
        assert quest.description  # non-empty


# ---------------------------------------------------------------------------
# default_commonwealth factory
# ---------------------------------------------------------------------------


class TestDefaultCommonwealth:
    def test_factory_creates_director(self):
        director = RadiantQuestDirector.default_commonwealth(player_level=15)
        assert isinstance(director, RadiantQuestDirector)

    def test_generates_quest_at_various_levels(self):
        for level in (5, 15, 30, 45):
            director = RadiantQuestDirector.default_commonwealth(player_level=level)
            quest = director.generate_quest(quest_type=QuestType.CLEAR_LOCATION)
            assert isinstance(quest, RadiantQuest)

    def test_invalid_player_level_raises(self):
        with pytest.raises(ValueError):
            RadiantQuestDirector(locations=[], settlers=[], player_level=0)
