"""Tests spécifiques pour le rôle Chasseur."""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager
from game.vote_manager import VoteManager


class TestChasseur:
    """Tests du mécanisme de tir du Chasseur."""
    
    def setup_method(self):
        self.game = GameManager()
        for i in range(6):
            self.game.add_player(f"Player{i}", f"user_{i}")
        
        self.chasseur = self.game.players["user_0"]
        self.target = self.game.players["user_1"]
        self.loup = self.game.players["user_2"]
        
        chasseur_role = RoleFactory.create_role(RoleType.CHASSEUR)
        chasseur_role.assign_to_player(self.chasseur)
        
        loup_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        loup_role.assign_to_player(self.loup)
        
        for i in range(3, 6):
            v = RoleFactory.create_role(RoleType.VILLAGEOIS)
            v.assign_to_player(self.game.players[f"user_{i}"])
        
        villageois_role = RoleFactory.create_role(RoleType.VILLAGEOIS)
        villageois_role.assign_to_player(self.target)
    
    def test_chasseur_shoot_on_death_day(self):
        """Chasseur peut tirer quand il meurt de jour."""
        self.chasseur.kill()
        self.chasseur.role.can_shoot_now = True
        
        result = self.chasseur.role.perform_action(
            self.game, ActionType.KILL, self.target
        )
        assert result["success"] == True
        assert self.target.is_alive == False
    
    def test_chasseur_shoot_wolf(self):
        """Chasseur peut tirer sur un loup."""
        self.chasseur.kill()
        self.chasseur.role.can_shoot_now = True
        
        result = self.chasseur.role.perform_action(
            self.game, ActionType.KILL, self.loup
        )
        assert result["success"] == True
        assert self.loup.is_alive == False
    
    def test_chasseur_cannot_shoot_alive(self):
        """Chasseur ne peut pas tirer s'il est vivant."""
        result = self.chasseur.role.perform_action(
            self.game, ActionType.KILL, self.target
        )
        assert result["success"] == False
    
    def test_chasseur_cannot_shoot_dead_target(self):
        """Chasseur ne peut pas tirer sur un joueur déjà mort."""
        self.chasseur.kill()
        self.chasseur.role.can_shoot_now = True
        self.target.kill()
        
        result = self.chasseur.role.perform_action(
            self.game, ActionType.KILL, self.target
        )
        assert result["success"] == False
    
    def test_chasseur_on_player_death_day(self):
        """on_player_death active le tir si tué de jour."""
        self.chasseur.role.on_player_death(
            self.game, self.chasseur, killed_during_day=True
        )
        assert self.chasseur.role.can_shoot_now == True
    
    def test_chasseur_on_player_death_night(self):
        """on_player_death active le tir si tué de nuit."""
        self.chasseur.role.on_player_death(
            self.game, self.chasseur, killed_during_day=False
        )
        assert self.chasseur.role.can_shoot_now == True
    
    def test_chasseur_team(self):
        """Chasseur est du côté des gentils."""
        assert self.chasseur.role.team == Team.GENTIL
    
    def test_chasseur_not_night_active(self):
        """Chasseur n'agit pas activement la nuit."""
        assert self.chasseur.role.can_act_at_night() == False
    
    def test_chasseur_on_other_death(self):
        """on_player_death ne déclenche rien si c'est un autre joueur qui meurt."""
        self.chasseur.role.on_player_death(
            self.game, self.target, killed_during_day=True
        )
        assert self.chasseur.role.can_shoot_now == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
