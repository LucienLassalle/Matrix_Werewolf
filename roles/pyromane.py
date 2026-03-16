"""Role Pyromane."""

from typing import TYPE_CHECKING, List

from models.role import Role
from models.enums import RoleType, Team, ActionType

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Pyromane(Role):
    """Pyromane - Marque des joueurs et peut les bruler une fois."""

    emoji = "🔥"

    def __init__(self):
        super().__init__(RoleType.PYROMANE, Team.NEUTRE)
        self.has_ignited = False
        self.soaked_tonight = 0
        self.ignited_tonight = False
        self._soaked_user_ids: set[str] = set()

    def get_description(self) -> str:
        return (
            "Pyromane - Chaque nuit, vous pouvez asperger jusqu'a deux personnes. "
            "Sinon, vous pouvez embraser toutes les personnes aspergees (une fois dans la partie). "
            "Vous gagnez seul si vous etes le dernier survivant."
        )

    def can_act_at_night(self) -> bool:
        return True

    def can_perform_action(self, action_type: ActionType) -> bool:
        if not self.player or not self.player.is_alive:
            return False

        if action_type == ActionType.PYROMANE_SOAK:
            return self.soaked_tonight < 2 and not self.ignited_tonight
        if action_type == ActionType.PYROMANE_IGNITE:
            return (not self.has_ignited
                    and not self.soaked_tonight
                    and bool(self._soaked_user_ids))

        return False

    def perform_action(self, game: 'GameManager', action_type: ActionType, target=None, **kwargs) -> dict:
        if action_type == ActionType.PYROMANE_SOAK:
            if self.ignited_tonight:
                return {"success": False, "message": "Vous avez deja embrase cette nuit"}
            if self.soaked_tonight >= 2:
                return {"success": False, "message": "Vous avez deja asperge deux personnes cette nuit"}
            if not target or not target.is_alive or target == self.player:
                return {"success": False, "message": "Cible invalide"}

            self._soaked_user_ids.add(target.user_id)
            self.soaked_tonight += 1
            return {
                "success": True,
                "message": f"Vous avez asperge {target.pseudo} cette nuit",
                "target": target,
            }

        if action_type == ActionType.PYROMANE_IGNITE:
            if self.has_ignited:
                return {"success": False, "message": "Vous avez deja embrase cette partie"}
            if self.soaked_tonight > 0:
                return {"success": False, "message": "Vous avez deja asperge cette nuit"}
            if not self._soaked_user_ids:
                return {"success": False, "message": "Aucune personne aspergee"}

            self.has_ignited = True
            self.ignited_tonight = True
            return {
                "success": True,
                "message": "Vous embrasez toutes les personnes aspergees",
            }

        return {"success": False, "message": "Action non disponible"}

    def on_night_start(self, game: 'GameManager'):
        self.soaked_tonight = 0
        self.ignited_tonight = False

    def get_state(self) -> dict:
        return {
            "has_ignited": self.has_ignited,
            "soaked_tonight": self.soaked_tonight,
            "ignited_tonight": self.ignited_tonight,
            "soaked_user_ids": list(self._soaked_user_ids),
        }

    def restore_state(self, data: dict, players: dict):
        self.has_ignited = data.get("has_ignited", False)
        self.soaked_tonight = data.get("soaked_tonight", 0)
        self.ignited_tonight = data.get("ignited_tonight", False)
        self._soaked_user_ids = set(data.get("soaked_user_ids", []))

    def get_soaked_players(self, players_by_id: dict) -> List:
        return [players_by_id[uid] for uid in self._soaked_user_ids if uid in players_by_id]
