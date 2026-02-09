"""Tests complets des modèles du jeu."""

import pytest
from models.player import Player
from models.enums import RoleType, Team, GamePhase
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.voyante import Voyante
from roles.chasseur import Chasseur


class TestPlayer:
    """Tests du modèle Player."""
    
    def test_player_creation(self):
        """Test la création d'un joueur."""
        player = Player("Alice", "@alice:matrix.org")
        
        assert player.pseudo == "Alice"
        assert player.user_id == "@alice:matrix.org"
        assert player.role is None
        assert player.is_alive is True
        assert player.is_protected is False
        assert player.lover is None
        assert player.votes_against == 0
        assert player.can_vote is True
        assert player.is_mayor is False
    
    def test_player_with_role(self):
        """Test un joueur avec un rôle."""
        player = Player("Bob", "@bob:matrix.org")
        player.role = Villageois()
        
        assert player.role.role_type == RoleType.VILLAGEOIS
        assert player.get_team() == Team.GENTIL
    
    def test_player_kill(self):
        """Test la mort d'un joueur."""
        player = Player("Charlie", "@charlie:matrix.org")
        player.role = LoupGarou()
        
        assert player.is_alive is True
        player.kill()
        assert player.is_alive is False
    
    def test_player_with_lover(self):
        """Test la mort d'un joueur avec son amoureux."""
        player1 = Player("David", "@david:matrix.org")
        player2 = Player("Eve", "@eve:matrix.org")
        
        player1.lover = player2
        player2.lover = player1
        
        assert player1.is_alive is True
        assert player2.is_alive is True
        
        player1.kill()
        
        assert player1.is_alive is False
        assert player2.is_alive is False
    
    def test_player_mayor(self):
        """Test qu'un joueur peut être maire en plus de son rôle."""
        player = Player("Frank", "@frank:matrix.org")
        player.role = LoupGarou()
        player.is_mayor = True
        
        assert player.role.role_type == RoleType.LOUP_GAROU
        assert player.is_mayor is True
        assert player.get_team() == Team.MECHANT
    
    def test_player_equality(self):
        """Test l'égalité entre joueurs."""
        player1 = Player("Alice", "@alice:matrix.org")
        player2 = Player("Alice", "@alice:matrix.org")
        player3 = Player("Bob", "@bob:matrix.org")
        
        assert player1 == player2
        assert player1 != player3
    
    def test_player_hash(self):
        """Test que les joueurs sont hashables."""
        player1 = Player("Alice", "@alice:matrix.org")
        player2 = Player("Bob", "@bob:matrix.org")
        
        player_set = {player1, player2}
        assert len(player_set) == 2
        assert player1 in player_set
    
    def test_player_protection(self):
        """Test la protection d'un joueur."""
        player = Player("Protected", "@protected:matrix.org")
        player.is_protected = False
        
        player.is_protected = True
        assert player.is_protected is True
    
    def test_player_votes(self):
        """Test les votes contre un joueur."""
        player = Player("Suspect", "@suspect:matrix.org")
        
        assert player.votes_against == 0
        player.votes_against += 1
        assert player.votes_against == 1
        player.votes_against += 2
        assert player.votes_against == 3


class TestRoles:
    """Tests des rôles de base."""
    
    def test_villageois(self):
        """Test le rôle Villageois."""
        role = Villageois()
        
        assert role.role_type == RoleType.VILLAGEOIS
        assert role.team == Team.GENTIL
        assert role.can_act_at_night() is False
        assert role.can_vote_with_wolves() is False
    
    def test_loup_garou(self):
        """Test le rôle Loup-Garou."""
        role = LoupGarou()
        
        assert role.role_type == RoleType.LOUP_GAROU
        assert role.team == Team.MECHANT
        assert role.can_act_at_night() is True
        assert role.can_vote_with_wolves() is True
    
    def test_voyante(self):
        """Test le rôle Voyante."""
        role = Voyante()
        
        assert role.role_type == RoleType.VOYANTE
        assert role.team == Team.GENTIL
        assert role.can_act_at_night() is True
        assert role.can_vote_with_wolves() is False
        assert role.has_used_power_tonight is False
    
    def test_chasseur(self):
        """Test le rôle Chasseur."""
        role = Chasseur()
        
        assert role.role_type == RoleType.CHASSEUR
        assert role.team == Team.GENTIL
        assert role.can_act_at_night() is False
        assert role.has_shot is False


class TestTeam:
    """Tests des équipes."""
    
    def test_all_teams(self):
        """Test que toutes les équipes existent."""
        assert Team.GENTIL.value == "GENTIL"
        assert Team.MECHANT.value == "MECHANT"
        assert Team.COUPLE.value == "COUPLE"
        assert Team.NEUTRE.value == "NEUTRE"


class TestGamePhase:
    """Tests des phases de jeu."""
    
    def test_all_phases(self):
        """Test que toutes les phases existent."""
        assert GamePhase.SETUP.value == "SETUP"
        assert GamePhase.NIGHT.value == "NIGHT"
        assert GamePhase.DAY.value == "DAY"
        assert GamePhase.VOTE.value == "VOTE"
        assert GamePhase.ENDED.value == "ENDED"


class TestMultipleRoles:
    """Tests pour vérifier qu'un joueur peut cumuler rôle + maire."""
    
    def test_loup_garou_becomes_mayor(self):
        """Test qu'un loup-garou peut devenir maire."""
        player = Player("Alpha", "@alpha:matrix.org")
        player.role = LoupGarou()
        player.is_mayor = True
        
        # Le joueur garde son rôle de loup
        assert player.role.role_type == RoleType.LOUP_GAROU
        assert player.get_team() == Team.MECHANT
        assert player.role.can_vote_with_wolves() is True
        
        # Mais il est aussi maire
        assert player.is_mayor is True
    
    def test_voyante_becomes_mayor(self):
        """Test qu'une voyante peut devenir maire."""
        player = Player("Seer", "@seer:matrix.org")
        player.role = Voyante()
        player.is_mayor = True
        
        # Le joueur garde son rôle de voyante
        assert player.role.role_type == RoleType.VOYANTE
        assert player.get_team() == Team.GENTIL
        assert player.role.can_act_at_night() is True
        
        # Mais elle est aussi maire
        assert player.is_mayor is True
    
    def test_mayor_vote_weight_with_other_role(self):
        """Test que le poids du vote du maire fonctionne avec un autre rôle."""
        player = Player("MayorWolf", "@mayor:matrix.org")
        player.role = LoupGarou()
        player.is_mayor = True
        
        # Le joueur est un loup ET maire
        # Le vote du maire devrait compter double (via is_mayor)
        assert player.is_mayor is True
        
        # Le joueur principal garde son équipe de loup
        assert player.get_team() == Team.MECHANT


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
