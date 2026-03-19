"""Tests du CommandHandler : commandes convertir et dictateur.

Couvre :
- convertir : activation, mauvais rôle
- dictateur : exécution, mort si innocent, mauvais rôle, pas de cible
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager
from commands.command_handler import CommandHandler


def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés en phase NIGHT."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


class TestConvertirCommand:
    """Tests de la commande convertir."""

    def test_convertir_command(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        handler = CommandHandler(game)

        result = handler.execute_command("ln1", "convertir", [])
        assert result["success"]
        assert game.players["ln1"].role.wants_to_convert

    def test_convertir_wrong_role(self):
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        handler = CommandHandler(game)

        result = handler.execute_command("v1", "convertir", [])
        assert not result["success"]


class TestDictateurCommand:
    """Tests de la commande dictateur."""

    def test_dictateur_kills_wolf(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        game.phase = GamePhase.NIGHT
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", [])
        assert result["success"]

        game.phase = GamePhase.DAY
        result = handler.execute_command("d1", "dictateur", ["Loup"])
        assert result["success"]
        assert not game.players["w1"].is_alive
        assert game.players["d1"].is_mayor  # Tué un loup → maire

    def test_dictateur_kills_innocent_dies_too(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.NIGHT
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", [])
        assert result["success"]

        game.phase = GamePhase.DAY
        result = handler.execute_command("d1", "dictateur", ["Villageois"])
        assert result["success"]
        assert not game.players["v1"].is_alive
        assert not game.players["d1"].is_alive  # Dictateur meurt aussi

    def test_dictateur_wrong_role(self):
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Target", "t1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("v1", "dictateur", ["Target"])
        assert not result["success"]

    def test_dictateur_no_target(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", [])
        assert not result["success"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
