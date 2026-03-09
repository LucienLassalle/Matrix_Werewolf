"""Tests complets de persistance : sauvegarde et restauration complète de l'état.

Vérifie que l'état intégral d'une partie peut être sauvegardé puis restauré
après un redémarrage du bot, y compris :
- Phase, compteurs, identifiant de partie
- Joueurs (rôles, vivant/mort, maire, amoureux, mentor, cible, etc.)
- États internes des rôles (potions sorcière, garde, etc.)
- Votes (village, loups, maire)
- Ordre d'assise, élection du maire, succession, extra rôles
"""

import os
import json
import pytest
import tempfile
from datetime import datetime

from database.game_db import GameDatabase
from game.game_manager import GameManager
from game.vote_manager import VoteManager
from models.enums import GamePhase, Team, RoleType, ActionType
from models.player import Player
from roles import RoleFactory


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def _make_game(db_path: str, n_players: int = 6, role_config=None) -> GameManager:
    """Crée un GameManager avec une partie démarrée.

    Par défaut : 1 loup, 1 sorcière, 1 voyante, 1 chasseur, 2 villageois.
    """
    gm = GameManager(db_path=db_path)

    if role_config is None:
        role_config = {
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: max(0, n_players - 4),
        }

    ids = [f"@player{i}:server.com" for i in range(n_players)]
    for uid in ids:
        pseudo = uid.split(":")[0].lstrip("@")
        gm.add_player(pseudo, uid)
        gm.players[uid].display_name = f"Display_{pseudo}"

    gm.set_roles(role_config)
    result = gm.start_game(immediate_night=True)
    assert result["success"], f"Échec start_game: {result.get('message')}"
    return gm


def _load_into_new_gm(db_path: str) -> GameManager:
    """Ouvre une nouvelle instance de GameManager et restaure l'état."""
    gm2 = GameManager(db_path=db_path)
    ok = gm2.load_state()
    assert ok, "load_state() a retourné False"
    return gm2


# ═══════════════════════════════════════════════════════════
#  Tests de base : sauvegarde/restauration phase + compteurs
# ═══════════════════════════════════════════════════════════

class TestBasicPersistence:
    """Vérifie la restauration des attributs de base du GameManager."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_phase_restored(self):
        """La phase est correctement restaurée."""
        gm = _make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.phase == GamePhase.NIGHT
        gm2.db.close()
        gm.db.close()

    def test_day_night_counters_restored(self):
        """Les compteurs jour/nuit sont restaurés."""
        gm = _make_game(self.tmp.name)
        assert gm.night_count == 1
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.day_count == gm.day_count
        assert gm2.night_count == gm.night_count
        gm2.db.close()
        gm.db.close()

    def test_game_id_restored(self):
        """L'identifiant de partie est restauré."""
        gm = _make_game(self.tmp.name)
        original_id = gm.game_id
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.game_id == original_id
        gm2.db.close()
        gm.db.close()

    def test_start_time_restored(self):
        """Le start_time est restauré."""
        gm = _make_game(self.tmp.name)
        assert gm.start_time is not None
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.start_time is not None
        # Tolérance d'une seconde en raison de la sérialisation ISO
        assert abs((gm2.start_time - gm.start_time).total_seconds()) < 1
        gm2.db.close()
        gm.db.close()

    def test_mayor_election_done_restored(self):
        """Le flag mayor_election_done est restauré."""
        gm = _make_game(self.tmp.name)
        gm.mayor_election_done = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.mayor_election_done is True
        gm2.db.close()
        gm.db.close()

    def test_cupidon_wins_config_restored(self):
        """La config cupidon_wins_with_couple est restaurée."""
        gm = _make_game(self.tmp.name)
        gm.cupidon_wins_with_couple = False
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.cupidon_wins_with_couple is False
        gm2.db.close()
        gm.db.close()

    def test_game_log_restored(self):
        """Le game_log est restauré."""
        gm = _make_game(self.tmp.name)
        gm.log("Événement test")
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert "Événement test" in gm2.game_log
        gm2.db.close()
        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests joueurs : attributs, rôles, relations
# ═══════════════════════════════════════════════════════════

