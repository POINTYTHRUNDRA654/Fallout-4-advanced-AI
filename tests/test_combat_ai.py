"""
Tests for combat_ai.py
"""

import pytest
from src.ai.combat_ai import (
    CombatAI,
    CombatantNPC,
    CoverType,
    DetectionState,
    DetectionSystem,
    MoraleSystem,
    NavMesh,
    NavNode,
)


# ---------------------------------------------------------------------------
# NavMesh helpers
# ---------------------------------------------------------------------------


def _simple_mesh() -> NavMesh:
    """3×1 mesh: open at (0,0), low cover at (1,0), high cover at (2,0)."""
    mesh = NavMesh()
    mesh.add_node(NavNode(0, 0, elevation=0.0, cover_type=CoverType.OPEN))
    mesh.add_node(NavNode(1, 0, elevation=0.5, cover_type=CoverType.LOW_COVER))
    mesh.add_node(NavNode(2, 0, elevation=1.0, cover_type=CoverType.HIGH_COVER))
    return mesh


def _elevated_mesh() -> NavMesh:
    """4×1 mesh with a high-ground node at (3,0)."""
    mesh = NavMesh()
    mesh.add_node(NavNode(0, 0, cover_type=CoverType.OPEN))
    mesh.add_node(NavNode(1, 0, cover_type=CoverType.LOW_COVER))
    mesh.add_node(NavNode(2, 0, cover_type=CoverType.HIGH_COVER))
    mesh.add_node(NavNode(3, 0, elevation=5.0, cover_type=CoverType.HIGH_GROUND))
    return mesh


def _make_npc(npc_id="raider_01", faction="Raiders", health=100.0, position=(0, 0)):
    return CombatantNPC(npc_id=npc_id, faction=faction, max_health=100, health=health, position=position)


# ---------------------------------------------------------------------------
# NavMesh
# ---------------------------------------------------------------------------


class TestNavMesh:
    def test_add_and_get_node(self):
        mesh = NavMesh()
        node = NavNode(5, 5, elevation=2.0, cover_type=CoverType.HIGH_COVER)
        mesh.add_node(node)
        retrieved = mesh.get_node(5, 5)
        assert retrieved is node

    def test_get_nonexistent_node_returns_none(self):
        mesh = NavMesh()
        assert mesh.get_node(99, 99) is None

    def test_neighbors_4_directional(self):
        mesh = _simple_mesh()
        # (0,0) has only one walkable neighbour → (1,0)
        neighbours = mesh.neighbors(0, 0)
        positions = {(n.x, n.y) for n in neighbours}
        assert (1, 0) in positions
        assert (0, 1) not in positions  # not in mesh

    def test_find_cover_nodes(self):
        mesh = _simple_mesh()
        cover = mesh.find_cover_nodes()
        cover_types = {n.cover_type for n in cover}
        assert CoverType.LOW_COVER in cover_types
        assert CoverType.HIGH_COVER in cover_types
        assert CoverType.OPEN not in cover_types

    def test_find_high_ground(self):
        mesh = _elevated_mesh()
        hg = mesh.find_high_ground()
        assert len(hg) == 1
        assert hg[0].cover_type == CoverType.HIGH_GROUND

    def test_unwalkable_node_excluded_from_neighbors(self):
        mesh = NavMesh()
        mesh.add_node(NavNode(0, 0))
        mesh.add_node(NavNode(1, 0, is_walkable=False))
        assert mesh.neighbors(0, 0) == []


# ---------------------------------------------------------------------------
# DetectionSystem
# ---------------------------------------------------------------------------


class TestDetectionSystem:
    def setup_method(self):
        self.ds = DetectionSystem(visibility_threshold=0.3, danger_threshold=0.6)
        self.npc = _make_npc()

    def test_hidden_when_scores_low(self):
        state = self.ds.evaluate(self.npc, visibility=0.1, light_level=0.1, noise=0.0)
        assert state == DetectionState.HIDDEN

    def test_caution_on_partial_visibility(self):
        state = self.ds.evaluate(self.npc, visibility=0.5, light_level=0.5, noise=0.0)
        # combined = 0.25 → below threshold for caution at 0.3? Let's check:
        # combined = 0.5*0.5 + 0.0*0.5 = 0.25  →  HIDDEN if < 0.3
        assert state == DetectionState.HIDDEN

    def test_caution_triggered(self):
        # combined = 0.7*0.7 + 0.0 = 0.49 → CAUTION (>= 0.3, < 0.6)
        state = self.ds.evaluate(self.npc, visibility=0.7, light_level=0.7, noise=0.0)
        assert state == DetectionState.CAUTION

    def test_danger_triggered(self):
        state = self.ds.evaluate(self.npc, visibility=1.0, light_level=1.0, noise=0.5)
        assert state == DetectionState.DANGER

    def test_noise_alone_can_trigger_caution(self):
        # combined = 0.0*0.0 + 0.8*0.5 = 0.4 → CAUTION
        state = self.ds.evaluate(self.npc, visibility=0.0, light_level=0.0, noise=0.8)
        assert state == DetectionState.CAUTION

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            self.ds.evaluate(self.npc, visibility=1.5, light_level=0.5, noise=0.0)
        with pytest.raises(ValueError):
            self.ds.evaluate(self.npc, visibility=0.5, light_level=-0.1, noise=0.0)

    def test_state_stored_on_npc(self):
        self.ds.evaluate(self.npc, visibility=1.0, light_level=1.0, noise=1.0)
        assert self.npc.detection_state == DetectionState.DANGER


