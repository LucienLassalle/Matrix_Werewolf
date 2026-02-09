"""Tests du rôle Loup Noir.

Couvre :
- Conversion réussie d'un villageois
- Conversion bloquée par le Garde
- Conversion échouée sur cible déjà méchante → meurtre normal
- Pouvoir unique (une seule utilisation)
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


def make_game(*specs) -> GameManager:
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestLoupNoirConversion:
    """Conversion Loup Noir : succès, échec, et protection."""

    def test_conversion_success(self):
        """Convertir un villageois en loup réussit."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["ln1"].role.perform_action(game, ActionType.CONVERT)
        game.vote_manager.add_wolf_vote(game.players["ln1"], game.players["a1"])
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] == game.players["a1"]
        assert game.players["a1"].is_alive
        assert game.players["a1"].role.role_type == RoleType.LOUP_GAROU

    def test_conversion_blocked_by_guard(self):
        """Le Garde bloque la conversion."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Garde", "g1", RoleType.GARDE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.players["ln1"].role.perform_action(game, ActionType.CONVERT)
        game.players["g1"].role.perform_action(game, ActionType.PROTECT, game.players["a1"])
        game.action_manager.register_action(game.players["g1"], ActionType.PROTECT, game.players["a1"])

        game.vote_manager.add_wolf_vote(game.players["ln1"], game.players["a1"])
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert game.players["a1"].is_alive
        assert game.players["a1"].role.role_type == RoleType.VILLAGEOIS

    def test_failed_conversion_on_evil_target_kills(self):
        """Si la cible est déjà méchante, la conversion échoue → meurtre normal."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("EvilTarget", "e1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.players["ln1"].role.perform_action(game, ActionType.CONVERT)
        game.vote_manager.add_wolf_vote(game.players["ln1"], game.players["e1"])
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["e1"])

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert not game.players["e1"].is_alive
        assert len(results["deaths"]) == 1

    def test_power_single_use(self):
        """Le Loup Noir ne peut convertir qu'une seule fois."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        r1 = game.players["ln1"].role.perform_action(game, ActionType.CONVERT)
        assert r1["success"]

        # Réinitialiser la nuit (simule une nouvelle nuit)
        game.players["ln1"].role.on_night_start(game)

        r2 = game.players["ln1"].role.perform_action(game, ActionType.CONVERT)
        assert not r2["success"]


class TestLoupNoirToggleAndReset:
    """Tests du toggle de conversion et du reset entre nuits."""

    def test_convert_toggle(self):
        """Activer la conversion met wants_to_convert à True."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]
        assert not ln.role.wants_to_convert
        r = ln.role.perform_action(game, ActionType.CONVERT)
        assert r["success"]
        assert ln.role.wants_to_convert

    def test_cannot_convert_twice_same_night(self):
        """Impossible d'activer la conversion deux fois la même nuit."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]
        ln.role.perform_action(game, ActionType.CONVERT)
        r = ln.role.perform_action(game, ActionType.CONVERT)
        assert not r["success"]

    def test_reset_on_night_start(self):
        """Le flag wants_to_convert est réinitialisé au début de la nuit."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]
        ln.role.wants_to_convert = True
        ln.role.on_night_start(game)
        assert not ln.role.wants_to_convert

    def test_can_vote_with_wolves(self):
        """Le Loup Noir peut voter avec les loups."""
        role = RoleFactory.create_role(RoleType.LOUP_NOIR)
        assert role.can_vote_with_wolves()

    def test_no_conversion_normal_kill(self):
        """Sans activation de conversion, le meurtre classique a lieu."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["ln1"])
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["ln1"], target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert not target.is_alive
        assert target in results["deaths"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
