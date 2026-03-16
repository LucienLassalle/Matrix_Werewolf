"""Tests des messages Geolier <-> prisonnier via command_router."""

import pytest

from models.enums import ActionType, GamePhase, RoleType
from roles import RoleFactory
from game.game_manager import GameManager
from commands.command_handler import CommandHandler
from matrix_bot.command_router import CommandRouterMixin


class DummyClient:
    def __init__(self):
        self.sent_dm = []
        self.sent_msg = []

    async def send_dm(self, user_id: str, message: str):
        self.sent_dm.append((user_id, message))

    async def send_message(self, room_id: str, message: str, formatted: bool = False):
        self.sent_msg.append((room_id, message, formatted))


class DummyRoomManager:
    def __init__(self, dm_room_id: str):
        self._dm_room_id = dm_room_id

    def is_village_room(self, room_id: str) -> bool:
        return False

    def is_wolves_room(self, room_id: str) -> bool:
        return False

    def is_dm_room(self, room_id: str) -> bool:
        return room_id == self._dm_room_id


class DummyBot(CommandRouterMixin):
    def __init__(self, dm_room_id: str):
        self.command_prefix = "!"
        self.client = DummyClient()
        self.room_manager = DummyRoomManager(dm_room_id)
        self.game_manager = GameManager()
        self.command_handler = CommandHandler(self.game_manager, command_prefix=self.command_prefix)
        self._wolf_votes_locked = False

    async def _check_wolf_vote_complete(self):
        return None

    async def _check_mayor_election_progress(self):
        return None

    async def _create_couple_room_if_needed(self):
        return None

    async def _check_loup_voyant_room(self):
        return None

    async def _handle_voleur_swap_rooms(self, player, swapped):
        return None

    async def _check_voleur_new_role_rooms(self, player):
        return None

    def _cancel_chasseur_timeout(self, user_id: str):
        return None

    async def _process_command_deaths(self, result, command, user_id):
        return None

    async def _announce_victory(self, winner):
        return None

    async def _check_victory(self):
        return None


def _assign_role(game: GameManager, pseudo: str, uid: str, role_type: RoleType):
    game.add_player(pseudo, uid)
    role = RoleFactory.create_role(role_type)
    role.assign_to_player(game.players[uid])


@pytest.mark.asyncio
class TestGeolierMessaging:
    async def test_msg_relay_between_jailer_and_prisoner(self):
        bot = DummyBot(dm_room_id="dm1")
        game = bot.game_manager

        _assign_role(game, "Geolier", "g1", RoleType.GEOLIER)
        _assign_role(game, "Prisonnier", "p1", RoleType.VILLAGEOIS)
        _assign_role(game, "Loup", "w1", RoleType.LOUP_GAROU)
        _assign_role(game, "Alice", "a1", RoleType.VILLAGEOIS)
        _assign_role(game, "Bob", "b1", RoleType.VILLAGEOIS)
        _assign_role(game, "Eve", "e1", RoleType.VILLAGEOIS)

        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        game.phase = GamePhase.NIGHT
        game.begin_night()

        await bot._handle_command("dm1", "g1", "msg", ["Bonjour"], None)
        assert ("p1", "🔒 **Message du geolier :**\nBonjour") in bot.client.sent_dm

        await bot._handle_command("dm1", "p1", "msg", ["Recu"], None)
        assert ("g1", "🔒 **Message du prisonnier :**\nRecu") in bot.client.sent_dm

    async def test_msg_requires_dm_room(self):
        bot = DummyBot(dm_room_id="dm1")
        game = bot.game_manager

        _assign_role(game, "Geolier", "g1", RoleType.GEOLIER)
        _assign_role(game, "Prisonnier", "p1", RoleType.VILLAGEOIS)
        _assign_role(game, "Loup", "w1", RoleType.LOUP_GAROU)
        _assign_role(game, "Alice", "a1", RoleType.VILLAGEOIS)
        _assign_role(game, "Bob", "b1", RoleType.VILLAGEOIS)
        _assign_role(game, "Eve", "e1", RoleType.VILLAGEOIS)

        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        game.phase = GamePhase.NIGHT
        game.begin_night()

        await bot._handle_command("not-dm", "g1", "msg", ["Test"], None)
        assert any("message privé" in msg for _, msg in bot.client.sent_dm)

    async def test_msg_only_for_jailer_or_prisoner(self):
        bot = DummyBot(dm_room_id="dm1")
        game = bot.game_manager

        _assign_role(game, "Geolier", "g1", RoleType.GEOLIER)
        _assign_role(game, "Prisonnier", "p1", RoleType.VILLAGEOIS)
        _assign_role(game, "Intrus", "i1", RoleType.VILLAGEOIS)
        _assign_role(game, "Loup", "w1", RoleType.LOUP_GAROU)
        _assign_role(game, "Alice", "a1", RoleType.VILLAGEOIS)
        _assign_role(game, "Bob", "b1", RoleType.VILLAGEOIS)

        geolier = game.players["g1"]
        prisoner = game.players["p1"]

        geolier.role.perform_action(game, ActionType.JAIL_SELECT, prisoner)
        game.phase = GamePhase.NIGHT
        game.begin_night()

        await bot._handle_command("dm1", "i1", "msg", ["Test"], None)
        assert any("interrogatoire" in msg for _, msg in bot.client.sent_dm)