class TestPlayerPersistence:
    """Vérifie la restauration complète des joueurs."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_all_players_restored(self):
        """Tous les joueurs sont restaurés."""
        gm = _make_game(self.tmp.name)
        n = len(gm.players)
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert len(gm2.players) == n
        gm2.db.close()
        gm.db.close()

    def test_player_pseudo_and_uid(self):
        """Le pseudo et user_id sont restaurés."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        original = gm.players[uid]
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        restored = gm2.players[uid]
        assert restored.pseudo == original.pseudo
        assert restored.user_id == original.user_id
        gm2.db.close()
        gm.db.close()

    def test_player_display_name_restored(self):
        """Le display_name est restauré."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].display_name = "CustomName"
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].display_name == "CustomName"
        gm2.db.close()
        gm.db.close()

    def test_player_alive_status(self):
        """Le statut vivant/mort est restauré."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_alive = False
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_alive is False
        gm2.db.close()
        gm.db.close()

    def test_player_mayor_status(self):
        """Le statut de maire est restauré."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_mayor = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_mayor is True
        gm2.db.close()
        gm.db.close()

    def test_player_protected_status(self):
        """Le statut de protection est restauré."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].is_protected = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].is_protected is True
        gm2.db.close()
        gm.db.close()

    def test_player_can_vote(self):
        """Le droit de vote est restauré."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].can_vote = False
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].can_vote is False
        gm2.db.close()
        gm.db.close()

    def test_player_has_been_pardoned(self):
        """Le flag has_been_pardoned est restauré (Idiot)."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].has_been_pardoned = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].has_been_pardoned is True
        gm2.db.close()
        gm.db.close()

    def test_player_votes_against(self):
        """Le compteur votes_against est restauré (Corbeau)."""
        gm = _make_game(self.tmp.name)
        uid = list(gm.players.keys())[0]
        gm.players[uid].votes_against = 3
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.players[uid].votes_against == 3
        gm2.db.close()
        gm.db.close()

    def test_player_role_type_restored(self):
        """Le type de rôle est restauré pour chaque joueur."""
        gm = _make_game(self.tmp.name)
        roles_before = {
            uid: p.role.role_type for uid, p in gm.players.items() if p.role
        }
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        for uid, rt in roles_before.items():
            assert gm2.players[uid].role is not None, f"Joueur {uid} n'a pas de rôle"
            assert gm2.players[uid].role.role_type == rt, (
                f"Joueur {uid}: attendu {rt}, obtenu {gm2.players[uid].role.role_type}"
            )
        gm2.db.close()
        gm.db.close()

    def test_player_order_restored(self):
        """L'ordre d'assise est restauré."""
        gm = _make_game(self.tmp.name)
        order_before = list(gm._player_order)
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2._player_order == order_before
        gm2.db.close()
        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests relations inter-joueurs (lover, mentor, target)
# ═══════════════════════════════════════════════════════════

