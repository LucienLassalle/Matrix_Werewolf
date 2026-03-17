"""Tests du mode spectateur pour les joueurs morts.

Vérifie que :
- Les villageois morts passent en lecture seule (village uniquement)
- Les loups morts passent en lecture seule (village + salon des loups)
- Personne n'est expulsé des salons de jeu
- Le salon du couple passe aussi en lecture seule (mute)
"""

import pytest
import pytest_asyncio

from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.chasseur import Chasseur
from models.player import Player

pytestmark = pytest.mark.asyncio


class FakeRoomManager:
    """Simule le RoomManager."""

    def __init__(self):
        self.village_room = "!village:matrix.org"
        self.wolves_room = "!wolves:matrix.org"
        self.couple_room = "!couple:matrix.org"
        self.dead_invited = []

    async def add_to_dead(self, user_id):
        self.dead_invited.append(user_id)


class FakeClient:
    """Simule le MatrixClientWrapper."""

    def __init__(self):
        self.power_levels = {}   # (room_id, user_id) → level
        self.kicked = []         # (room_id, user_id)
        self._room_members = {}  # room_id → set(user_ids)

    async def set_power_level(self, room_id, user_id, level):
        self.power_levels[(room_id, user_id)] = level

    async def kick_user(self, room_id, user_id, reason=None):
        self.kicked.append((room_id, user_id))

    async def get_room_members(self, room_id):
        return self._room_members.get(room_id, set())


class FakeGameManager:
    """Simule un GameManager minimal pour les tests de roles."""

    def __init__(self, players=None):
        self.players = players or {}

    def get_player(self, user_id):
        return self.players.get(user_id)


def _make_bot_stub():
    """Crée un stub WerewolfBot avec les méthodes réelles."""
    from matrix_bot.bot_controller import WerewolfBot

    class BotStub:
        pass

    stub = BotStub()
    stub.room_manager = FakeRoomManager()
    stub.client = FakeClient()
    stub._wolves_in_room = set()
    stub.game_manager = None

    # Binder les méthodes réelles
    stub._mute_player = WerewolfBot._mute_player.__get__(stub, BotStub)
    stub._remove_wolf_from_room = WerewolfBot._remove_wolf_from_room.__get__(stub, BotStub)
    return stub


class TestSpectatorVillager:
    """Un villageois mort reste en lecture seule dans le village."""

    async def test_mute_player_sets_village_read_only(self):
        stub = _make_bot_stub()
        user_id = "@alice:matrix.org"

        await stub._mute_player(user_id)

        key = (stub.room_manager.village_room, user_id)
        assert key in stub.client.power_levels
        assert stub.client.power_levels[key] == -1

    async def test_villager_not_kicked_from_village(self):
        stub = _make_bot_stub()
        user_id = "@alice:matrix.org"

        await stub._mute_player(user_id)

        village_kicks = [
            (r, u) for r, u in stub.client.kicked
            if r == stub.room_manager.village_room
        ]
        assert len(village_kicks) == 0


class TestSpectatorWolf:
    """Un loup mort reste en lecture seule dans le village ET le salon des loups."""

    async def test_wolf_read_only_in_wolves_room(self):
        stub = _make_bot_stub()
        user_id = "@wolf:matrix.org"
        stub._wolves_in_room.add(user_id)

        await stub._mute_player(user_id)

        key = (stub.room_manager.wolves_room, user_id)
        assert key in stub.client.power_levels
        assert stub.client.power_levels[key] == -1

    async def test_wolf_not_kicked_from_wolves_room(self):
        stub = _make_bot_stub()
        user_id = "@wolf:matrix.org"
        stub._wolves_in_room.add(user_id)

        await stub._mute_player(user_id)

        wolf_kicks = [
            (r, u) for r, u in stub.client.kicked
            if r == stub.room_manager.wolves_room
        ]
        assert len(wolf_kicks) == 0

    async def test_remove_wolf_from_room_sets_read_only(self):
        stub = _make_bot_stub()
        user_id = "@wolf:matrix.org"
        stub._wolves_in_room.add(user_id)

        await stub._remove_wolf_from_room(user_id)

        key = (stub.room_manager.wolves_room, user_id)
        assert key in stub.client.power_levels
        assert stub.client.power_levels[key] == -1

        wolf_kicks = [
            (r, u) for r, u in stub.client.kicked
            if r == stub.room_manager.wolves_room
        ]
        assert len(wolf_kicks) == 0


class TestCoupleRoomCleanup:
    """Le salon du couple passe en lecture seule (mute) à la mort."""

    async def test_couple_member_muted_on_death(self):
        stub = _make_bot_stub()
        user_id = "@lover:matrix.org"
        stub.client._room_members[stub.room_manager.couple_room] = {user_id}

        await stub._mute_player(user_id)

        key = (stub.room_manager.couple_room, user_id)
        assert key in stub.client.power_levels
        assert stub.client.power_levels[key] == -1

    async def test_non_couple_member_not_muted_in_couple(self):
        stub = _make_bot_stub()
        user_id = "@solo:matrix.org"
        stub.client._room_members[stub.room_manager.couple_room] = set()

        await stub._mute_player(user_id)

        key = (stub.room_manager.couple_room, user_id)
        assert key not in stub.client.power_levels or stub.client.power_levels.get(key) != -1

    async def test_dead_player_invited_to_cemetery(self):
        stub = _make_bot_stub()
        user_id = "@dead:matrix.org"

        await stub._mute_player(user_id)

        assert user_id in stub.room_manager.dead_invited


class TestSpectatorChasseur:
    """Le Chasseur n'est pas invite au cimetiere tant qu'il peut tirer."""

    async def test_hunter_not_invited_before_shot(self):
        stub = _make_bot_stub()
        user_id = "@hunter:matrix.org"

        player = Player("Hunter", user_id)
        role = Chasseur()
        role.assign_to_player(player)
        player.is_alive = False
        role.can_shoot_now = True
        role.has_shot = False

        stub.game_manager = FakeGameManager({user_id: player})

        await stub._mute_player(user_id)

        assert user_id not in stub.room_manager.dead_invited


class TestDeathNotificationSpectator:
    """Vérifie que la notification de mort mentionne le mode spectateur."""

    async def test_villager_death_notification(self):
        from matrix_bot.notifications import NotificationManager

        sent_messages = []

        class FakeRM:
            async def send_dm(self, user_id, message):
                sent_messages.append((user_id, message))

        nm = NotificationManager(FakeRM(), command_prefix="!")
        role = Villageois()

        await nm.send_death_notification("@v:matrix.org", role)

        assert len(sent_messages) == 1
        msg = sent_messages[0][1]
        assert "spectateur" in msg.lower()
        assert "lire" in msg.lower()
        # Villager notification should NOT mention wolf room
        assert "loups" not in msg.lower()

    async def test_wolf_death_notification(self):
        from matrix_bot.notifications import NotificationManager

        sent_messages = []

        class FakeRM:
            async def send_dm(self, user_id, message):
                sent_messages.append((user_id, message))

        nm = NotificationManager(FakeRM(), command_prefix="!")
        role = LoupGarou()

        await nm.send_death_notification("@w:matrix.org", role)

        assert len(sent_messages) == 1
        msg = sent_messages[0][1]
        assert "spectateur" in msg.lower()
        assert "loups" in msg.lower()
