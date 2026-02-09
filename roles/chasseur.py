"""Rôle Chasseur."""

from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager
    from models.player import Player


class Chasseur(Role):
    """Chasseur - Peut tuer quelqu'un quand il meurt."""
    
    def __init__(self):
        super().__init__(RoleType.CHASSEUR, Team.GENTIL)
        self.has_shot = False
        self.can_shoot_now = False
        self.killed_during_day = False
    
    def get_description(self) -> str:
        return ("Chasseur - Quand vous mourrez, vous pouvez tuer quelqu'un de votre choix. "
                "Tué la nuit → tirez le jour. Tué le jour → tirez la nuit.")
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.KILL and 
                self.player and 
                not self.player.is_alive and 
                self.can_shoot_now and
                not self.has_shot)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.KILL:
            if self.has_shot:
                return {"success": False, "message": "Vous avez déjà tiré"}
            
            if not self.can_shoot_now:
                return {"success": False, "message": "Ce n'est pas encore le moment de tirer"}
            
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            self.has_shot = True
            
            # IMPORTANT: Annuler tous les votes/actions de la cible
            game.cancel_player_actions(target.user_id)
            
            # Tuer via le game manager (mute, retrait salon loups, notifications, amoureux)
            dead_players = game.kill_player(target, killed_during_day=False)
            
            return {
                "success": True, 
                "message": f"💥 Vous avez tué {target.pseudo} ! Leurs votes et actions sont annulés.",
                "target_id": target.user_id,
                "deaths": dead_players
            }
        
        return {"success": False, "message": "Action non disponible"}
    
    def can_act_at_night(self) -> bool:
        return False  # Passif, le tir est déclenché par la mort
    
    def on_player_death(self, game, dead_player, **kwargs):
        """Le chasseur peut tirer après sa mort.
        
        kwargs:
            killed_during_day: True si tué le jour (vote), False si tué la nuit
        """
        killed_during_day = kwargs.get('killed_during_day', False)
        if dead_player == self.player and not self.has_shot:
            self.killed_during_day = killed_during_day
            self.can_shoot_now = True
