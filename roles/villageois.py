"""Rôle Villageois."""

from models.role import Role
from models.enums import RoleType, Team


class Villageois(Role):
    """Villageois simple sans pouvoir spécial."""
    
    def __init__(self):
        super().__init__(RoleType.VILLAGEOIS, Team.GENTIL)
    
    def get_description(self) -> str:
        return "Villageois - Vous êtes un simple villageois. Votre seul pouvoir est votre vote."
