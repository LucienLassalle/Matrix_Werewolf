"""Tests du role Geolier."""

from models.enums import ActionType, GamePhase, RoleType
from roles import RoleFactory
from game.game_manager import GameManager
from commands.command_handler import CommandHandler


def make_game(*specs) -> GameManager:
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.DAY
    return game


class TestGeolierJail:
    def test_jail_applied_at_night_start(self):
        game = make_game(
            ("Geolier", "g1", RoleType.GEOLIER),
            ("Prisonnier", "p1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        result = geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        assert result["success"]

        game.begin_night()
        assert prisoner.is_jailed is True
        assert game.is_player_jailed(prisoner.user_id) is True

    def test_jail_cancelled_if_prisoner_dead_before_night(self):
        game = make_game(
            ("Geolier", "g1", RoleType.GEOLIER),
            ("Prisonnier", "p1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        prisoner.kill()

        game.begin_night()
        assert prisoner.is_jailed is False
        assert game.is_player_jailed(prisoner.user_id) is False

    def test_prisoner_cannot_act(self):
        game = make_game(
            ("Geolier", "g1", RoleType.GEOLIER),
            ("Voyante", "s1", RoleType.VOYANTE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        prisoner = game.players["s1"]
        prisoner.is_jailed = True

        handler = CommandHandler(game)
        game.phase = GamePhase.NIGHT
        result = handler.execute_command("s1", "voyante", ["Alice"])
        assert not result["success"]
        assert "prison" in result["message"].lower()

    def test_geolier_execute_kills_prisoner(self):
        game = make_game(
            ("Geolier", "g1", RoleType.GEOLIER),
            ("Prisonnier", "p1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        game.begin_night()

        handler = CommandHandler(game)
        result = handler.execute_command("g1", "geolier-tuer", [])
        assert result["success"]
        assert not prisoner.is_alive
