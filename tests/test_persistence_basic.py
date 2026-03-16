"""Tests de base de persistance."""

import os
import tempfile

from models.enums import GamePhase, RoleType
from tests.persistence_helpers import make_game, load_into_new_gm


class TestBasicPersistence:
    """Verifie la restauration des attributs de base du GameManager."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_phase_restored(self):
        gm = make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.phase == GamePhase.NIGHT
        gm2.db.close()
        gm.db.close()

    def test_day_night_counters_restored(self):
        gm = make_game(self.tmp.name)
        assert gm.night_count == 1
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.day_count == gm.day_count
        assert gm2.night_count == gm.night_count
        gm2.db.close()
        gm.db.close()

    def test_game_id_restored(self):
        gm = make_game(self.tmp.name)
        original_id = gm.game_id
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.game_id == original_id
        gm2.db.close()
        gm.db.close()

    def test_start_time_restored(self):
        gm = make_game(self.tmp.name)
        assert gm.start_time is not None
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.start_time is not None
        assert abs((gm2.start_time - gm.start_time).total_seconds()) < 1
        gm2.db.close()
        gm.db.close()

    def test_mayor_election_done_restored(self):
        gm = make_game(self.tmp.name)
        gm.mayor_election_done = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.mayor_election_done is True
        gm2.db.close()
        gm.db.close()

    def test_cupidon_wins_config_restored(self):
        gm = make_game(self.tmp.name)
        gm.cupidon_wins_with_couple = False
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.cupidon_wins_with_couple is False
        gm2.db.close()
        gm.db.close()

    def test_game_log_restored(self):
        gm = make_game(self.tmp.name)
        gm.log("Evenement test")
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert "Evenement test" in gm2.game_log
        gm2.db.close()
        gm.db.close()


class TestPlayerPersistence:
    """Verifie la restauration complete des joueurs."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_all_players_restored(self):
        gm = make_game(self.tmp.name)
        n = len(gm.players)
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert len(gm2.players) == n
        gm2.db.close()
        gm.db.close()

    def test_player_pseudo_and_uid(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        original = gm.players[uid]
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        restored = gm2.players[uid]
        assert restored.pseudo == original.pseudo
        assert restored.user_id == original.user_id
        gm2.db.close()
        gm.db.close()

    def test_player_display_name_restored(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].display_name = "CustomName"
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].display_name == "CustomName"
        gm2.db.close()
        gm.db.close()

    def test_player_alive_status(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_alive = False
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_alive is False
        gm2.db.close()
        gm.db.close()

    def test_player_mayor_status(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_mayor = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_mayor is True
        gm2.db.close()
        gm.db.close()

    def test_player_protected_status(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_protected = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_protected is True
        gm2.db.close()
        gm.db.close()

    def test_player_can_vote(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].can_vote = False
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].can_vote is False
        gm2.db.close()
        gm.db.close()

    def test_player_has_been_pardoned(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].has_been_pardoned = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].has_been_pardoned is True
        gm2.db.close()
        gm.db.close()

    def test_player_votes_against(self):
        gm = make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].votes_against = 3
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].votes_against == 3
        gm2.db.close()
        gm.db.close()

    def test_player_role_type_restored(self):
        gm = make_game(self.tmp.name)
        roles_before = {
            uid: p.role.role_type for uid, p in gm.players.items() if p.role
        }
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        for uid, rt in roles_before.items():
            assert gm2.players[uid].role is not None, f"Joueur {uid} n'a pas de role"
            assert gm2.players[uid].role.role_type == rt
        gm2.db.close()
        gm.db.close()

    def test_player_order_restored(self):
        gm = make_game(self.tmp.name)
        order_before = list(gm._player_order)
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert gm2._player_order == order_before
        gm2.db.close()
        gm.db.close()


class TestRelationsPersistence:
    """Verifie la restauration des relations entre joueurs."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_lover_relation_restored(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())
        p0, p1 = gm.players[uids[0]], gm.players[uids[1]]
        p0.lover = p1
        p1.lover = p0
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        r0, r1 = gm2.players[uids[0]], gm2.players[uids[1]]
        assert r0.lover is not None
        assert r0.lover.user_id == p1.user_id
        assert r1.lover is not None
        assert r1.lover.user_id == p0.user_id
        gm2.db.close()
        gm.db.close()

    def test_mentor_relation_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.ENFANT_SAUVAGE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        es_player = None
        for p in gm.players.values():
            if p.role and p.role.role_type == RoleType.ENFANT_SAUVAGE:
                es_player = p
                break

        if es_player:
            mentor = [p for p in gm.players.values() if p != es_player][0]
            es_player.mentor = mentor
            es_player.role.has_chosen_mentor = True
            gm.save_state()

            gm2 = load_into_new_gm(self.tmp.name)
            restored_es = gm2.players[es_player.user_id]
            assert restored_es.mentor is not None
            assert restored_es.mentor.user_id == mentor.user_id
            gm2.db.close()

        gm.db.close()

    def test_mercenaire_target_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.MERCENAIRE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        merc_player = None
        for p in gm.players.values():
            if p.role and p.role.role_type == RoleType.MERCENAIRE:
                merc_player = p
                break

        if merc_player:
            target = [p for p in gm.players.values() if p != merc_player][0]
            merc_player.target = target
            merc_player.role.target_assigned = True
            gm.save_state()

            gm2 = load_into_new_gm(self.tmp.name)
            restored_merc = gm2.players[merc_player.user_id]
            assert restored_merc.target is not None
            assert restored_merc.target.user_id == target.user_id
            gm2.db.close()

        gm.db.close()
