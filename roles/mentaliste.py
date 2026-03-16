"""Rôle Mentaliste."""

from models.role import Role
from models.enums import RoleType, Team
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager


class Mentaliste(Role):
    """Mentaliste - Sait si le vote est positif ou négatif."""

    emoji = "🧠"
    
    def __init__(self):
        super().__init__(RoleType.MENTALISTE, Team.GENTIL)
    
    def get_description(self) -> str:
        return "Mentaliste - Avant la fin du vote, vous savez si le vote est positif (élimine un loup) ou négatif (élimine un villageois)."
    
    def predict_vote_outcome(self, game: 'GameManager', most_voted_player) -> str:
        """Prédit le résultat du vote."""
        if not most_voted_player:
            return "neutre"
        
        if most_voted_player.get_team() == Team.MECHANT:
            return "positif"
        else:
            return "négatif"
