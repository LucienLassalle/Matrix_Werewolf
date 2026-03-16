"""Role Geolier."""

from typing import TYPE_CHECKING

from models.role import Role
from models.enums import RoleType, Team, ActionType

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Geolier(Role):
    """Geolier - Interroge un prisonnier la nuit et peut l'executer une fois."""

    emoji = "🔒"
    is_info_role = True

    def __init__(self):
        super().__init__(RoleType.GEOLIER, Team.GENTIL)
        self.pending_prisoner_user_id: str | None = None
        self.prisoner_user_id: str | None = None
        self.has_executed = False

    def get_description(self) -> str:
        return (
            "Geolier - Pendant le jour, vous choisissez un prisonnier a interroger la nuit. "
            "Le prisonnier ne peut pas agir et est isole. Une fois dans la partie, "
            "vous pouvez decider de l'executer."
        )

    def can_act_at_night(self) -> bool:
        return True

    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False
        if action_type == ActionType.JAIL_SELECT:
            return True
        if action_type == ActionType.JAIL_EXECUTE:
            return not self.has_executed and self.prisoner_user_id is not None
        return False

    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.JAIL_SELECT:
            if not target or not target.is_alive or target == self.player:
                return {"success": False, "message": "Cible invalide"}

            self.pending_prisoner_user_id = target.user_id
            return {
                "success": True,
                "message": f"Vous interrogerez {target.pseudo} cette nuit",
                "target": target,
            }

        if action_type == ActionType.JAIL_EXECUTE:
            if self.has_executed:
                return {"success": False, "message": "Vous avez deja execute un prisonnier"}
            if not self.prisoner_user_id:
                return {"success": False, "message": "Aucun prisonnier a executer"}

            self.has_executed = True
            return {"success": True, "message": "Vous executez votre prisonnier"}

        return {"success": False, "message": "Action non disponible"}

    def on_night_start(self, game: 'GameManager'):
        if self.pending_prisoner_user_id:
            prisoner = game.get_player(self.pending_prisoner_user_id)
            if prisoner and prisoner.is_alive:
                self.prisoner_user_id = prisoner.user_id
            else:
                self.prisoner_user_id = None
            self.pending_prisoner_user_id = None
        else:
            self.prisoner_user_id = None

    def on_day_start(self, game: 'GameManager'):
        self.prisoner_user_id = None

    def get_state(self) -> dict:
        return {
            "pending_prisoner_user_id": self.pending_prisoner_user_id,
            "prisoner_user_id": self.prisoner_user_id,
            "has_executed": self.has_executed,
        }

    def restore_state(self, data: dict, players: dict):
        self.pending_prisoner_user_id = data.get("pending_prisoner_user_id")
        self.prisoner_user_id = data.get("prisoner_user_id")
        self.has_executed = data.get("has_executed", False)
