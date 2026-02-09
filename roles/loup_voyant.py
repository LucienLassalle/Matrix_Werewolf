"""Rôle Loup-Voyant."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class LoupVoyant(Role):
    """Loup-Voyant - Peut voir les rôles mais ne peut pas voter (sauf conditions)."""
    
    def __init__(self):
        super().__init__(RoleType.LOUP_VOYANT, Team.MECHANT)
        self._can_vote_with_pack = False
        self.has_used_power_tonight = False
    
    def get_description(self) -> str:
        return ("Loup-Voyant - Vous pouvez voir les rôles chaque nuit, mais vous ne pouvez pas voter. "
                "Si vous êtes le dernier loup, vous devenez un loup normal.")
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_vote_with_wolves(self) -> bool:
        return self._can_vote_with_pack
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False
        
        if action_type == ActionType.SEE_ROLE:
            # Ne peut plus voir après avoir rejoint la meute
            return not self.has_used_power_tonight and not self._can_vote_with_pack
        elif action_type == ActionType.VOTE:
            return self._can_vote_with_pack
        elif action_type == ActionType.BECOME_WEREWOLF:
            return not self._can_vote_with_pack
        
        return False
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.SEE_ROLE:
            if not target or not target.is_alive or target == self.player:
                return {"success": False, "message": "Cible invalide"}
            
            self.has_used_power_tonight = True
            role_name = target.role.role_type.value if target.role else "Inconnu"
            return {
                "success": True,
                "message": f"{target.pseudo} est {role_name}",
                "role": role_name
            }
        
        elif action_type == ActionType.BECOME_WEREWOLF:
            self._can_vote_with_pack = True
            return {
                "success": True,
                "message": "Vous avez abandonné votre pouvoir de voyance. Vous pouvez maintenant voter avec les loups."
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False
        
        # Vérifier si c'est le dernier loup
        living_wolves = game.get_living_wolves()
        if len(living_wolves) == 1 and self.player in living_wolves:
            self._can_vote_with_pack = True
