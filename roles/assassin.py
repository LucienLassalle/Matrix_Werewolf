"""Role Assassin."""

from typing import TYPE_CHECKING

from models.role import Role
from models.enums import RoleType, Team, ActionType

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Assassin(Role):
    """Assassin - Tueur neutre qui elimine une cible chaque nuit."""

    emoji = "🗡️"

    def __init__(self):
        super().__init__(RoleType.ASSASSIN, Team.NEUTRE)
        self.has_killed_tonight = False

    def get_description(self) -> str:
        return (
            "Assassin - Chaque nuit, vous pouvez eliminer une personne. "
            "Vous gagnez seul si vous etes le dernier survivant."
        )

    def can_act_at_night(self) -> bool:
        return True

    def can_perform_action(self, action_type: ActionType) -> bool:
        return (
            action_type == ActionType.ASSASSIN_KILL
            and self.player
            and self.player.is_alive
            and not self.has_killed_tonight
        )

    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type != ActionType.ASSASSIN_KILL:
            return {"success": False, "message": "Action non disponible"}

        if self.has_killed_tonight:
            return {"success": False, "message": "Vous avez deja tue cette nuit"}

        if not target or not target.is_alive or target == self.player:
            return {"success": False, "message": "Cible invalide"}

        self.has_killed_tonight = True
        return {
            "success": True,
            "message": f"Vous avez choisi d'eliminer {target.pseudo} cette nuit",
            "target": target,
        }

    def on_night_start(self, game: 'GameManager'):
        self.has_killed_tonight = False

    def get_state(self) -> dict:
        return {"has_killed_tonight": self.has_killed_tonight}

    def restore_state(self, data: dict, players: dict):
        self.has_killed_tonight = data.get("has_killed_tonight", False)
