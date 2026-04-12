"""Rôle Corbeau."""

import os
from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Corbeau(Role):
    """Corbeau - Rajoute 2 votes sur quelqu'un chaque nuit."""

    emoji = "🐦"
    
    def __init__(self):
        super().__init__(RoleType.CORBEAU, Team.GENTIL)
        self.has_used_power_tonight = False
        self.current_target_id: Optional[str] = None
    
    def get_description(self) -> str:
        return "Corbeau - Chaque nuit, vous pouvez ajouter 2 votes sur une personne de votre choix pour le vote du lendemain."
    
    def can_act_at_night(self) -> bool:
        return True
    
    def can_perform_action(self, action_type: ActionType) -> bool:
        return (action_type == ActionType.ADD_VOTES and
            self.player and
            self.player.is_alive)
    
    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.ADD_VOTES:
            if not target or not target.is_alive:
                return {"success": False, "message": "Cible invalide"}
            
            if target == self.player:
                return {"success": False, "message": "Vous ne pouvez pas vous maudire vous-même"}

            if self.current_target_id and self.current_target_id != target.user_id:
                previous = game.players.get(self.current_target_id)
                if previous:
                    previous.votes_against = max(0, previous.votes_against - 2)

            if self.current_target_id != target.user_id:
                target.votes_against += 2
                self.current_target_id = target.user_id
                self.has_used_power_tonight = True
                message = f"Vous avez ajouté 2 votes sur {target.pseudo}"
            else:
                message = f"Vous avez deja maudit {target.pseudo}"

            return {
                "success": True,
                "message": message,
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}

    def on_player_death(self, game: 'GameManager', dead_player, **kwargs):
        """Retire l'effet du Corbeau mort si l'option est désactivée."""
        if dead_player != self.player:
            return

        keep_after_death = os.getenv('CORBEAU_EFFECT_ACTIVE_AFTER_DEATH', 'true').strip().lower() == 'true'
        if keep_after_death:
            return

        if self.current_target_id:
            target = game.players.get(self.current_target_id)
            if target:
                target.votes_against = max(0, target.votes_against - 2)
        self.current_target_id = None
        self.has_used_power_tonight = False
    
    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False
        self.current_target_id = None

    def get_state(self) -> dict:
        return {
            'has_used_power_tonight': self.has_used_power_tonight,
            'current_target_id': self.current_target_id,
        }

    def restore_state(self, data: dict, players: dict):
        self.has_used_power_tonight = data.get('has_used_power_tonight', False)
        self.current_target_id = data.get('current_target_id')
