"""Tests du rôle Loup-Voyant.

Couvre :
- Voir le rôle d'un joueur
- Ne peut pas se voir lui-même
- Une utilisation par nuit
- Perd la voyance en rejoignant la meute
- Rejoint auto la meute si dernier loup
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager(db_path=":memory:")
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestLoupVoyant:
    """Tests du Loup-Voyant."""

    def test_see_role(self):
        """Le Loup-Voyant peut voir le rôle d'un joueur."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.SORCIERE),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        alice = game.players["a1"]

        result = lv.role.perform_action(game, ActionType.SEE_ROLE, target=alice)
        assert result["success"]
        assert "role" in result

    def test_cannot_see_self(self):
        """Le Loup-Voyant ne peut pas se voir lui-même."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        result = lv.role.perform_action(game, ActionType.SEE_ROLE, target=lv)
        assert not result["success"]

    def test_one_use_per_night(self):
        """Le Loup-Voyant ne peut voir qu'une fois par nuit."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        lv.role.perform_action(game, ActionType.SEE_ROLE, target=game.players["a1"])
        assert not lv.role.can_perform_action(ActionType.SEE_ROLE)

    def test_power_reset_on_night(self):
        """Le pouvoir se réinitialise chaque nuit."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        lv.role.perform_action(game, ActionType.SEE_ROLE, target=game.players["a1"])
        lv.role.on_night_start(game)
        assert lv.role.can_perform_action(ActionType.SEE_ROLE)

    def test_cannot_vote_with_wolves_initially(self):
        """Le Loup-Voyant ne peut pas voter avec les loups au départ."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        assert not lv.role.can_vote_with_wolves()

    def test_become_werewolf(self):
        """Le Loup-Voyant peut abandonner sa voyance pour voter."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        lv = game.players["lv1"]
        result = lv.role.perform_action(game, ActionType.BECOME_WEREWOLF)
        assert result["success"]
        assert lv.role.can_vote_with_wolves()
        # Plus de voyance
        assert not lv.role.can_perform_action(ActionType.SEE_ROLE)

    def test_auto_join_pack_as_last_wolf(self):
        """Le Loup-Voyant rejoint auto la meute s'il est le dernier loup."""
        game = make_game(
            ("LV", "lv1", RoleType.LOUP_VOYANT),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
        )
        lv = game.players["lv1"]
        # Tuer l'autre loup
        game.players["w1"].is_alive = False

        lv.role.on_night_start(game)
        assert lv.role.can_vote_with_wolves()

    def test_team(self):
        role = RoleFactory.create_role(RoleType.LOUP_VOYANT)
        assert role.team == Team.MECHANT
