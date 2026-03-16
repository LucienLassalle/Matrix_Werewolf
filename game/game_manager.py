"""Gestionnaire principal du jeu.

Classe centrale qui orchestre une partie de Loup-Garou.
La logique est répartie via mixins :
- game_phases.py   : transitions de phase (nuit → jour → vote)
- game_lifecycle.py : conditions de victoire, kill chain, fin de partie
"""

from typing import Dict, List, Optional
import math
import random
import uuid
from datetime import datetime
import logging
from collections import Counter

from models.player import Player
from models.enums import GamePhase, Team, RoleType
from models.enums import Phase  # Alias pour compatibilité
from models.role import Role
from roles import RoleFactory
from game.vote_manager import VoteManager
from game.action_manager import ActionManager
from game.game_phases import PhaseManagerMixin
from game.game_lifecycle import GameLifecycleMixin
from game.game_persistence import GamePersistenceMixin
from database.game_db import GameDatabase

logger = logging.getLogger(__name__)


class GameManager(PhaseManagerMixin, GameLifecycleMixin, GamePersistenceMixin):
    """Gestionnaire principal du jeu Loup-Garou."""

    # Rôles obligatoires pour toute partie
    MANDATORY_ROLES = [
        RoleType.SORCIERE,
        RoleType.VOYANTE,
        RoleType.CHASSEUR,
    ]

    def __init__(self, db_path: str = "werewolf_game.db"):
        self.players: Dict[str, Player] = {}   # user_id → Player
        self._player_order: List[str] = []     # Ordre d'assise (pour voisins)
        self.phase = GamePhase.SETUP
        self.day_count = 0
        self.night_count = 0
        self.vote_manager = VoteManager()
        self.action_manager = ActionManager()
        self.available_roles: List[Role] = []
        self.extra_roles: List[Role] = []  # Cartes supplémentaires pour le Voleur
        self.game_log: List[str] = []

        # Base de données pour persistance
        self.db = GameDatabase(db_path)
        self.game_id = str(uuid.uuid4())
        self.start_time: Optional[datetime] = None

        # Gestion des permissions Matrix
        self.on_remove_wolf_from_room: Optional[callable] = None
        self.on_mute_player: Optional[callable] = None

        # Élection du maire : se fait une seule fois après la première nuit
        self.mayor_election_done: bool = False

        # Succession de maire
        self._pending_mayor_succession: Optional[Player] = None

        # Morts différées (initialisé ici pour éviter AttributeError)
        self._pending_kills: List[Player] = []

        # Geolier (prison)
        self._jailed_user_id: Optional[str] = None

        # Configuration Cupidon
        self.cupidon_wins_with_couple = True

        # Rôles désactivés (set de RoleType)
        self.disabled_roles: set = set()

    def reset(self):
        """Réinitialise le GameManager pour une nouvelle partie.

        Conserve la connexion BDD, les callbacks et la configuration.
        """
        self.players.clear()
        self._player_order.clear()
        self.phase = GamePhase.SETUP
        self.day_count = 0
        self.night_count = 0
        self.vote_manager = VoteManager()
        self.action_manager = ActionManager()
        self.available_roles.clear()
        self.extra_roles.clear()
        self.game_log.clear()
        self.game_id = str(uuid.uuid4())
        self.start_time = None
        self._pending_mayor_succession = None
        self.mayor_election_done = False
        self._jailed_user_id = None
        logger.info("GameManager réinitialisé pour une nouvelle partie")

    # ==================== Gestion des joueurs ====================

    def add_player(self, pseudo: str, user_id: str) -> dict:
        """Ajoute un joueur à la partie."""
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}

        if user_id in self.players:
            return {"success": False, "message": "Ce joueur est déjà dans la partie"}

        player = Player(pseudo, user_id)
        self.players[user_id] = player
        self._player_order.append(user_id)
        self.vote_manager.register_player(player)
        self.log(f"{pseudo} a rejoint la partie")

        return {"success": True, "message": f"{pseudo} a rejoint la partie", "player": player}

    def get_player(self, user_id: str) -> Optional[Player]:
        """Trouve un joueur par son user_id."""
        return self.players.get(user_id)

    def get_player_by_user_id(self, user_id: str) -> Optional[Player]:
        """Trouve un joueur par son user_id (alias de get_player)."""
        return self.get_player(user_id)

    def get_player_by_pseudo(self, pseudo: str) -> Optional[Player]:
        """Trouve un joueur par son pseudo ou son identifiant Matrix.

        Accepte :
        - Pseudo direct : "Alice"
        - Matrix ID partiel : "alice:matrix.org" (sans @)
        - Matrix ID complet : "@alice:matrix.org"
        """
        if not pseudo:
            return None

        search = pseudo.strip()

        # 1. Correspondance exacte par pseudo
        for player in self.players.values():
            if player.pseudo.lower() == search.lower():
                return player

        # 2. Correspondance par user_id complet (avec ou sans @)
        search_id = search if search.startswith('@') else f'@{search}'
        for player in self.players.values():
            if player.user_id.lower() == search_id.lower():
                return player

        # 3. Correspondance par la partie username d'un Matrix ID
        if ':' in search:
            username = search.split(':')[0].lstrip('@')
            for player in self.players.values():
                if player.pseudo.lower() == username.lower():
                    return player

        # 4. Correspondance par display_name
        for player in self.players.values():
            if player.display_name.lower() == search.lower():
                return player

        return None

    def get_living_players(self) -> List[Player]:
        """Retourne la liste des joueurs vivants."""
        return [p for p in self.players.values() if p.is_alive]

    def get_jailer_and_prisoner(self) -> tuple[Optional[Player], Optional[Player]]:
        """Retourne le geolier et son prisonnier actuel, si present."""
        jailer = None
        prisoner = None
        for player in self.players.values():
            if player.role and player.role.role_type == RoleType.GEOLIER:
                jailer = player
                break

        if not jailer or not jailer.role or not jailer.is_alive:
            return None, None

        prisoner_uid = getattr(jailer.role, 'prisoner_user_id', None)
        if prisoner_uid and prisoner_uid in self.players:
            prisoner = self.players[prisoner_uid]

        if prisoner and not prisoner.is_alive:
            prisoner = None

        return jailer, prisoner

    def is_player_jailed(self, user_id: str) -> bool:
        """Indique si un joueur est actuellement emprisonne."""
        return self._jailed_user_id == user_id

    def set_jailed_player(self, prisoner: Optional[Player]):
        """Met a jour l'etat d'emprisonnement pour la nuit."""
        for player in self.players.values():
            player.is_jailed = False

        if prisoner and prisoner.is_alive:
            prisoner.is_jailed = True
            self._jailed_user_id = prisoner.user_id
        else:
            self._jailed_user_id = None

    def get_living_wolves(self) -> List[Player]:
        """Retourne la liste des loups vivants."""
        return [p for p in self.get_living_players() if p.get_team() == Team.MECHANT]

    def get_neighbors(self, player: Player) -> List[Player]:
        """Retourne les voisins vivants d'un joueur (pour le montreur d'ours).

        Les joueurs morts sont ignorés : on cherche le prochain joueur
        vivant dans chaque direction (comme si les morts étaient retirés du cercle).
        """
        if player.user_id not in self._player_order:
            return []

        index = self._player_order.index(player.user_id)
        n = len(self._player_order)
        neighbors = []

        # Voisin de gauche (sauter les morts)
        for offset in range(1, n):
            left_uid = self._player_order[(index - offset) % n]
            left_player = self.players.get(left_uid)
            if left_player and left_player.is_alive and left_player != player:
                neighbors.append(left_player)
                break

        # Voisin de droite (sauter les morts)
        for offset in range(1, n):
            right_uid = self._player_order[(index + offset) % n]
            right_player = self.players.get(right_uid)
            if right_player and right_player.is_alive and right_player != player:
                neighbors.append(right_player)
                break

        return neighbors

    def get_love_group(self, player: Player, alive_only: bool = False) -> set[Player]:
        """Retourne le groupe d'amoureux connecte a un joueur."""
        if not player:
            return set()

        visited: set[Player] = set()
        stack = [player]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            if alive_only and not current.is_alive:
                continue
            visited.add(current)
            for lover in current.get_lovers():
                if lover not in visited:
                    stack.append(lover)
        return visited

    def get_love_groups(self, alive_only: bool = False) -> list[set[Player]]:
        """Retourne la liste des groupes d'amoureux (taille >= 2)."""
        groups: list[set[Player]] = []
        visited: set[Player] = set()
        for player in self.players.values():
            if player in visited:
                continue
            if alive_only and not player.is_alive:
                continue
            if not player.get_lovers():
                continue
            group = self.get_love_group(player, alive_only=alive_only)
            if len(group) >= 2:
                groups.append(group)
                visited.update(group)
        return groups

    def get_available_roles(self) -> List[Role]:
        """Retourne les rôles non assignés."""
        assigned_roles = [p.role for p in self.players.values() if p.role]
        return [r for r in self.available_roles if r not in assigned_roles]

    # ==================== Configuration des rôles ====================

    def set_roles(self, role_config: Dict[RoleType, int]):
        """Configure les rôles pour la partie."""
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}

        # Vérifier que les rôles ne sont pas désactivés
        for role_type in role_config:
            if role_type in self.disabled_roles:
                from models.role import ROLE_DISPLAY_NAMES
                name = ROLE_DISPLAY_NAMES.get(role_type, role_type.value)
                return {"success": False, "message": f"Le rôle {name} est désactivé"}

        if (RoleType.ASSASSIN in role_config or RoleType.PYROMANE in role_config):
            if len(self.players) < 8:
                return {
                    "success": False,
                    "message": "Assassin et Pyromane ne sont disponibles qu'a partir de 8 joueurs",
                }

        roles = []
        for role_type, count in role_config.items():
            for _ in range(count):
                roles.append(RoleFactory.create_role(role_type))

        if RoleType.ASSASSIN in role_config or RoleType.PYROMANE in role_config:
            total_players = max(len(roles), len(self.players))
            evilish_count = sum(
                1 for r in roles if r.team in (Team.MECHANT, Team.NEUTRE)
            )
            ratio = evilish_count / total_players if total_players else 0
            if ratio < 0.20:
                return {
                    "success": False,
                    "message": "Le ratio neutre + mechant doit etre au moins 20%",
                }

        if len(roles) < len(self.players):
            while len(roles) < len(self.players):
                roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))

        validation = self._validate_mandatory_roles(roles)
        if not validation["valid"]:
            return {"success": False, "message": " ; ".join(validation["errors"])}

        for mandatory_rt in self.MANDATORY_ROLES:
            count = sum(1 for r in roles if r.role_type == mandatory_rt)
            if count > 1:
                return {"success": False, "message": f"Maximum 1 {mandatory_rt.value} autorisé (trouvé: {count})"}


        self.available_roles = roles
        return {"success": True, "message": f"{len(roles)} rôles configurés"}

    def set_phase(self, phase: GamePhase):
        """Change la phase du jeu."""
        self.phase = phase
        logger.info(f"Phase changée: {phase.value}")

    def _validate_mandatory_roles(self, roles: list) -> dict:
        """Vérifie que les rôles obligatoires sont présents (sauf s'ils sont désactivés)."""
        errors = []
        role_types = [r.role_type for r in roles]


        wolf_types = {
            RoleType.LOUP_GAROU, RoleType.LOUP_BLANC,
            RoleType.LOUP_NOIR, RoleType.LOUP_BAVARD, RoleType.LOUP_VOYANT,
        }
        wolf_count = sum(1 for rt in role_types if rt in wolf_types)
        if wolf_count == 0:
            errors.append("Il faut au moins un rôle méchant (Loup-Garou) dans la partie")
        else:
            min_wolves = self._min_wolf_count(len(roles))
            if wolf_count < min_wolves:
                errors.append(
                    f"Il faut au moins {min_wolves} rôle(s) méchant(s) (25% minimum)"
                )

        for mandatory in self.MANDATORY_ROLES:
            if mandatory in self.disabled_roles:
                continue
            if mandatory not in role_types:
                errors.append(f"Le rôle {mandatory.value} est obligatoire")

        return {"valid": len(errors) == 0, "errors": errors}

    def _min_wolf_count(self, total_players: int) -> int:
        """Retourne le nombre minimal de loups requis pour une partie."""
        if total_players <= 5:
            return 1
        return max(1, int(math.ceil(total_players * 0.25)))

    def _max_info_count(self, total_players: int) -> int:
        """Retourne le nombre maximal de roles a information (30% max)."""
        return max(1, int(math.floor(total_players * 0.30)))

    def _role_types_by(self, predicate) -> list[RoleType]:
        """Retourne les RoleType filtrés par un prédicat sur les instances de rôle."""
        results: list[RoleType] = []
        for rt in RoleFactory.get_available_roles():
            if rt in self.disabled_roles:
                continue
            role = RoleFactory.create_role(rt)
            if predicate(role):
                results.append(rt)
        return results

    def _auto_configure_roles(self):
        """Configure automatiquement les rôles basé sur le nombre de joueurs.

        Principe :
        - ~20-25% de méchants
        - Rôles obligatoires : Sorcière, Voyante, Chasseur
        - Rôles à pouvoir (Garde, Médium) : uniques sous 10 joueurs, doublables au-delà
        """
        n = len(self.players)

        if n == 4:
            roles = [RoleFactory.create_role(RoleType.LOUP_GAROU)]
            for rt in [RoleType.CHASSEUR, RoleType.SORCIERE, RoleType.VOYANTE]:
                if rt not in self.disabled_roles:
                    roles.append(RoleFactory.create_role(rt))
            while len(roles) < n:
                roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))
            self.available_roles = roles
            return

        if n == 5:
            roles = [RoleFactory.create_role(RoleType.LOUP_GAROU)]
            for rt in [RoleType.CHASSEUR, RoleType.SORCIERE, RoleType.VOYANTE]:
                if rt not in self.disabled_roles:
                    roles.append(RoleFactory.create_role(rt))

            non_info_candidates = self._role_types_by(
                lambda r: (
                    r.team == Team.GENTIL
                    and not r.is_info_role
                    and r.role_type not in self.MANDATORY_ROLES
                    and r.role_type != RoleType.VILLAGEOIS
                )
            )
            if non_info_candidates:
                roles.append(RoleFactory.create_role(random.choice(non_info_candidates)))

            while len(roles) < n:
                roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))
            self.available_roles = roles
            return

        evil_count = self._min_wolf_count(n)

        neutral_pool = self._role_types_by(
            lambda r: r.team == Team.NEUTRE
        )

        neutral_count = 0
        if n >= 8 and neutral_pool and random.random() < 0.35:
            neutral_count = 1

        good_count = n - (evil_count + neutral_count)
        mandatory_good = [rt for rt in self.MANDATORY_ROLES if rt not in self.disabled_roles]
        if good_count < len(mandatory_good):
            neutral_count = 0
            good_count = n - evil_count

        # ── Attribution des rôles méchants ──
        evil_roles: list = []
        for _ in range(evil_count):
            roll = random.random()
            if roll < 0.01 and RoleType.LOUP_NOIR not in self.disabled_roles and not any(r.role_type == RoleType.LOUP_NOIR for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_NOIR))
            elif roll < 0.03 and RoleType.LOUP_BLANC not in self.disabled_roles and not any(r.role_type == RoleType.LOUP_BLANC for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_BLANC))
            elif roll < 0.05 and RoleType.LOUP_BAVARD not in self.disabled_roles and not any(r.role_type == RoleType.LOUP_BAVARD for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_BAVARD))
            elif roll < 0.10 and RoleType.LOUP_VOYANT not in self.disabled_roles and not any(r.role_type == RoleType.LOUP_VOYANT for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_VOYANT))
            else:
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_GAROU))

        # ── Attribution des rôles neutres ──
        neutral_roles: list = []
        if neutral_count > 0 and neutral_pool:
            random.shuffle(neutral_pool)
            neutral_roles = [RoleFactory.create_role(neutral_pool[0])]

        # ── Attribution des rôles gentils ──
        good_roles: list = [RoleFactory.create_role(rt) for rt in mandatory_good]
        good_roles = good_roles[:good_count]

        info_count = sum(1 for r in good_roles if r.is_info_role)
        target_info = max(2, round(n * 0.25))
        target_info = min(target_info, self._max_info_count(n))
        target_info = max(target_info, info_count)
        target_info = min(target_info, good_count)

        info_pool = self._role_types_by(
            lambda r: (
                r.team == Team.GENTIL
                and r.is_info_role
                and r.role_type not in self.MANDATORY_ROLES
            )
        )
        if evil_count < 2:
            info_pool = [rt for rt in info_pool if rt != RoleType.PETITE_FILLE]

        random.shuffle(info_pool)
        cupidon_added = any(r.role_type == RoleType.CUPIDON for r in good_roles)
        while len(good_roles) < good_count and info_count < target_info and info_pool:
            rt = info_pool.pop()
            if rt == RoleType.CUPIDON and cupidon_added:
                continue
            good_roles.append(RoleFactory.create_role(rt))
            if rt == RoleType.CUPIDON:
                cupidon_added = True
            info_count += 1

        non_info_pool = self._role_types_by(
            lambda r: (
                r.team == Team.GENTIL
                and not r.is_info_role
                and r.role_type not in self.MANDATORY_ROLES
                and r.role_type != RoleType.VILLAGEOIS
            )
        )
        random.shuffle(non_info_pool)

        while len(good_roles) < good_count and non_info_pool:
            rt = non_info_pool.pop()
            if rt == RoleType.CUPIDON and cupidon_added:
                continue
            good_roles.append(RoleFactory.create_role(rt))
            if rt == RoleType.CUPIDON:
                cupidon_added = True

        while len(good_roles) < good_count:
            good_roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))

        self.available_roles = evil_roles + neutral_roles + good_roles

    # ==================== Résumé des rôles ====================

    def get_roles_summary(self) -> dict:
        """Retourne un résumé des rôles en jeu (pour l'annonce)."""
        role_counts = Counter()
        for player in self.players.values():
            if player.role:
                role_counts[player.role.role_type] += 1

        summary = {}
        for rt, count in role_counts.items():
            role = RoleFactory.create_role(rt)
            summary[rt] = {
                'count': count,
                'name': role.name,
                'description': role.description,
                'team': role.team,
                'emoji': role.emoji,
            }
        return summary

    # ==================== Utilitaires ====================

    def log(self, message: str):
        """Ajoute un message au log de la partie."""
        self.game_log.append(message)

