"""Tests de la commande maire."""

from commands.command_handler import CommandHandler
from models.enums import RoleType
from tests.mayor_cupidon_helpers import make_game


class TestMaireCommand:
    """Tests de la commande maire pour la succession."""

    def test_maire_command_success(self):
        """Le maire mort peut utiliser la commande maire pour designer un successeur."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)

        result = handler.execute_command("m1", "maire", ["Successeur"])

        assert result["success"]
        assert game.players["s1"].is_mayor
        assert game._pending_mayor_succession is None

    def test_maire_command_dead_non_mayor_fails(self):
        """Un joueur mort non-maire ne peut pas utiliser la commande maire."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        dead = game.players["d1"]
        dead.is_alive = False

        result = handler.execute_command("d1", "maire", ["Maire"])

        assert not result["success"]
        assert "mort" in result["message"].lower()

    def test_maire_command_alive_player_fails(self):
        """Un joueur vivant ne peut pas utiliser la commande maire."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)

        result = handler.execute_command("v1", "maire", ["Loup"])

        assert not result["success"]

    def test_maire_command_no_args(self):
        """La commande maire sans argument echoue."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)

        result = handler.execute_command("m1", "maire", [])

        assert not result["success"]
        assert "Usage" in result["message"]

    def test_maire_command_invalid_target(self):
        """La commande maire avec un pseudo inexistant echoue."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)

        result = handler.execute_command("m1", "maire", ["Inexistant"])

        assert not result["success"]
        assert "non trouvé" in result["message"]

    def test_maire_via_handle_command(self):
        """handle_command avec cible resolue fonctionne."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True

        game.kill_player(mayor, killed_during_day=True)

        result = handler.handle_command("m1", "maire", "Successeur")

        assert result["success"]
        assert game.players["s1"].is_mayor
