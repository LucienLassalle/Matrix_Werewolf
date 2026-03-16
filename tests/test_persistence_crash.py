"""Tests de crash et reprise de partie."""

import os
import tempfile

import pytest

from database.game_db import GameDatabase
from game.game_manager import GameManager
from models.enums import GamePhase, RoleType
from roles import RoleFactory
from tests.persistence_helpers import make_game, load_into_new_gm


class TestCrashScenarios:
    """Simule des crashs a differents moments de la partie."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_crash_during_first_night(self):
        gm = make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        assert gm.night_count == 1

        wolves = [p for p in gm.players.values() if p.get_team().value == "MECHANT"]
        villagers = [p for p in gm.players.values() if p.get_team().value == "GENTIL"]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)

        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        assert gm2.db.has_active_game()
        ok = gm2.load_state()
        assert ok

        assert gm2.phase == GamePhase.NIGHT
        assert gm2.night_count == 1
        assert len(gm2.players) == len(gm.players)

        if wolves:
            assert wolves[0].user_id in gm2.vote_manager.wolf_votes

        for p in gm2.players.values():
            assert p.role is not None, f"Joueur {p.pseudo} n'a pas de role apres restauration"

        gm2.db.close()

    def test_crash_during_day_phase(self):
        gm = make_game(self.tmp.name)

        result = gm.end_night()
        assert gm.phase in (GamePhase.DAY, GamePhase.ENDED)

        if gm.phase == GamePhase.ENDED:
            gm.db.close()
            pytest.skip("La partie s'est terminee pendant la nuit (cas rare)")

        living = gm.get_living_players()
        if len(living) >= 2:
            gm.vote_manager.cast_vote(living[0], living[1], is_wolf_vote=False)

        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok
        assert gm2.phase == GamePhase.DAY
        assert gm2.day_count == gm.day_count
        assert len(gm2.vote_manager.votes) > 0
        gm2.db.close()

    def test_crash_after_role_actions(self):
        gm = make_game(self.tmp.name)

        sorc = None
        for p in gm.players.values():
            if p.role and p.role.role_type == RoleType.SORCIERE:
                sorc = p
                break
        assert sorc is not None

        sorc.role.has_life_potion = False
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        sorc2 = None
        for p in gm2.players.values():
            if p.role and p.role.role_type == RoleType.SORCIERE:
                sorc2 = p
                break
        assert sorc2 is not None
        assert sorc2.role.has_life_potion is False
        assert sorc2.role.has_death_potion is True
        gm2.db.close()

    def test_crash_with_dead_players(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())

        gm.players[uids[0]].is_alive = False
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok
        assert gm2.players[uids[0]].is_alive is False
        for uid in uids[1:]:
            assert gm2.players[uid].is_alive is True
        gm2.db.close()

    def test_crash_with_mayor_succession_pending(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())
        gm.players[uids[0]].is_mayor = True
        gm._pending_mayor_succession = gm.players[uids[0]]
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok
        assert gm2._pending_mayor_succession is not None
        assert gm2._pending_mayor_succession.user_id == uids[0]
        gm2.db.close()

    def test_crash_with_lovers(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())
        p0, p1 = gm.players[uids[0]], gm.players[uids[1]]
        p0.lover = p1
        p1.lover = p0
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        r0, r1 = gm2.players[uids[0]], gm2.players[uids[1]]
        assert r0.lover is r1
        assert r1.lover is r0
        gm2.db.close()

    def test_full_night_cycle_crash_restore_continue(self):
        gm = make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        gm.save_state()
        original_players = {uid: p.role.role_type for uid, p in gm.players.items()}
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        for uid, rt in original_players.items():
            assert gm2.players[uid].role.role_type == rt

        result = gm2.end_night()
        assert result["success"] is True
        assert gm2.phase in (GamePhase.DAY, GamePhase.ENDED)
        gm2.db.close()

    def test_extra_roles_restored(self):
        gm = make_game(self.tmp.name)
        gm.extra_roles = [
            RoleFactory.create_role(RoleType.VILLAGEOIS),
            RoleFactory.create_role(RoleType.LOUP_GAROU),
        ]
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok
        assert len(gm2.extra_roles) == 2
        extra_types = [r.role_type for r in gm2.extra_roles]
        assert RoleType.VILLAGEOIS in extra_types
        assert RoleType.LOUP_GAROU in extra_types
        gm2.db.close()

    def test_vote_manager_player_cache_rebuilt(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())

        voter = gm.players[uids[0]]
        target = gm.players[uids[1]]
        gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        for uid in uids:
            assert gm2.vote_manager._player_cache.get(uid) is not None

        counts = gm2.vote_manager.count_votes()
        assert uids[1] in counts
        gm2.db.close()

    def test_load_state_returns_false_when_empty(self):
        gm = GameManager(db_path=self.tmp.name)
        assert gm.load_state() is False
        gm.db.close()

    def test_has_active_game_after_save(self):
        gm = make_game(self.tmp.name)
        gm.save_state()

        db2 = GameDatabase(self.tmp.name)
        assert db2.has_active_game() is True
        db2.close()
        gm.db.close()

    def test_multiple_save_restore_cycles(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())

        for cycle in range(3):
            gm.players[uids[0]].votes_against = cycle
            gm.save_state()

            gm2 = GameManager(db_path=self.tmp.name)
            ok = gm2.load_state()
            assert ok
            assert gm2.players[uids[0]].votes_against == cycle
            gm2.db.close()

        gm.db.close()


class TestGameContinuationAfterRestore:
    """Verifie que le jeu peut continuer normalement apres restauration."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_end_night_after_restore(self):
        gm = make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        result = gm2.end_night()
        assert result["success"]
        gm2.db.close()

    def test_get_living_players_after_restore(self):
        gm = make_game(self.tmp.name)
        expected_living = len(gm.get_living_players())
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        assert len(gm2.get_living_players()) == expected_living
        gm2.db.close()

    def test_get_living_wolves_after_restore(self):
        gm = make_game(self.tmp.name)
        expected_wolves = len(gm.get_living_wolves())
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        assert len(gm2.get_living_wolves()) == expected_wolves
        gm2.db.close()

    def test_check_win_condition_after_restore(self):
        gm = make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.check_win_condition() is None
        gm2.db.close()

    def test_get_neighbors_after_restore(self):
        gm = make_game(self.tmp.name)
        uid = gm._player_order[0]
        neighbors_before = gm.get_neighbors(gm.players[uid])
        neighbor_uids = [n.user_id for n in neighbors_before]
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        neighbors_after = gm2.get_neighbors(gm2.players[uid])
        restored_neighbor_uids = [n.user_id for n in neighbors_after]
        assert restored_neighbor_uids == neighbor_uids
        gm2.db.close()

    def test_full_game_cycle_after_restore(self):
        gm = make_game(self.tmp.name, 8, role_config={
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.phase == GamePhase.NIGHT

        result = gm2.end_night()
        assert result["success"]

        if gm2.phase == GamePhase.ENDED:
            gm2.db.close()
            return

        assert gm2.phase == GamePhase.DAY
        vote_result = gm2.start_vote_phase()
        assert vote_result["success"]
        assert gm2.phase == GamePhase.VOTE

        living = gm2.get_living_players()
        if len(living) >= 2:
            gm2.vote_manager.cast_vote(living[0], living[1])
            end_result = gm2.end_vote_phase()
            assert end_result["success"]

        gm2.db.close()
