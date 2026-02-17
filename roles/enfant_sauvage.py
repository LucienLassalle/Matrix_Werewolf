"""Rôle Enfant Sauvage."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager
    from models.player import Player


class EnfantSauvage(Role):
    """Enfant Sauvage - Choisit un mentor, devient loup si le mentor meurt."""
    
    def __init__(self):
        super().__init__(RoleType.ENFANT_SAUVAGE, Team.GENTIL)
        self.has_chosen_mentor = False
    
    def get_description(self) -> str:
        return "Enfant Sauvage - Vous choisissez un mentor au début. Si votre mentor meurt, vous devenez un loup-garou."
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.CHOOSE_MENTOR and 
                self.player and 
                self.player.is_alive and 
                not self.has_chosen_mentor)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.CHOOSE_MENTOR:
            if not target or not target.is_alive or target == self.player:
                return {"success": False, "message": "Cible invalide"}
            
            self.player.mentor = target
            self.has_chosen_mentor = True
            return {
                "success": True,
                "message": f"Vous avez choisi {target.pseudo} comme mentor",
                "mentor": target
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def can_act_at_night(self) -> bool:
        return not self.has_chosen_mentor
    
    def on_player_death(self, game, dead_player, **kwargs):
        """Devient loup si le mentor meurt."""
        if self.player and dead_player == self.player.mentor and self.player.is_alive:
            from roles.loup_garou import LoupGarou
            new_role = LoupGarou()
            new_role.assign_to_player(self.player)

    def get_state(self) -> dict:
        return {
            'has_chosen_mentor': self.has_chosen_mentor,
            'mentor_user_id': self.player.mentor.user_id if self.player and self.player.mentor else None,
        }

    def restore_state(self, data: dict, players: dict):
        self.has_chosen_mentor = data.get('has_chosen_mentor', False)
        mentor_uid = data.get('mentor_user_id')
        if mentor_uid and self.player:
            self.player.mentor = players.get(mentor_uid)
