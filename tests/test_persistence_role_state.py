"""Tests de persistance des etats de roles."""

import os
import tempfile

import pytest

from models.enums import RoleType, Team
from tests.persistence_helpers import make_game, load_into_new_gm


class TestRoleStatePersistence:
    """Verifie la restauration de l'etat interne des roles."""

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
        gm = make_game(self.tmp.name)
        sorc = self._find_player_by_role(gm, RoleType.SORCIERE)
        assert sorc is not None

        sorc.role.has_life_potion = False
        sorc.role.has_death_potion = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        sorc2 = self._find_player_by_role(gm2, RoleType.SORCIERE)
        assert sorc2.role.has_life_potion is False
        assert sorc2.role.has_death_potion is True
        gm2.db.close()
        gm.db.close()

    def test_chasseur_state_restored(self):
        gm = make_game(self.tmp.name)
        hunter = self._find_player_by_role(gm, RoleType.CHASSEUR)
        assert hunter is not None

        hunter.role.has_shot = True
        hunter.role.can_shoot_now = False
        hunter.role.killed_during_day = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        h2 = self._find_player_by_role(gm2, RoleType.CHASSEUR)
        assert h2.role.has_shot is True
        assert h2.role.can_shoot_now is False
        assert h2.role.killed_during_day is True
        gm2.db.close()
        gm.db.close()

    def test_garde_last_protected_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
            RoleType.LOUP_GAROU: 1,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.GARDE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        garde = self._find_player_by_role(gm, RoleType.GARDE)
        if not garde:
            pytest.skip("Garde non trouvé (alea distribution)")

        target = [p for p in gm.players.values() if p != garde][0]
        garde.role.last_protected = target
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        g2 = self._find_player_by_role(gm2, RoleType.GARDE)
        assert g2.role.last_protected is not None
        assert g2.role.last_protected.user_id == target.user_id
        gm2.db.close()
        gm.db.close()

    def test_cupidon_has_used_power_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        c2 = self._find_player_by_role(gm2, RoleType.CUPIDON)
        assert c2.role.has_used_power is True
        gm2.db.close()
        gm.db.close()

    def test_loup_noir_conversion_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        ln2 = self._find_player_by_role(gm2, RoleType.LOUP_NOIR)
        assert ln2.role.has_used_conversion is True
        gm2.db.close()
        gm.db.close()

    def test_loup_blanc_night_count_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        lb2 = self._find_player_by_role(gm2, RoleType.LOUP_BLANC)
        assert lb2.role.night_count == 5
        gm2.db.close()
        gm.db.close()

    def test_loup_bavard_state_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        b2 = self._find_player_by_role(gm2, RoleType.LOUP_BAVARD)
        assert b2.role.word_to_say == "fromage"
        assert b2.role.has_said_word is True
        gm2.db.close()
        gm.db.close()

    def test_dictateur_state_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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
        dicta.role.is_armed = True
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        d2 = self._find_player_by_role(gm2, RoleType.DICTATEUR)
        assert d2.role.has_used_power is True
        assert d2.role.is_armed is True
        gm2.db.close()
        gm.db.close()

    def test_enfant_sauvage_state_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        es2 = self._find_player_by_role(gm2, RoleType.ENFANT_SAUVAGE)
        assert es2.role.has_chosen_mentor is True
        gm2.db.close()
        gm.db.close()

    def test_mercenaire_full_state_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        m2 = self._find_player_by_role(gm2, RoleType.MERCENAIRE)
        assert m2.role.target_assigned is True
        assert m2.role.has_won is True
        assert m2.role.days_elapsed == 2
        assert m2.role.deadline == 3
        assert m2.role.team == Team.GENTIL
        gm2.db.close()
        gm.db.close()

    def test_loup_voyant_pack_status_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        lv2 = self._find_player_by_role(gm2, RoleType.LOUP_VOYANT)
        assert lv2.role._can_vote_with_pack is True
        gm2.db.close()
        gm.db.close()

    def test_voleur_has_used_power_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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

        gm2 = load_into_new_gm(self.tmp.name)
        v2 = self._find_player_by_role(gm2, RoleType.VOLEUR)
        assert v2.role.has_used_power is True
        gm2.db.close()
        gm.db.close()

    def test_corbeau_state_restored(self):
        gm = make_game(self.tmp.name, 7, role_config={
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
        corbeau.role.current_target_id = corbeau.user_id
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        c2 = self._find_player_by_role(gm2, RoleType.CORBEAU)
        assert c2.role.has_used_power_tonight is True
        assert c2.role.current_target_id == corbeau.user_id
        gm2.db.close()
        gm.db.close()
