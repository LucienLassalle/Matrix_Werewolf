"""Rôle Petite Fille."""

from models.role import Role
from models.enums import RoleType, Team


class PetiteFille(Role):
    """Petite Fille - Observe partiellement les messages des loups."""
    
    def __init__(self):
        super().__init__(RoleType.PETITE_FILLE, Team.GENTIL)
    
    def get_description(self) -> str:
        return "Petite Fille - Vous pouvez observer partiellement les messages des loups-garous."
    
    def can_act_at_night(self) -> bool:
        return True  # Passif mais actif la nuit (espionnage)
    
    def can_see_wolf_messages(self) -> bool:
        """La petite fille peut voir les messages des loups."""
        return self.player and self.player.is_alive
