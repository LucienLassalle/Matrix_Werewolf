"""Role Detective."""

from typing import TYPE_CHECKING

from models.role import Role
from models.enums import RoleType, Team, ActionType

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Detective(Role):
    """Detective - Compare l'equipe de deux joueurs la nuit."""

    emoji = "🕵️"
    is_info_role = True

    def __init__(self):
        super().__init__(RoleType.DETECTIVE, Team.GENTIL)
        self.has_used_power_tonight = False

    def get_description(self) -> str:
        return (
            "Detective - Chaque nuit, vous pouvez interroger deux joueurs. "
            "Le bot vous dit s'ils sont dans la meme equipe."
        )

    def can_act_at_night(self) -> bool:
        return True

    def can_perform_action(self, action_type: ActionType) -> bool:
        return (
            action_type == ActionType.DETECTIVE_CHECK
            and self.player
            and self.player.is_alive
            and not self.has_used_power_tonight
        )

    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type != ActionType.DETECTIVE_CHECK:
            return {"success": False, "message": "Action non disponible"}

        if self.has_used_power_tonight:
            return {"success": False, "message": "Vous avez deja utilise votre pouvoir cette nuit"}

        target1 = kwargs.get("target1")
        target2 = kwargs.get("target2")

        if not target1 or not target2:
            return {"success": False, "message": "Vous devez choisir deux joueurs"}
        if target1 == target2:
            return {"success": False, "message": "Les deux joueurs doivent etre differents"}
        if not target1.is_alive or not target2.is_alive:
            return {"success": False, "message": "Les deux joueurs doivent etre vivants"}
        if target1 == self.player or target2 == self.player:
            return {"success": False, "message": "Vous ne pouvez pas vous cibler"}

        self.has_used_power_tonight = True
        same_team = target1.get_team() == target2.get_team()
        verdict = "meme equipe" if same_team else "equipes differentes"
        return {
            "success": True,
            "message": f"{target1.pseudo} et {target2.pseudo} sont {verdict}.",
            "same_team": same_team,
        }

    def on_night_start(self, game: 'GameManager'):
        self.has_used_power_tonight = False

    def get_state(self) -> dict:
        return {"has_used_power_tonight": self.has_used_power_tonight}

    def restore_state(self, data: dict, players: dict):
        self.has_used_power_tonight = data.get("has_used_power_tonight", False)
