from __future__ import annotations

from unittest.mock import MagicMock

from game.commander.battlepositions import BattlePositions
from game.commander.tasks.primitive.breakthroughattack import BreakthroughAttack
from game.commander.theaterstate import battle_position_bases
from game.theater import Player


def _front_line(friendly: MagicMock, enemy: MagicMock) -> MagicMock:
    front_line = MagicMock()
    front_line.control_point_friendly_to.return_value = friendly
    front_line.control_point_hostile_to.return_value = enemy
    return front_line


def test_front_line_base_beyond_air_assault_reach_is_kept() -> None:
    # Bardufoss to Alta is 116 NM, so air_assault_targets() drops Bardufoss.
    near, bardufoss = MagicMock(), MagicMock()
    front_line = _front_line(MagicMock(), bardufoss)

    bases = battle_position_bases([near], [front_line], Player.RED)

    assert bases == [near, bardufoss]


def test_front_line_base_already_listed_is_not_repeated() -> None:
    near, front_base = MagicMock(), MagicMock()
    front_line = _front_line(MagicMock(), front_base)

    bases = battle_position_bases([front_base, near], [front_line], Player.RED)

    assert bases == [front_base, near]


def test_no_front_lines_leaves_the_air_assault_list_alone() -> None:
    a, b = MagicMock(), MagicMock()

    assert battle_position_bases([a, b], [], Player.BLUE) == [a, b]


def test_breakthrough_reads_a_far_front_base_without_error() -> None:
    # The crash: red had 2 to 1 at the front, so BreakthroughAttack looked up
    # the enemy base, and a 116 NM front had no entry for it.
    friendly, bardufoss = MagicMock(), MagicMock()
    front_line = _front_line(friendly, bardufoss)
    state = MagicMock()
    state.enemy_battle_positions = {
        cp: BattlePositions(blocking_capture=[], defending_front_line=[])
        for cp in battle_position_bases([], [front_line], Player.RED)
    }

    task = BreakthroughAttack(front_line, Player.RED)

    assert task.opposing_battle_positions_eliminated(state)
