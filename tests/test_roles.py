"""Tests unitaires pour les rôles."""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


class TestBasicRoles:
    """Tests pour les rôles de base."""
    
    def test_villageois(self):
        """Test le rôle Villageois."""
        role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        assert role.team == Team.GENTIL
        assert "villageois" in role.get_description().lower()
        assert role.name == "Villageois"
    
    def test_loup_garou(self):
        """Test le rôle Loup-Garou."""
        role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        assert role.team == Team.MECHANT
        assert role.name == "Loup-Garou"
        assert role.can_act_at_night() == True
        
        player = Player("Wolf", "user_1")
        role.assign_to_player(player)
        assert role.can_perform_action(ActionType.VOTE) == True
    
    def test_voyante(self):
        """Test le rôle Voyante."""
        game = GameManager()
        game.add_player("Voyante", "user_1")
        game.add_player("Target", "user_2")
        
        voyante = game.players["user_1"]
        target = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.VOYANTE)
        role.assign_to_player(voyante)
        assert role.can_act_at_night() == True
        
        target_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        target_role.assign_to_player(target)
        
        result = role.perform_action(game, ActionType.SEE_ROLE, target)
        assert result["success"] == True
        assert "Loup-Garou" in result["message"]
    
    def test_chasseur(self):
        """Test le rôle Chasseur."""
        game = GameManager()
        game.add_player("Chasseur", "user_1")
        game.add_player("Target", "user_2")
        
        chasseur = game.players["user_1"]
        target = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.CHASSEUR)
        role.assign_to_player(chasseur)
        
        chasseur.kill()
        role.can_shoot_now = True
        
        result = role.perform_action(game, ActionType.KILL, target)
        assert result["success"] == True
        assert target.is_alive == False
    
    def test_sorciere(self):
        """Test le rôle Sorcière."""
        game = GameManager()
        game.add_player("Sorciere", "user_1")
        game.add_player("Target", "user_2")
        
        sorciere = game.players["user_1"]
        target = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.SORCIERE)
        role.assign_to_player(sorciere)
        assert role.can_act_at_night() == True
        
        # Test potion de vie
        assert role.has_life_potion == True
        result = role.perform_action(game, ActionType.HEAL, target)
        assert result["success"] == True
        assert role.has_life_potion == False
        
        # Test potion de mort (les deux potions peuvent être utilisées la même nuit)
        assert role.has_death_potion == True
        result = role.perform_action(game, ActionType.POISON, target)
        assert result["success"] == True
        assert role.has_death_potion == False
        # NB: La sorcière ne tue plus directement, l'action_manager gère la mort
    
    def test_cupidon(self):
        """Test le rôle Cupidon."""
        game = GameManager()
        game.add_player("Cupidon", "user_1")
        game.add_player("Target1", "user_2")
        game.add_player("Target2", "user_3")
        
        cupidon = game.players["user_1"]
        target1 = game.players["user_2"]
        target2 = game.players["user_3"]
        
        role = RoleFactory.create_role(RoleType.CUPIDON)
        role.assign_to_player(cupidon)
        assert role.can_act_at_night() == True
        
        result = role.perform_action(game, ActionType.MARRY, None, target1=target1, target2=target2)
        assert result["success"] == True
        assert target1.lover == target2
        assert target2.lover == target1
        
        target1.kill()
        assert target2.is_alive == False


