"""Rôle Corbeau."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Corbeau(Role):
    """Corbeau - Rajoute 2 votes sur quelqu'un chaque nuit."""

    emoji = "🐦"
    
    def __init__(self):
        super().__init__(RoleType.CORBEAU, Team.GENTIL)
        self.has_used_power_tonight = False
    
    def get_description(self) -> str:
        return "Corbeau - Chaque nuit, vous pouvez ajouter 2 votes sur une personne de votre choix pour le vote du lendemain."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.ADD_VOTES and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power_tonight)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.ADD_VOTES:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous maudire vous-même"}
            
            target.votes_against += 2
            self.has_used_power_tonight = True
            return {
                "success": True,
                "message": f"Vous avez ajouté 2 votes sur {target.pseudo}",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False

    def get_state(self) -> dict:
        return {'has_used_power_tonight': self.has_used_power_tonight}

    def restore_state(self, data: dict, players: dict):
        self.has_used_power_tonight = data.get('has_used_power_tonight', False)
