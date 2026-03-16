"""Tests de persistance des salons Matrix."""

import os
import tempfile

from database.game_db import GameDatabase
from models.enums import GamePhase, RoleType
from models.player import Player
from roles import RoleFactory


class TestRoomStatePersistence:
    """Verifie la sauvegarde et restauration des IDs de salons Matrix."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = GameDatabase(self.tmp.name)

    def teardown_method(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_save_and_load_rooms(self):
        rooms = {
            'village': '!abc123:server.com',
            'wolves': '!def456:server.com',
            'dead': '!ghi789:server.com',
        }
        self.db.save_room_state(rooms)

        loaded = self.db.load_room_state()
        assert loaded == rooms

    def test_rooms_with_couple(self):
        rooms = {
            'village': '!abc:s',
            'wolves': '!def:s',
            'couple': '!jkl:s',
            'dead': '!ghi:s',
        }
        self.db.save_room_state(rooms)

        loaded = self.db.load_room_state()
        assert loaded['couple'] == '!jkl:s'

    def test_rooms_survive_reconnection(self):
        rooms = {'village': '!test:s', 'wolves': '!wolves:s'}
        self.db.save_room_state(rooms)

        self.db.close()
        db2 = GameDatabase(self.tmp.name)
        loaded = db2.load_room_state()
        assert loaded == rooms
        db2.close()

    def test_clear_rooms_with_game(self):
        rooms = {'village': '!test:s'}
        self.db.save_room_state(rooms)

        players = {}
        p = Player("test", "@test:s")
        role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        role.assign_to_player(p)
        players["@test:s"] = p
        self.db.save_game_state(
            phase=GamePhase.NIGHT, day_count=1, start_time=None,
            players=players, votes={}, wolf_votes={},
        )

        self.db.clear_current_game()
        loaded = self.db.load_room_state()
        assert loaded == {}

    def test_none_rooms_excluded(self):
        rooms = {
            'village': '!abc:s',
            'wolves': None,
            'couple': None,
            'dead': '!ghi:s',
        }
        self.db.save_room_state(rooms)

        loaded = self.db.load_room_state()
        assert 'wolves' not in loaded
        assert 'couple' not in loaded
        assert loaded['village'] == '!abc:s'