class TestAdvancedRoles:
    """Tests pour les rôles avancés."""
    
    def test_loup_blanc(self):
        """Test le rôle Loup Blanc."""
        game = GameManager()
        game.add_player("LoupBlanc", "user_1")
        game.add_player("Target", "user_2")
        
        loup_blanc = game.players["user_1"]
        target = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.LOUP_BLANC)
        role.assign_to_player(loup_blanc)
        assert role.can_act_at_night() == True
        
        # Première nuit : ne peut pas tuer
        role.on_night_start(game)
        assert role.can_kill_tonight == False
        
        # Deuxième nuit : peut tuer
        role.on_night_start(game)
        assert role.can_kill_tonight == True
        
        result = role.perform_action(game, ActionType.KILL, target)
        assert result["success"] == True
    
    def test_garde(self):
        """Test le rôle Garde."""
        game = GameManager()
        game.add_player("Garde", "user_1")
        game.add_player("Target", "user_2")
        
        garde = game.players["user_1"]
        target = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.GARDE)
        role.assign_to_player(garde)
        assert role.can_act_at_night() == True
        
        result = role.perform_action(game, ActionType.PROTECT, target)
        assert result["success"] == True
        assert target.is_protected == True
        
        target.is_protected = False  # Reset
        result = role.perform_action(game, ActionType.PROTECT, target)
        assert result["success"] == False
    
    def test_enfant_sauvage(self):
        """Test le rôle Enfant Sauvage."""
        game = GameManager()
        game.add_player("Enfant", "user_1")
        game.add_player("Mentor", "user_2")
        
        enfant = game.players["user_1"]
        mentor = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.ENFANT_SAUVAGE)
        role.assign_to_player(enfant)
        assert role.can_act_at_night() == True
        
        result = role.perform_action(game, ActionType.CHOOSE_MENTOR, mentor)
        assert result["success"] == True
        assert enfant.mentor == mentor
        
        mentor_role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        mentor_role.assign_to_player(mentor)
        
        role.on_player_death(game, mentor)
        assert enfant.role.role_type == RoleType.LOUP_GAROU
    
    def test_idiot(self):
        """Test le rôle Idiot."""
        game = GameManager()
        game.add_player("Idiot", "user_1")
        
        idiot = game.players["user_1"]
        role = RoleFactory.create_role(RoleType.IDIOT)
        role.assign_to_player(idiot)
        
        saved = role.on_voted_out(game)
        assert saved == True
        assert idiot.can_vote == False
        assert idiot.has_been_pardoned == True
        
        saved = role.on_voted_out(game)
        assert saved == False
    
    def test_loup_voyant_no_shadow(self):
        """Test que LoupVoyant n'a pas de conflit attribut/méthode."""
        role = RoleFactory.create_role(RoleType.LOUP_VOYANT)
        assert role.can_act_at_night() == True
        # can_vote_with_wolves doit être callable et retourner False par défaut
        assert callable(role.can_vote_with_wolves)
        assert role.can_vote_with_wolves() == False


class TestSpecialRoles:
    """Tests pour les rôles spéciaux."""
    
    def test_dictateur(self):
        """Test le rôle Dictateur."""
        game = GameManager()
        game.add_player("Dictateur", "user_1")
        game.add_player("Loup", "user_2")
        game.add_player("Villageois", "user_3")
        
        dictateur = game.players["user_1"]
        loup = game.players["user_2"]
        
        role = RoleFactory.create_role(RoleType.DICTATEUR)
        role.assign_to_player(dictateur)
        
        loup_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        loup_role.assign_to_player(loup)
        
        # Le Dictateur ne peut agir que le jour
        game.phase = GamePhase.DAY
        result = role.perform_action(game, ActionType.DICTATOR_KILL, loup)
        assert result["success"] == True
        assert result["became_mayor"] == True
        assert dictateur.is_mayor == True
    
    def test_mercenaire(self):
        """Test le rôle Mercenaire."""
        game = GameManager()
        for i in range(4):
            game.add_player(f"Player{i}", f"user_{i}")
        
        mercenaire = game.players["user_0"]
        role = RoleFactory.create_role(RoleType.MERCENAIRE)
        role.assign_to_player(mercenaire)
        
        role.on_game_start(game)
        assert mercenaire.target is not None
        assert mercenaire.target != mercenaire
    
    def test_all_roles_have_name_and_description(self):
        """Test que tous les rôles ont name et description."""
        for role_type in RoleType:
            try:
                role = RoleFactory.create_role(role_type)
                assert role.name is not None
                assert len(role.name) > 0
                assert role.description is not None
                assert len(role.description) > 0
            except ValueError:
                pass  # Certains RoleType n'ont pas de factory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
