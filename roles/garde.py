"""Rôle Garde."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Garde(Role):
    """Garde - Protège un joueur chaque nuit."""
    
    def __init__(self):
        super().__init__(RoleType.GARDE, Team.GENTIL)
        self.last_protected = None
    
    def get_description(self) -> str:
        return "Garde - Chaque nuit, vous protégez un joueur des attaques de loups. Vous ne pouvez pas protéger la même personne deux nuits de suite."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return action_type == ActionType.PROTECT and self.player and self.player.is_alive
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.PROTECT:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if self.last_protected == target:
                return {"success": False, "message": "Vous ne pouvez pas protéger la même personne deux nuits de suite"}
            
            target.is_protected = True
            self.last_protected = target
            return {
                "success": True,
                "message": f"Vous protégez {target.pseudo} cette nuit",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}
