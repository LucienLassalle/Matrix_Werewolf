"""Rôle Voyante."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Voyante(Role):
    """Voyante - Peut voir le rôle d'un joueur chaque nuit."""

    emoji = "🔮"
    is_info_role = True
    
    def __init__(self):
        super().__init__(RoleType.VOYANTE, Team.GENTIL)
        self.has_used_power_tonight = False
    
    def get_description(self) -> str:
        return "Voyante - Chaque nuit, vous pouvez découvrir le rôle d'un joueur."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.SEE_ROLE and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power_tonight)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.SEE_ROLE:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous voir vous-même"}
            
            self.has_used_power_tonight = True
            role_name = target.role.name if target.role else "Inconnu"
            return {
                "success": True, 
                "message": f"{target.pseudo} est **{role_name}**",
                "role": role_name
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        """Réinitialise le pouvoir au début de la nuit."""
        self.has_used_power_tonight = False