# ---------------------------------------------------------------------------
# MoraleSystem
# ---------------------------------------------------------------------------


class TestMoraleSystem:
    def setup_method(self):
        self.ms = MoraleSystem(flee_health_threshold=0.25)

    def _make_faction(self, health_fractions, leader_index=0, kill_leader=False):
        npcs = []
        for i, frac in enumerate(health_fractions):
            hp = frac * 100
            npc = CombatantNPC(
                npc_id=f"raider_{i}",
                faction="Raiders",
                max_health=100,
                health=hp,
                is_leader=(i == leader_index),
            )
            npcs.append(npc)
        if kill_leader:
            npcs[leader_index].health = 0
        return npcs

    def test_no_flee_when_healthy(self):
        faction = self._make_faction([1.0, 0.9, 0.8])
        assert self.ms.evaluate_faction(faction) is False

    def test_flee_when_avg_health_low(self):
        faction = self._make_faction([0.1, 0.1, 0.1])
        assert self.ms.evaluate_faction(faction) is True

    def test_flee_when_leader_dies(self):
        faction = self._make_faction([0.9, 0.9, 0.9], kill_leader=True)
        assert self.ms.evaluate_faction(faction) is True

    def test_all_survivors_flagged_fleeing(self):
        faction = self._make_faction([0.1, 0.1, 0.1])
        self.ms.evaluate_faction(faction)
        alive = [c for c in faction if c.is_alive]
        assert all(c.is_fleeing for c in alive)

    def test_empty_faction_returns_false(self):
        assert self.ms.evaluate_faction([]) is False

    def test_all_dead_returns_false(self):
        faction = self._make_faction([0.0, 0.0])
        assert self.ms.evaluate_faction(faction) is False


# ---------------------------------------------------------------------------
# CombatAI integration
# ---------------------------------------------------------------------------


class TestCombatAI:
    def setup_method(self):
        self.mesh = _simple_mesh()
        self.ai = CombatAI(self.mesh)
        self.npc = _make_npc(position=(0, 0))

    def test_seek_cover_moves_to_high_cover(self):
        node = self.ai.seek_cover(self.npc)
        assert node is not None
        assert node.cover_type == CoverType.HIGH_COVER
        assert self.npc.position == (node.x, node.y)

    def test_seek_cover_returns_none_when_no_cover(self):
        open_mesh = NavMesh()
        open_mesh.add_node(NavNode(0, 0, cover_type=CoverType.OPEN))
        ai = CombatAI(open_mesh)
        npc = _make_npc()
        assert ai.seek_cover(npc) is None

    def test_attempt_flank_moves_npc(self):
        mesh = _elevated_mesh()
        ai = CombatAI(mesh)
        attacker = _make_npc(position=(0, 0))
        target_pos = (1, 0)
        result = ai.attempt_flank(attacker, target_pos)
        assert result is not None
        assert attacker.position != (0, 0)

    def test_attempt_flank_returns_none_on_empty_mesh(self):
        empty_mesh = NavMesh()
        ai = CombatAI(empty_mesh)
        npc = _make_npc()
        assert ai.attempt_flank(npc, (5, 5)) is None

    def test_update_detection_delegates_correctly(self):
        state = self.ai.update_detection(self.npc, 1.0, 1.0, 1.0)
        assert state == DetectionState.DANGER
        assert self.npc.detection_state == DetectionState.DANGER

    def test_evaluate_morale_triggers_flee(self):
        squad = [
            CombatantNPC("r1", "Raiders", 100, 10, is_leader=True),
            CombatantNPC("r2", "Raiders", 100, 10),
        ]
        fled = self.ai.evaluate_morale(squad)
        assert fled is True
        assert all(c.is_fleeing for c in squad if c.is_alive)


# ---------------------------------------------------------------------------
# CombatantNPC properties
# ---------------------------------------------------------------------------


class TestCombatantNPCProperties:
    def test_health_fraction(self):
        npc = CombatantNPC("x", "f", 200, 50)
        assert npc.health_fraction == pytest.approx(0.25)

    def test_is_alive(self):
        npc = CombatantNPC("x", "f", 100, 1)
        assert npc.is_alive is True
        npc.health = 0
        assert npc.is_alive is False

    def test_zero_max_health_fraction(self):
        npc = CombatantNPC("x", "f", 0, 0)
        assert npc.health_fraction == 0.0