class TestRelationsPersistence:
    """Vérifie la restauration des relations entre joueurs."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_lover_relation_restored(self):
        """Les amoureux sont correctement restaurés."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())
        p0, p1 = gm.players[uids[0]], gm.players[uids[1]]
        p0.lover = p1
        p1.lover = p0
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        r0, r1 = gm2.players[uids[0]], gm2.players[uids[1]]
        assert r0.lover is not None
        assert r0.lover.user_id == p1.user_id
        assert r1.lover is not None
        assert r1.lover.user_id == p0.user_id
        gm2.db.close()
        gm.db.close()

    def test_mentor_relation_restored(self):
        """Le mentor de l'enfant sauvage est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.ENFANT_SAUVAGE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        # Trouver l'enfant sauvage
        es_player = None
        for p in gm.players.values():
            if p.role and p.role.role_type == RoleType.ENFANT_SAUVAGE:
                es_player = p
                break

        if es_player:
            # Assigner un mentor manuellement
            mentor = [p for p in gm.players.values() if p != es_player][0]
            es_player.mentor = mentor
            es_player.role.has_chosen_mentor = True
            gm.save_state()

            gm2 = _load_into_new_gm(self.tmp.name)
            restored_es = gm2.players[es_player.user_id]
            assert restored_es.mentor is not None
            assert restored_es.mentor.user_id == mentor.user_id
            gm2.db.close()

        gm.db.close()

    def test_mercenaire_target_restored(self):
        """La cible du mercenaire est restaurée."""
        gm = _make_game(self.tmp.name, 7, role_config={
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

            gm2 = _load_into_new_gm(self.tmp.name)
            restored_merc = gm2.players[merc_player.user_id]
            assert restored_merc.target is not None
            assert restored_merc.target.user_id == target.user_id
            gm2.db.close()

        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests états des rôles
# ═══════════════════════════════════════════════════════════

class TestRoleStatePersistence:
    """Vérifie la restauration de l'état interne des rôles."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def _find_player_by_role(self, gm, role_type):
        for p in gm.players.values():
            if p.role and p.role.role_type == role_type:
                return p
        return None

    def test_sorciere_potions_restored(self):
        """Les potions de la sorcière sont restaurées."""
        gm = _make_game(self.tmp.name)
        sorc = self._find_player_by_role(gm, RoleType.SORCIERE)
        assert sorc is not None

        sorc.role.has_life_potion = False
        sorc.role.has_death_potion = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        sorc2 = self._find_player_by_role(gm2, RoleType.SORCIERE)
        assert sorc2.role.has_life_potion is False
        assert sorc2.role.has_death_potion is True
        gm2.db.close()
        gm.db.close()

    def test_chasseur_state_restored(self):
        """L'état du chasseur est restauré (has_shot, can_shoot_now)."""
        gm = _make_game(self.tmp.name)
        hunter = self._find_player_by_role(gm, RoleType.CHASSEUR)
        assert hunter is not None

        hunter.role.has_shot = True
        hunter.role.can_shoot_now = False
        hunter.role.killed_during_day = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        h2 = self._find_player_by_role(gm2, RoleType.CHASSEUR)
        assert h2.role.has_shot is True
        assert h2.role.can_shoot_now is False
        assert h2.role.killed_during_day is True
        gm2.db.close()
        gm.db.close()

    def test_garde_last_protected_restored(self):
        """Le last_protected du garde est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.GARDE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        garde = self._find_player_by_role(gm, RoleType.GARDE)
        if not garde:
            pytest.skip("Garde non trouvé (aléa distribution)")

        target = [p for p in gm.players.values() if p != garde][0]
        garde.role.last_protected = target
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        g2 = self._find_player_by_role(gm2, RoleType.GARDE)
        assert g2.role.last_protected is not None
        assert g2.role.last_protected.user_id == target.user_id
        gm2.db.close()
        gm.db.close()

    def test_cupidon_has_used_power_restored(self):
        """Le flag has_used_power du Cupidon est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.CUPIDON: 1,
            RoleType.VILLAGEOIS: 2,
        })
        cupidon = self._find_player_by_role(gm, RoleType.CUPIDON)
        if not cupidon:
            pytest.skip("Cupidon non trouvé")

        cupidon.role.has_used_power = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        c2 = self._find_player_by_role(gm2, RoleType.CUPIDON)
        assert c2.role.has_used_power is True
        gm2.db.close()
        gm.db.close()

    def test_loup_noir_conversion_restored(self):
        """Le flag has_used_conversion du Loup Noir est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_NOIR: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        ln = self._find_player_by_role(gm, RoleType.LOUP_NOIR)
        if not ln:
            pytest.skip("Loup Noir non trouvé")

        ln.role.has_used_conversion = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        ln2 = self._find_player_by_role(gm2, RoleType.LOUP_NOIR)
        assert ln2.role.has_used_conversion is True
        gm2.db.close()
        gm.db.close()

    def test_loup_blanc_night_count_restored(self):
        """Le night_count du Loup Blanc est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_BLANC: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        lb = self._find_player_by_role(gm, RoleType.LOUP_BLANC)
        if not lb:
            pytest.skip("Loup Blanc non trouvé")

        lb.role.night_count = 5
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        lb2 = self._find_player_by_role(gm2, RoleType.LOUP_BLANC)
        assert lb2.role.night_count == 5
        gm2.db.close()
        gm.db.close()

    def test_loup_bavard_state_restored(self):
        """L'état du Loup Bavard est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_BAVARD: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        bavard = self._find_player_by_role(gm, RoleType.LOUP_BAVARD)
        if not bavard:
            pytest.skip("Loup Bavard non trouvé")

        bavard.role.word_to_say = "fromage"
        bavard.role.has_said_word = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        b2 = self._find_player_by_role(gm2, RoleType.LOUP_BAVARD)
        assert b2.role.word_to_say == "fromage"
        assert b2.role.has_said_word is True
        gm2.db.close()
        gm.db.close()

    def test_dictateur_state_restored(self):
        """L'état du Dictateur est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.DICTATEUR: 1,
            RoleType.VILLAGEOIS: 2,
        })
        dicta = self._find_player_by_role(gm, RoleType.DICTATEUR)
        if not dicta:
            pytest.skip("Dictateur non trouvé")

        dicta.role.has_used_power = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        d2 = self._find_player_by_role(gm2, RoleType.DICTATEUR)
        assert d2.role.has_used_power is True
        gm2.db.close()
        gm.db.close()

    def test_enfant_sauvage_state_restored(self):
        """L'état de l'Enfant Sauvage est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.ENFANT_SAUVAGE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        es = self._find_player_by_role(gm, RoleType.ENFANT_SAUVAGE)
        if not es:
            pytest.skip("Enfant Sauvage non trouvé")

        mentor = [p for p in gm.players.values() if p != es][0]
        es.mentor = mentor
        es.role.has_chosen_mentor = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        es2 = self._find_player_by_role(gm2, RoleType.ENFANT_SAUVAGE)
        assert es2.role.has_chosen_mentor is True
        gm2.db.close()
        gm.db.close()

    def test_mercenaire_full_state_restored(self):
        """L'état complet du Mercenaire est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.MERCENAIRE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        merc = self._find_player_by_role(gm, RoleType.MERCENAIRE)
        if not merc:
            pytest.skip("Mercenaire non trouvé")

        target = [p for p in gm.players.values() if p != merc][0]
        merc.target = target
        merc.role.target_assigned = True
        merc.role.has_won = True
        merc.role.days_elapsed = 2
        merc.role.deadline = 3
        merc.role.team = Team.GENTIL
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        m2 = self._find_player_by_role(gm2, RoleType.MERCENAIRE)
        assert m2.role.target_assigned is True
        assert m2.role.has_won is True
        assert m2.role.days_elapsed == 2
        assert m2.role.deadline == 3
        assert m2.role.team == Team.GENTIL
        gm2.db.close()
        gm.db.close()

    def test_loup_voyant_pack_status_restored(self):
        """Le statut _can_vote_with_pack du Loup Voyant est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_VOYANT: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        lv = self._find_player_by_role(gm, RoleType.LOUP_VOYANT)
        if not lv:
            pytest.skip("Loup Voyant non trouvé")

        lv.role._can_vote_with_pack = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        lv2 = self._find_player_by_role(gm2, RoleType.LOUP_VOYANT)
        assert lv2.role._can_vote_with_pack is True
        gm2.db.close()
        gm.db.close()

    def test_voleur_has_used_power_restored(self):
        """Le flag has_used_power du Voleur est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VOLEUR: 1,
            RoleType.VILLAGEOIS: 2,
        })
        voleur = self._find_player_by_role(gm, RoleType.VOLEUR)
        if not voleur:
            pytest.skip("Voleur non trouvé")

        voleur.role.has_used_power = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        v2 = self._find_player_by_role(gm2, RoleType.VOLEUR)
        assert v2.role.has_used_power is True
        gm2.db.close()
        gm.db.close()

    def test_corbeau_state_restored(self):
        """L'état du Corbeau est restauré."""
        gm = _make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.CORBEAU: 1,
            RoleType.VILLAGEOIS: 2,
        })
        corbeau = self._find_player_by_role(gm, RoleType.CORBEAU)
        if not corbeau:
            pytest.skip("Corbeau non trouvé")

        corbeau.role.has_used_power_tonight = True
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        c2 = self._find_player_by_role(gm2, RoleType.CORBEAU)
        assert c2.role.has_used_power_tonight is True
        gm2.db.close()
        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests votes
