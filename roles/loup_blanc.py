"""Rôle Loup-Blanc."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class LoupBlanc(Role):
    """Loup-Blanc - Une nuit sur deux, peut tuer quelqu'un seul. Gagne seul."""
    
    def __init__(self):
        super().__init__(RoleType.LOUP_BLANC, Team.MECHANT)
        self.can_kill_tonight = False
        self.night_count = 0
        self.has_killed_tonight = False
    
    def get_description(self) -> str:
        return ("Loup Blanc - Vous votez avec les loups la nuit, mais une nuit sur deux "
                "vous pouvez tuer un autre joueur (y compris un loup). "
                "Vous gagnez SEUL en étant le dernier survivant, "
                "ou avec votre couple si vous êtes en couple. "
                "Vous PERDEZ si les loups ou le village gagnent.")
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False
        
        if action_type == ActionType.KILL:
            return self.can_kill_tonight and not self.has_killed_tonight
        elif action_type == ActionType.VOTE:
            return True
        
        return False
    
    def can_act_at_night(self) -> bool:
        return True
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.KILL:
            if not self.can_kill_tonight:
                return {"success": False, "message": "Vous ne pouvez pas tuer cette nuit"}
            
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous cibler vous-même"}
            
            self.has_killed_tonight = True
            # NE PAS tuer ici - l'action_manager gère la mort à la résolution
            return {
                "success": True,
                "message": f"Vous avez choisi de tuer {target.pseudo}",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        self.night_count += 1
        self.can_kill_tonight = (self.night_count % 2 == 0)
        self.has_killed_tonight = False
