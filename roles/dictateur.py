"""Rôle Dictateur."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Dictateur(Role):
    """Dictateur - Peut prendre le pouvoir et forcer un vote."""
    
    def __init__(self):
        super().__init__(RoleType.DICTATEUR, Team.GENTIL)
        self.has_used_power = False
    
    def get_description(self) -> str:
        return ("Dictateur - Vous pouvez prendre le pouvoir et décider d'éliminer quelqu'un. "
                "Si vous tuez un loup, vous devenez maire. Sinon, vous mourrez.")
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.DICTATOR_KILL and 
                self.player and 
                self.player.is_alive and 
                not self.has_used_power)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.DICTATOR_KILL:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            self.has_used_power = True
            
            if target.get_team() == Team.MECHANT:
                # Le dictateur tue un loup, il devient maire
                dead = game.kill_player(target, killed_during_day=True)
                self.player.is_mayor = True
                return {
                    "success": True,
                    "message": f"Vous avez éliminé {target.pseudo}, un loup ! Vous êtes maintenant maire.",
                    "became_mayor": True,
                    "target": target,
                    "deaths": dead
                }
            else:
                # Le dictateur tue un innocent, il meurt aussi
                dead_target = game.kill_player(target, killed_during_day=True)
                dead_self = game.kill_player(self.player, killed_during_day=True)
                return {
                    "success": True,
                    "message": f"Vous avez éliminé {target.pseudo}, qui n'était pas un loup. Vous mourrez.",
                    "became_mayor": False,
                    "target": target,
                    "deaths": dead_target + dead_self
                }
        
        return {"success": False, "message": "Action non disponible"}
