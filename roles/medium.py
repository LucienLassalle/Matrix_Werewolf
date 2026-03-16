"""Rôle Médium."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Medium(Role):
    """Médium - Parle avec les morts."""

    emoji = "👻"
    is_info_role = True
    
    def __init__(self):
        super().__init__(RoleType.MEDIUM, Team.GENTIL)
        self.has_used_power_tonight = False
    
    def get_description(self) -> str:
        return "Médium - Vous pouvez parler avec les morts. Ils ne peuvent répondre que par des émojis."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.SPEAK_WITH_DEAD and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power_tonight)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.SPEAK_WITH_DEAD:
            if not target or target.is_alive:
                return {"success": False, "message": "Cette personne n'est pas morte"}
            
            self.has_used_power_tonight = True
            return {
                "success": True,
                "message": f"Vous pouvez maintenant parler avec {target.pseudo}",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False
