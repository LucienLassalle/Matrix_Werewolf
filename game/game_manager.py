"""Gestionnaire principal du jeu.

Classe centrale qui orchestre une partie de Loup-Garou.
La logique est répartie via mixins :
- game_phases.py   : transitions de phase (nuit → jour → vote)
- game_lifecycle.py : conditions de victoire, kill chain, fin de partie
"""

from typing import Dict, List, Optional
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
from database.game_db import GameDatabase

logger = logging.getLogger(__name__)


class GameManager(PhaseManagerMixin, GameLifecycleMixin):
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

        # Configuration Cupidon
        self.cupidon_wins_with_couple = True

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

    def get_available_roles(self) -> List[Role]:
        """Retourne les rôles non assignés."""
        assigned_roles = [p.role for p in self.players.values() if p.role]
        return [r for r in self.available_roles if r not in assigned_roles]

    # ==================== Configuration des rôles ====================

    def set_roles(self, role_config: Dict[RoleType, int]):
        """Configure les rôles pour la partie."""
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}

        roles = []
        for role_type, count in role_config.items():
            for _ in range(count):
                roles.append(RoleFactory.create_role(role_type))

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
        """Vérifie que les rôles obligatoires sont présents."""
        errors = []
        role_types = [r.role_type for r in roles]

        wolf_types = {
            RoleType.LOUP_GAROU, RoleType.LOUP_BLANC,
            RoleType.LOUP_NOIR, RoleType.LOUP_BAVARD, RoleType.LOUP_VOYANT,
        }
        if not any(rt in wolf_types for rt in role_types):
            errors.append("Il faut au moins un rôle méchant (Loup-Garou) dans la partie")

        for mandatory in self.MANDATORY_ROLES:
            if mandatory not in role_types:
                errors.append(f"Le rôle {mandatory.value} est obligatoire")

        return {"valid": len(errors) == 0, "errors": errors}

    def _auto_configure_roles(self):
        """Configure automatiquement les rôles basé sur le nombre de joueurs.

        Principe :
        - ~20-25% de méchants
        - Rôles obligatoires : Sorcière, Voyante, Chasseur
        - Rôles à pouvoir (Garde, Médium) : uniques sous 10 joueurs, doublables au-delà
        """
        n = len(self.players)

        # ── Calcul du nombre de méchants (~20-25%) ──
        evil_ratio = random.uniform(0.20, 0.25)
        evil_count = max(1, round(n * evil_ratio))
        good_count = n - evil_count

        # ── Attribution des rôles méchants ──
        evil_roles: list = []
        for _ in range(evil_count):
            roll = random.random()
            if roll < 0.01 and not any(r.role_type == RoleType.LOUP_NOIR for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_NOIR))
            elif roll < 0.03 and not any(r.role_type == RoleType.LOUP_BLANC for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_BLANC))
            elif roll < 0.05 and not any(r.role_type == RoleType.LOUP_BAVARD for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_BAVARD))
            elif roll < 0.10 and not any(r.role_type == RoleType.LOUP_VOYANT for r in evil_roles):
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_VOYANT))
            else:
                evil_roles.append(RoleFactory.create_role(RoleType.LOUP_GAROU))

        # ── Attribution des rôles gentils ──
        good_roles: list = [
            RoleFactory.create_role(RoleType.SORCIERE),
            RoleFactory.create_role(RoleType.VOYANTE),
            RoleFactory.create_role(RoleType.CHASSEUR),
        ]
        good_roles = good_roles[:good_count]

        unique_good = [
            RoleType.CUPIDON, RoleType.VOLEUR,
            RoleType.IDIOT, RoleType.CORBEAU,
            RoleType.MONTREUR_OURS, RoleType.MERCENAIRE, RoleType.MENTALISTE,
            RoleType.DICTATEUR, RoleType.ENFANT_SAUVAGE,
        ]
        if evil_count >= 2:
            unique_good.append(RoleType.PETITE_FILLE)

        power_good = [
            RoleType.VOYANTE_AURA,
            RoleType.GARDE, RoleType.MEDIUM,
        ]

        assigned_power_counts: dict = {
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
        }

        available_unique = list(unique_good)
        random.shuffle(available_unique)

        for rt in available_unique:
            if len(good_roles) >= good_count:
                break
            if random.random() < 0.40:
                good_roles.append(RoleFactory.create_role(rt))

        available_power = list(power_good)
        random.shuffle(available_power)

        for rt in available_power:
            if len(good_roles) >= good_count:
                break
            if random.random() < 0.50:
                good_roles.append(RoleFactory.create_role(rt))
                assigned_power_counts[rt] = assigned_power_counts.get(rt, 0) + 1

        non_duplicable = {RoleType.SORCIERE, RoleType.VOYANTE, RoleType.CHASSEUR}
        while len(good_roles) < good_count:
            if n >= 10 and random.random() < 0.12:
                rt = random.choice(power_good)
                if rt not in non_duplicable:
                    count = assigned_power_counts.get(rt, 0)
                    if count < 2:
                        good_roles.append(RoleFactory.create_role(rt))
                        assigned_power_counts[rt] = count + 1
                        continue

            good_roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))

        self.available_roles = evil_roles + good_roles

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
                'team': role.team
            }
        return summary

    # ==================== Utilitaires ====================

    def log(self, message: str):
        """Ajoute un message au log de la partie."""
        self.game_log.append(message)

    def get_game_state(self) -> dict:
        """Retourne l'état actuel de la partie."""
        return {
            "phase": self.phase.value,
            "day": self.day_count,
            "night": self.night_count,
            "living_players": len(self.get_living_players()),
            "total_players": len(self.players),
            "wolves_alive": len(self.get_living_wolves()),
            "players": [
                {
                    "pseudo": p.pseudo,
                    "is_alive": p.is_alive,
                    "role": p.role.role_type.value if p.role else None,
                    "is_mayor": p.is_mayor,
                    "can_vote": p.can_vote
                }
                for p in self.players.values()
            ]
        }

    def save_state(self):
        """Sauvegarde l'état du jeu dans la base de données."""
        try:
            votes_by_target: Dict[str, List[str]] = {}
            for voter_uid, target_uid in self.vote_manager.votes.items():
                if target_uid not in votes_by_target:
                    votes_by_target[target_uid] = []
                votes_by_target[target_uid].append(voter_uid)

            wolf_votes_by_target: Dict[str, List[str]] = {}
            for voter_uid, target_uid in self.vote_manager.wolf_votes.items():
                if target_uid not in wolf_votes_by_target:
                    wolf_votes_by_target[target_uid] = []
                wolf_votes_by_target[target_uid].append(voter_uid)

            self.db.save_game_state(
                phase=self.phase,
                day_count=self.day_count,
                start_time=self.start_time,
                players=self.players,
                votes=votes_by_target,
                wolf_votes=wolf_votes_by_target,
                additional_data={
                    'game_id': self.game_id,
                    'night_count': self.night_count
                }
            )
            logger.info("État du jeu sauvegardé")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
