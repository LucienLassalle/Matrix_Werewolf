"""Tests du NotificationManager : mini-tutoriels de rôle.

Couvre :
- Chaque rôle a un tutoriel non vide
- Le tutoriel est inclus dans le message formaté
- Un rôle inconnu n'a pas de tutoriel
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from matrix_bot.notifications import NotificationManager
from models.enums import Team
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.voyante import Voyante
from roles.sorciere import Sorciere
from roles.chasseur import Chasseur
from roles.cupidon import Cupidon
from roles.garde import Garde
from roles.corbeau import Corbeau
from roles.dictateur import Dictateur
from roles.voleur import Voleur
from roles.enfant_sauvage import EnfantSauvage
from roles.medium import Medium
from roles.mercenaire import Mercenaire
from roles.mentaliste import Mentaliste
from roles.petite_fille import PetiteFille
from roles.montreur_ours import MontreurOurs
from roles.loup_blanc import LoupBlanc
from roles.loup_noir import LoupNoir
from roles.loup_bavard import LoupBavard
from roles.loup_voyant import LoupVoyant
from roles.idiot import Idiot
from roles.voyante_aura import VoyanteAura


class TestRoleTutorials:
    """Tests que chaque rôle a un mini-tutoriel dans le DM de rôle."""

    def setup_method(self):
        self.room_manager = MagicMock()
        self.room_manager.send_dm = AsyncMock()
        self.nm = NotificationManager(self.room_manager)

    def test_tutorial_exists_for_villageois(self):
        tutorial = self.nm._get_role_tutorial(Villageois())
        assert tutorial != ""
        assert "!vote" in tutorial

    def test_tutorial_exists_for_loup_garou(self):
        tutorial = self.nm._get_role_tutorial(LoupGarou())
        assert tutorial != ""
        assert "meute" in tutorial.lower() or "salon des loups" in tutorial.lower()

    def test_tutorial_exists_for_voyante(self):
        tutorial = self.nm._get_role_tutorial(Voyante())
        assert tutorial != ""
        assert "!voyante" in tutorial

    def test_tutorial_exists_for_sorciere(self):
        tutorial = self.nm._get_role_tutorial(Sorciere())
        assert tutorial != ""
        assert "potion" in tutorial.lower()

    def test_tutorial_exists_for_chasseur(self):
        tutorial = self.nm._get_role_tutorial(Chasseur())
        assert tutorial != ""
        assert "!tuer" in tutorial

    def test_tutorial_exists_for_cupidon(self):
        tutorial = self.nm._get_role_tutorial(Cupidon())
        assert tutorial != ""
        assert "!cupidon" in tutorial

    def test_tutorial_exists_for_garde(self):
        tutorial = self.nm._get_role_tutorial(Garde())
        assert tutorial != ""
        assert "!garde" in tutorial

    def test_tutorial_exists_for_corbeau(self):
        tutorial = self.nm._get_role_tutorial(Corbeau())
        assert tutorial != ""
        assert "!corbeau" in tutorial

    def test_tutorial_exists_for_dictateur(self):
        tutorial = self.nm._get_role_tutorial(Dictateur())
        assert tutorial != ""
        assert "!dictateur" in tutorial

    def test_tutorial_exists_for_voleur(self):
        tutorial = self.nm._get_role_tutorial(Voleur())
        assert tutorial != ""
        assert "!voleur" in tutorial

    def test_tutorial_exists_for_enfant_sauvage(self):
        tutorial = self.nm._get_role_tutorial(EnfantSauvage())
        assert tutorial != ""
        assert "mentor" in tutorial.lower()

    def test_tutorial_exists_for_medium(self):
        tutorial = self.nm._get_role_tutorial(Medium())
        assert tutorial != ""
        assert "!medium" in tutorial

    def test_tutorial_exists_for_mercenaire(self):
        tutorial = self.nm._get_role_tutorial(Mercenaire())
        assert tutorial != ""
        assert "cible" in tutorial.lower()

    @pytest.mark.asyncio
    async def test_send_mercenaire_target(self):
        """Le Mercenaire reçoit sa cible en DM."""
        await self.nm.send_mercenaire_target("@merc:matrix.org", "Alice")
        self.room_manager.send_dm.assert_called_once()
        call_args = self.room_manager.send_dm.call_args
        assert "Alice" in call_args[0][1]
        assert "Mission" in call_args[0][1]

    def test_tutorial_exists_for_mentaliste(self):
        tutorial = self.nm._get_role_tutorial(Mentaliste())
        assert tutorial != ""

    def test_tutorial_exists_for_petite_fille(self):
        tutorial = self.nm._get_role_tutorial(PetiteFille())
        assert tutorial != ""
        assert "passif" in tutorial.lower() or "espionn" in tutorial.lower()

    def test_tutorial_exists_for_montreur_ours(self):
        tutorial = self.nm._get_role_tutorial(MontreurOurs())
        assert tutorial != ""
        assert "ours" in tutorial.lower()

    def test_tutorial_exists_for_loup_blanc(self):
        tutorial = self.nm._get_role_tutorial(LoupBlanc())
        assert tutorial != ""
        assert "dernier" in tutorial.lower() or "survivant" in tutorial.lower()

    def test_tutorial_exists_for_loup_noir(self):
        tutorial = self.nm._get_role_tutorial(LoupNoir())
        assert tutorial != ""
        assert "convertir" in tutorial.lower() or "!convertir" in tutorial

    def test_tutorial_exists_for_loup_bavard(self):
        tutorial = self.nm._get_role_tutorial(LoupBavard())
        assert tutorial != ""
        assert "mot" in tutorial.lower()

    def test_tutorial_exists_for_loup_voyant(self):
        tutorial = self.nm._get_role_tutorial(LoupVoyant())
        assert tutorial != ""
        assert "!voyante" in tutorial or "!lg" in tutorial

    def test_tutorial_exists_for_idiot(self):
        tutorial = self.nm._get_role_tutorial(Idiot())
        assert tutorial != ""

    def test_tutorial_exists_for_voyante_aura(self):
        tutorial = self.nm._get_role_tutorial(VoyanteAura())
        assert tutorial != ""
        assert "aura" in tutorial.lower()

    def test_tutorial_included_in_role_message(self):
        """Le tutoriel est inclus dans le message de rôle formaté."""
        message = self.nm._format_role_message(LoupGarou())
        assert "💡 **Comment jouer :**" in message

    def test_role_message_without_tutorial_no_header(self):
        """Un rôle inconnu n'affiche pas l'en-tête tutoriel."""
        role = MagicMock()
        role.name = "RoleInconnu"
        role.description = "Un rôle inconnu"
        role.team = Team.GENTIL
        role.can_act_at_night = MagicMock(return_value=False)

        tutorial = self.nm._get_role_tutorial(role)
        assert tutorial == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
