"""Rôle Garde."""

from models.role import Role
from models.enums import RoleType, Team, ActionType, GamePhase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Garde(Role):
    """Garde - Protège un joueur chaque nuit."""

    emoji = "🛡️"
    
    def __init__(self):
        super().__init__(RoleType.GARDE, Team.GENTIL)
        self.last_protected = None
        self.has_used_power_tonight = False
        self.preselected_target_id = None
    
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

            # Le Garde peut préparer/modifier sa cible en journée.
            # L'effet n'est activé qu'au début de la nuit.
            if game.phase in (GamePhase.DAY, GamePhase.VOTE):
                if self.last_protected == target:
                    return {"success": False, "message": "Vous ne pouvez pas protéger la même personne deux nuits de suite"}
                self.preselected_target_id = target.user_id
                return {
                    "success": True,
                    "message": f"Cible mise à jour: {target.pseudo} sera protégé.e cette nuit",
                    "target": target,
                }
            
            if self.has_used_power_tonight:
                return {"success": False, "message": "Vous avez déjà protégé quelqu'un cette nuit"}
            
            if self.last_protected == target:
                return {"success": False, "message": "Vous ne pouvez pas protéger la même personne deux nuits de suite"}
            
            target.is_protected = True
            self.last_protected = target
            self.has_used_power_tonight = True
            return {
                "success": True,
                "message": f"Vous protégez {target.pseudo} cette nuit",
                "target": target
            }
        
        return {"success": False, "message": "Action non disponible"}

    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False
        if not self.player or not self.player.is_alive or not self.preselected_target_id:
            return

        target = game.players.get(self.preselected_target_id)
        self.preselected_target_id = None
        if not target or not target.is_alive:
            return
        if self.last_protected == target:
            return

        target.is_protected = True
        self.last_protected = target
        self.has_used_power_tonight = True

    def get_state(self) -> dict:
        return {
            'last_protected_user_id': self.last_protected.user_id if self.last_protected else None,
            'preselected_target_id': self.preselected_target_id,
        }

    def restore_state(self, data: dict, players: dict):
        uid = data.get('last_protected_user_id')
        self.last_protected = players.get(uid) if uid else None
        self.preselected_target_id = data.get('preselected_target_id')