# ═══════════════════════════════════════════════════════════

class TestVotePersistence:
    """Vérifie la restauration des votes."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_village_votes_restored(self):
        """Les votes du village sont restaurés."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())
        voter = gm.players[uids[0]]
        target = gm.players[uids[1]]
        gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert uids[0] in gm2.vote_manager.votes
        assert gm2.vote_manager.votes[uids[0]] == uids[1]
        gm2.db.close()
        gm.db.close()

    def test_wolf_votes_restored(self):
        """Les votes des loups sont restaurés."""
        gm = _make_game(self.tmp.name)
        wolves = [p for p in gm.players.values() if p.get_team() == Team.MECHANT]
        villagers = [p for p in gm.players.values() if p.get_team() == Team.GENTIL]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)
            gm.save_state()

            gm2 = _load_into_new_gm(self.tmp.name)
            assert wolves[0].user_id in gm2.vote_manager.wolf_votes
            assert gm2.vote_manager.wolf_votes[wolves[0].user_id] == villagers[0].user_id
            gm2.db.close()

        gm.db.close()

    def test_mayor_votes_restored(self):
        """Les votes pour le maire sont restaurés."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())
        voter = gm.players[uids[0]]
        candidate = gm.players[uids[1]]
        gm.vote_manager.cast_mayor_vote_for(voter, candidate)
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert uids[0] in gm2.vote_manager.mayor_votes_for
        assert gm2.vote_manager.mayor_votes_for[uids[0]] == uids[1]
        gm2.db.close()
        gm.db.close()

    def test_multiple_votes_restored(self):
        """Plusieurs votes sont tous restaurés correctement."""
        gm = _make_game(self.tmp.name, 8, role_config={
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        uids = list(gm.players.keys())
        # Plusieurs votes village
        for i in range(4):
            voter = gm.players[uids[i]]
            target = gm.players[uids[(i + 1) % len(uids)]]
            gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert len(gm2.vote_manager.votes) == 4
        gm2.db.close()
        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests de la table room_state
# ═══════════════════════════════════════════════════════════

class TestRoomStatePersistence:
    """Vérifie la sauvegarde et restauration des IDs de salons Matrix."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = GameDatabase(self.tmp.name)

    def teardown_method(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_save_and_load_rooms(self):
        """Les salons sont sauvegardés et restaurés."""
        rooms = {
            'village': '!abc123:server.com',
            'wolves': '!def456:server.com',
            'dead': '!ghi789:server.com',
        }
        self.db.save_room_state(rooms)

        loaded = self.db.load_room_state()
        assert loaded == rooms

    def test_rooms_with_couple(self):
        """Le salon du couple est aussi sauvegardé."""
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
        """Les salons persistent après fermeture/réouverture."""
        rooms = {'village': '!test:s', 'wolves': '!wolves:s'}
        self.db.save_room_state(rooms)

        self.db.close()
        db2 = GameDatabase(self.tmp.name)
        loaded = db2.load_room_state()
        assert loaded == rooms
        db2.close()

    def test_clear_rooms_with_game(self):
        """clear_current_game efface aussi les salons."""
        rooms = {'village': '!test:s'}
        self.db.save_room_state(rooms)

        # Sauvegarder un état de jeu minimal pour pouvoir le clear
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
        """Les salons None ne sont pas sauvegardés."""
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


# ═══════════════════════════════════════════════════════════
#  Tests scénarios de crash réalistes
# ═══════════════════════════════════════════════════════════

class TestCrashScenarios:
    """Simule des crashs à différents moments de la partie."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_crash_during_first_night(self):
        """Crash pendant la première nuit → restauration complète."""
        gm = _make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        assert gm.night_count == 1

        # Simuler des actions de nuit
        wolves = [p for p in gm.players.values() if p.get_team() == Team.MECHANT]
        villagers = [p for p in gm.players.values() if p.get_team() == Team.GENTIL]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)

        gm.save_state()
        gm.db.close()

        # Simuler redémarrage du bot
        gm2 = GameManager(db_path=self.tmp.name)
        assert gm2.db.has_active_game()
        ok = gm2.load_state()
        assert ok

        assert gm2.phase == GamePhase.NIGHT
        assert gm2.night_count == 1
        assert len(gm2.players) == len(gm.players)

        # Vérifier que les votes des loups sont restaurés
        if wolves:
            assert wolves[0].user_id in gm2.vote_manager.wolf_votes

        # Vérifier que les rôles sont bien assignés
        for p in gm2.players.values():
            assert p.role is not None, f"Joueur {p.pseudo} n'a pas de rôle après restauration"

        gm2.db.close()

    def test_crash_during_day_phase(self):
        """Crash pendant le jour → restauration avec votes de village."""
        gm = _make_game(self.tmp.name)

        # Finir la nuit et passer au jour
        result = gm.end_night()
        assert gm.phase in (GamePhase.DAY, GamePhase.ENDED)

        if gm.phase == GamePhase.ENDED:
            gm.db.close()
            pytest.skip("La partie s'est terminée pendant la nuit (cas rare)")

        # Voter
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
        """Crash après utilisation d'une potion → état du rôle préservé."""
        gm = _make_game(self.tmp.name)

        # Trouver la sorcière et lui faire utiliser une potion
        sorc = None
        for p in gm.players.values():
            if p.role and p.role.role_type == RoleType.SORCIERE:
                sorc = p
                break
        assert sorc is not None

        sorc.role.has_life_potion = False  # Potion de vie utilisée
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
        """Crash avec des joueurs morts → statut mort préservé."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())

        # Tuer un joueur
        gm.players[uids[0]].is_alive = False
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok
        assert gm2.players[uids[0]].is_alive is False
        # Les autres sont vivants
        for uid in uids[1:]:
            assert gm2.players[uid].is_alive is True
        gm2.db.close()

    def test_crash_with_mayor_succession_pending(self):
        """Crash pendant une succession de maire → état restauré."""
        gm = _make_game(self.tmp.name)
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
        """Crash avec couple formé → relation amoureux restaurée."""
        gm = _make_game(self.tmp.name)
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
        """Sauvegarde en nuit 1, restaure, puis continue la partie normalement."""
        gm = _make_game(self.tmp.name)
        assert gm.phase == GamePhase.NIGHT
        gm.save_state()
        original_players = {uid: p.role.role_type for uid, p in gm.players.items()}
        gm.db.close()

        # Restaurer
        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        # Vérifier que les rôles sont corrects
        for uid, rt in original_players.items():
            assert gm2.players[uid].role.role_type == rt

        # Vérifier que end_night fonctionne après restauration
        result = gm2.end_night()
        assert result["success"] is True
        assert gm2.phase in (GamePhase.DAY, GamePhase.ENDED)
        gm2.db.close()

    def test_extra_roles_restored(self):
        """Les extra_roles (Voleur) sont restaurés."""
        gm = _make_game(self.tmp.name)
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
        """Après restauration, le VoteManager peut résoudre les joueurs."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())

        # Ajouter un vote
        voter = gm.players[uids[0]]
        target = gm.players[uids[1]]
        gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()
        gm.db.close()

        gm2 = GameManager(db_path=self.tmp.name)
        ok = gm2.load_state()
        assert ok

        # Vérifier que le player cache du VoteManager est peuplé
        for uid in uids:
            assert gm2.vote_manager._player_cache.get(uid) is not None, (
                f"Joueur {uid} absent du cache VoteManager"
            )

        # Vérifier que count_votes fonctionne
        counts = gm2.vote_manager.count_votes()
        assert uids[1] in counts
        gm2.db.close()

    def test_load_state_returns_false_when_empty(self):
        """load_state retourne False quand il n'y a rien à restaurer."""
        gm = GameManager(db_path=self.tmp.name)
        assert gm.load_state() is False
        gm.db.close()

    def test_has_active_game_after_save(self):
        """has_active_game détecte une partie en cours après save_state."""
        gm = _make_game(self.tmp.name)
        gm.save_state()

        db2 = GameDatabase(self.tmp.name)
        assert db2.has_active_game() is True
        db2.close()
        gm.db.close()

    def test_multiple_save_restore_cycles(self):
        """Plusieurs cycles sauvegarde/restauration ne corrompent pas les données."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())

        for cycle in range(3):
            # Modifier l'état
            gm.players[uids[0]].votes_against = cycle
            gm.save_state()

            # Recharger
            gm2 = GameManager(db_path=self.tmp.name)
            ok = gm2.load_state()
            assert ok
            assert gm2.players[uids[0]].votes_against == cycle
            gm2.db.close()

        gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests VoteManager complet après restauration
# ═══════════════════════════════════════════════════════════

class TestVoteManagerAfterRestore:
    """Vérifie que le VoteManager fonctionne normalement après restauration."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_can_add_votes_after_restore(self):
        """On peut ajouter des votes après restauration."""
        gm = _make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        uids = list(gm2.players.keys())
        voter = gm2.players[uids[0]]
        target = gm2.players[uids[1]]
        result = gm2.vote_manager.cast_vote(voter, target)
        assert result["success"]
        gm2.db.close()

    def test_get_most_voted_after_restore(self):
        """get_most_voted fonctionne après restauration."""
        gm = _make_game(self.tmp.name)
        uids = list(gm.players.keys())

        # 3 joueurs votent pour la même cible
        for i in range(3):
            gm.vote_manager.cast_vote(gm.players[uids[i]], gm.players[uids[3]])

        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        most_voted = gm2.vote_manager.get_most_voted()
        assert most_voted is not None
        assert most_voted.user_id == uids[3]
        gm2.db.close()

    def test_wolf_vote_resolution_after_restore(self):
        """Les votes loups sont résolubles après restauration."""
        gm = _make_game(self.tmp.name)
        wolves = [p for p in gm.players.values() if p.get_team() == Team.MECHANT]
        villagers = [p for p in gm.players.values() if p.get_team() == Team.GENTIL]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)
            gm.save_state()
            gm.db.close()

            gm2 = _load_into_new_gm(self.tmp.name)
            wolf_target = gm2.vote_manager.get_most_voted(is_wolf_vote=True)
            assert wolf_target is not None
            assert wolf_target.user_id == villagers[0].user_id
            gm2.db.close()
        else:
            gm.db.close()


