"""Factory pour créer les rôles."""

from models.enums import RoleType
from models.role import Role
from roles.villageois import Villageois
from roles.loup_garou import LoupGarou
from roles.voyante import Voyante
from roles.chasseur import Chasseur
from roles.sorciere import Sorciere
from roles.cupidon import Cupidon
from roles.petite_fille import PetiteFille
from roles.voleur import Voleur
from roles.loup_voyant import LoupVoyant
from roles.loup_blanc import LoupBlanc
from roles.loup_noir import LoupNoir
from roles.loup_bavard import LoupBavard
from roles.montreur_ours import MontreurOurs
from roles.corbeau import Corbeau
from roles.idiot import Idiot
from roles.enfant_sauvage import EnfantSauvage
from roles.medium import Medium
from roles.garde import Garde
from roles.voyante_aura import VoyanteAura
from roles.mercenaire import Mercenaire
from roles.mentaliste import Mentaliste
from roles.dictateur import Dictateur
from roles.chasseur_de_tetes import ChasseurDeTetes
from roles.assassin import Assassin
from roles.pyromane import Pyromane
from roles.detective import Detective
from roles.geolier import Geolier


class RoleFactory:
    """Factory pour créer des instances de rôles."""
    
    _role_map = {
        RoleType.VILLAGEOIS: Villageois,
        RoleType.LOUP_GAROU: LoupGarou,
        RoleType.VOYANTE: Voyante,
        RoleType.CHASSEUR: Chasseur,
        RoleType.SORCIERE: Sorciere,
        RoleType.CUPIDON: Cupidon,
        RoleType.PETITE_FILLE: PetiteFille,
        RoleType.VOLEUR: Voleur,
        RoleType.LOUP_VOYANT: LoupVoyant,
        RoleType.LOUP_BLANC: LoupBlanc,
        RoleType.LOUP_NOIR: LoupNoir,
        RoleType.LOUP_BAVARD: LoupBavard,
        RoleType.MONTREUR_OURS: MontreurOurs,
        RoleType.CORBEAU: Corbeau,
        RoleType.IDIOT: Idiot,
        RoleType.ENFANT_SAUVAGE: EnfantSauvage,
        RoleType.MEDIUM: Medium,
        RoleType.GARDE: Garde,
        RoleType.VOYANTE_AURA: VoyanteAura,
        RoleType.MERCENAIRE: Mercenaire,
        RoleType.MENTALISTE: Mentaliste,
        RoleType.DICTATEUR: Dictateur,
        RoleType.CHASSEUR_DE_TETES: ChasseurDeTetes,
        RoleType.ASSASSIN: Assassin,
        RoleType.PYROMANE: Pyromane,
        RoleType.DETECTIVE: Detective,
        RoleType.GEOLIER: Geolier,
    }
    
    @classmethod
    def create_role(cls, role_type: RoleType) -> Role:
        """Crée une instance d'un rôle."""
        role_class = cls._role_map.get(role_type)
        if not role_class:
            raise ValueError(f"Rôle inconnu : {role_type}")
        return role_class()
    
    @classmethod
    def get_available_roles(cls) -> list[RoleType]:
        """Retourne la liste de tous les rôles disponibles."""
        return list(cls._role_map.keys())


def create_role(role_type: RoleType) -> Role:
    """Fonction de commodité pour créer un rôle."""
    return RoleFactory.create_role(role_type)