# ═══════════════════════════════════════════════════════════
#  Tests GameManager continue après restauration
# ═══════════════════════════════════════════════════════════

class TestGameContinuationAfterRestore:
    """Vérifie que le jeu peut continuer normalement après restauration."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_end_night_after_restore(self):
        """end_night fonctionne après restauration."""
        gm = _make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        result = gm2.end_night()
        assert result["success"]
        gm2.db.close()

    def test_get_living_players_after_restore(self):
        """get_living_players fonctionne après restauration."""
        gm = _make_game(self.tmp.name)
        expected_living = len(gm.get_living_players())
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert len(gm2.get_living_players()) == expected_living
        gm2.db.close()

    def test_get_living_wolves_after_restore(self):
        """get_living_wolves fonctionne après restauration."""
        gm = _make_game(self.tmp.name)
        expected_wolves = len(gm.get_living_wolves())
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert len(gm2.get_living_wolves()) == expected_wolves
        gm2.db.close()

    def test_check_win_condition_after_restore(self):
        """check_win_condition fonctionne après restauration."""
        gm = _make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        # Pas de gagnant en début de partie
        assert gm2.check_win_condition() is None
        gm2.db.close()

    def test_get_neighbors_after_restore(self):
        """get_neighbors fonctionne avec l'ordre d'assise restauré."""
        gm = _make_game(self.tmp.name)
        uid = gm._player_order[0]
        neighbors_before = gm.get_neighbors(gm.players[uid])
        neighbor_uids = [n.user_id for n in neighbors_before]
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        neighbors_after = gm2.get_neighbors(gm2.players[uid])
        restored_neighbor_uids = [n.user_id for n in neighbors_after]
        assert restored_neighbor_uids == neighbor_uids
        gm2.db.close()

    def test_full_game_cycle_after_restore(self):
        """Jouer un cycle complet (nuit → jour → vote → nuit) après restauration."""
        gm = _make_game(self.tmp.name, 8, role_config={
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        gm.save_state()
        gm.db.close()

        gm2 = _load_into_new_gm(self.tmp.name)
        assert gm2.phase == GamePhase.NIGHT

        # 1. Finir la nuit
        result = gm2.end_night()
        assert result["success"]

        if gm2.phase == GamePhase.ENDED:
            gm2.db.close()
            return  # Rare edge case

        # 2. Commencer le vote
        assert gm2.phase == GamePhase.DAY
        vote_result = gm2.start_vote_phase()
        assert vote_result["success"]
        assert gm2.phase == GamePhase.VOTE

        # 3. Voter et terminer
        living = gm2.get_living_players()
        if len(living) >= 2:
            gm2.vote_manager.cast_vote(living[0], living[1])
            end_result = gm2.end_vote_phase()
            assert end_result["success"]

        gm2.db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
