"""Gestionnaire principal du jeu."""

from typing import Dict, List, Optional
import random
import uuid
from datetime import datetime
import logging
from models.player import Player
from models.enums import GamePhase, Team, RoleType
from models.role import Role
from roles import RoleFactory
from game.vote_manager import VoteManager
from game.action_manager import ActionManager
from database.game_db import GameDatabase

# Alias pour compatibilité
Phase = GamePhase

logger = logging.getLogger(__name__)


class GameManager:
    """Gestionnaire principal du jeu Loup-Garou."""
    
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
        """Trouve un joueur par son user_id (alias)."""
        return self.players.get(user_id)
    
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
        # "alice:matrix.org" → chercher pseudo "alice"
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
        """Retourne les voisins d'un joueur (pour le montreur d'ours)."""
        if player.user_id not in self._player_order:
            return []
        
        index = self._player_order.index(player.user_id)
        n = len(self._player_order)
        neighbors = []
        
        # Voisin de gauche
        left_uid = self._player_order[(index - 1) % n]
        if left_uid in self.players:
            neighbors.append(self.players[left_uid])
        
        # Voisin de droite
        right_uid = self._player_order[(index + 1) % n]
        if right_uid in self.players:
            neighbors.append(self.players[right_uid])
        
        return neighbors
    
    def get_available_roles(self) -> List[Role]:
        """Retourne les rôles non assignés."""
        assigned_roles = [p.role for p in self.players.values() if p.role]
        return [r for r in self.available_roles if r not in assigned_roles]
    
    # ==================== Configuration ====================
    
    def set_roles(self, role_config: Dict[RoleType, int]):
        """Configure les rôles pour la partie."""
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}
        
        roles = []
        for role_type, count in role_config.items():
            for _ in range(count):
                roles.append(RoleFactory.create_role(role_type))
        
        if len(roles) < len(self.players):
            # Ajouter des villageois pour compléter
            while len(roles) < len(self.players):
                roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))
        
        self.available_roles = roles
        return {"success": True, "message": f"{len(roles)} rôles configurés"}
    
    def set_phase(self, phase: GamePhase):
        """Change la phase du jeu."""
        self.phase = phase
        logger.info(f"Phase changée: {phase.value}")
    
    def _auto_configure_roles(self):
        """Configure automatiquement les rôles basé sur le nombre de joueurs.
        
        Principe :
        - ~20-25% de méchants
        - Pour chaque slot méchant : probabilité faible d'être un loup spécial
          (2% Loup Bavard, 5% Loup Voyant, 2% Loup Blanc, 1% Loup Noir)
        - Rôles villageois piochés aléatoirement dans un pool (non prédictif)
        - Garantie d'au moins 1 loup
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
        # Pool de rôles possibles (chacun peut apparaître plusieurs fois,
        # sauf Cupidon et Voleur qui sont uniques)
        # Note : la Petite Fille n'est ajoutée que s'il y a >= 2 loups
        unique_good = [
            RoleType.CUPIDON, RoleType.VOLEUR, RoleType.CHASSEUR,
            RoleType.IDIOT, RoleType.CORBEAU,
            RoleType.MONTREUR_OURS, RoleType.MERCENAIRE, RoleType.MENTALISTE,
            RoleType.DICTATEUR, RoleType.ENFANT_SAUVAGE,
        ]
        if evil_count >= 2:
            unique_good.append(RoleType.PETITE_FILLE)
        stackable_good = [
            RoleType.VILLAGEOIS, RoleType.VOYANTE, RoleType.VOYANTE_AURA,
            RoleType.SORCIERE, RoleType.GARDE, RoleType.MEDIUM,
        ]
        
        good_roles: list = []
        # D'abord on pioche parmi les rôles uniques (shuffle pour éviter la prédictibilité)
        available_unique = list(unique_good)
        random.shuffle(available_unique)
        
        for rt in available_unique:
            if len(good_roles) >= good_count:
                break
            # Chaque rôle unique a ~40% de chance d'être inclus
            if random.random() < 0.40:
                good_roles.append(RoleFactory.create_role(rt))
        
        # Compléter avec des rôles stackables (piochés au hasard)
        while len(good_roles) < good_count:
            rt = random.choice(stackable_good)
            good_roles.append(RoleFactory.create_role(rt))
        
        self.available_roles = evil_roles + good_roles
    
    # ==================== Cycle de jeu ====================
    
    def start_game(self, player_ids: Optional[List[str]] = None) -> dict:
        """Démarre la partie.
        
        Args:
            player_ids: Liste optionnelle d'user_ids. Si fournie, crée les
                       joueurs automatiquement. Sinon, utilise les joueurs
                       déjà ajoutés via add_player().
        """
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}
        
        # Créer les joueurs depuis les IDs si fournis
        if player_ids:
            for uid in player_ids:
                if uid not in self.players:
                    # Extraire un pseudo depuis l'ID Matrix (@user:server → user)
                    pseudo = uid.split(':')[0].lstrip('@') if ':' in uid else uid
                    self.add_player(pseudo, uid)
        
        if len(self.players) < 4:
            return {"success": False, "message": "Il faut au moins 4 joueurs pour commencer"}
        
        # Auto-configurer les rôles si non définis
        if not self.available_roles:
            self._auto_configure_roles()
        
        # Compléter avec des villageois si nécessaire
        while len(self.available_roles) < len(self.players):
            self.available_roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))
        
        # Distribuer les rôles aléatoirement
        players_list = list(self.players.values())
        random.shuffle(players_list)
        random.shuffle(self.available_roles)
        for i, player in enumerate(players_list):
            if i < len(self.available_roles):
                self.available_roles[i].assign_to_player(player)
                self.vote_manager.register_player(player)
        
        # Appeler les callbacks de début de partie
        for player in self.players.values():
            if player.role:
                player.role.on_game_start(self)
        
        # Vérifier qu'il y a au moins 1 rôle méchant
        if not self.has_evil_role():
            self.phase = GamePhase.SETUP
            return {"success": False, "message": "Il faut au moins un rôle méchant (loup) dans la partie"}
        
        # Si un Voleur est présent, ajouter 2 cartes supplémentaires
        has_voleur = any(
            p.role and p.role.role_type == RoleType.VOLEUR
            for p in self.players.values()
        )
        if has_voleur:
            extra_pool = [RoleType.VILLAGEOIS, RoleType.CHASSEUR, RoleType.VOYANTE,
                          RoleType.GARDE, RoleType.SORCIERE, RoleType.CORBEAU]
            extras = random.sample(extra_pool, min(2, len(extra_pool)))
            for rt in extras:
                self.extra_roles.append(RoleFactory.create_role(rt))
        
        self.log("La partie commence !")
        self.phase = GamePhase.NIGHT
        self.day_count = 1
        self.night_count = 1
        self.start_time = datetime.now()
        self._start_night()
        
        # Sauvegarder l'état initial
        self.save_state()
        
        return {"success": True, "message": "La partie a commencé !"}
    
    def _start_night(self):
        """Commence une nouvelle nuit."""
        self.log(f"=== Nuit {self.night_count} ===")
        self.phase = GamePhase.NIGHT
        self.action_manager.reset()
        self.vote_manager.reset_votes(wolf_votes=True)
        
        # Vérifier si le chasseur peut tirer
        self.check_hunter_shot()
        
        # Réinitialiser les données journalières + votes_against du Corbeau
        for player in self.players.values():
            player.votes_against = 0  # Reset Corbeau votes (vote phase is over)
            player.reset_daily_data()
        
        # Appeler les callbacks de début de nuit
        for player in self.players.values():
            if player.role and player.is_alive:
                player.role.on_night_start(self)
        
        # Sauvegarder l'état
        self.save_state()
    
    def end_night(self) -> dict:
        """Termine la nuit et exécute les actions."""
        if self.phase != GamePhase.NIGHT:
            return {"success": False, "message": "Ce n'est pas la nuit"}
        
        # Auto-résoudre le Voleur si nécessaire
        self._auto_resolve_voleur()
        
        # Exécuter les actions de la nuit
        results = self.action_manager.execute_night_actions(self)
        
        # Log des événements
        if results["deaths"]:
            for dead in results["deaths"]:
                self.log(f"{dead.pseudo} est mort cette nuit")
                
                # Muter le joueur mort
                self.mute_dead_player(dead.user_id)
                
                # Si c'est un loup, le retirer du salon
                if dead.role and dead.role.can_vote_with_wolves():
                    self.remove_wolf_from_room(dead.user_id)
                
                # Notifier les rôles
                for player in self.players.values():
                    if player.role:
                        player.role.on_player_death(self, dead, killed_during_day=False)
        else:
            self.log("Personne n'est mort cette nuit")
        
        # Vérifier les conditions de victoire
        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {"success": True, "winner": winner, "results": results}
        
        # Passer au jour
        self.day_count += 1
        self._start_day()
        
        return {"success": True, "results": results}
    
    def resolve_night(self) -> dict:
        """Résout les actions de nuit et retourne les résultats.
        
        Wrapper autour de end_night() pour l'interface du bot.
        
        Returns:
            dict avec 'deaths' (liste d'user_ids), 'saved' (liste d'user_ids),
            'wolf_target' (Optional[str]), 'converted' (Optional[str]),
            'winner' (Optional[Team])
        """
        if self.phase != GamePhase.NIGHT:
            return {"deaths": [], "saved": [], "wolf_target": None, "converted": None, "winner": None}
        
        result = self.end_night()
        
        deaths = []
        saved = []
        wolf_target = None
        converted = None
        
        if result.get("results"):
            deaths = [p.user_id for p in result["results"].get("deaths", [])]
            saved = [p.user_id for p in result["results"].get("saved", [])]
            if result["results"].get("wolf_target"):
                wolf_target = result["results"]["wolf_target"].user_id
            if result["results"].get("converted"):
                converted = result["results"]["converted"].user_id
        
        return {
            "deaths": deaths,
            "saved": saved,
            "wolf_target": wolf_target,
            "converted": converted,
            "winner": result.get("winner")
        }
    
    def _start_day(self):
        """Commence un nouveau jour."""
        self.log(f"=== Jour {self.day_count} ===")
        self.phase = GamePhase.DAY
        
        # Vérifier si le chasseur peut tirer
        self.check_hunter_shot()
        
        # Appeler les callbacks de début de jour
        for player in self.players.values():
            if player.role and player.is_alive:
                player.role.on_day_start(self)
        
        # Vérifier le montreur d'ours
        for player in self.players.values():
            if player.role and player.role.role_type == RoleType.MONTREUR_OURS:
                if player.role.check_for_wolves(self):
                    self.log("L'ours du montreur d'ours grogne !")
        
        # Sauvegarder l'état
        self.save_state()
    
    def start_vote_phase(self) -> dict:
        """Commence la phase de vote."""
        if self.phase not in (GamePhase.DAY, GamePhase.VOTE):
            return {"success": False, "message": "Ce n'est pas le jour"}
        
        self.phase = GamePhase.VOTE
        self.vote_manager.reset_votes()
        
        # Réinitialiser les votes_against SAUF ceux du Corbeau
        # (le Corbeau pose ses votes la nuit, ils doivent persister
        # jusqu'au vote du jour suivant — pas besoin de reset ici,
        # ils sont déjà en place)
        
        self.log("Phase de vote commencée")
        
        return {"success": True, "message": "Phase de vote commencée"}
    
    def end_vote_phase(self) -> dict:
        """Termine la phase de vote et élimine le joueur le plus voté."""
        if self.phase != GamePhase.VOTE:
            return {"success": False, "message": "Ce n'est pas la phase de vote"}
        
        most_voted = self.vote_manager.get_most_voted()
        all_deaths = []
        
        if not most_voted:
            self.log("Aucun joueur n'a été éliminé (égalité ou pas de votes)")
        else:
            # Vérifier si c'est l'idiot
            if most_voted.role and most_voted.role.role_type == RoleType.IDIOT:
                if most_voted.role.on_voted_out(self):
                    self.log(f"{most_voted.pseudo} est l'idiot ! Il est gracié mais perd son droit de vote.")
                    most_voted = None
            
            if most_voted:
                self.log(f"{most_voted.pseudo} a été éliminé par vote")
                all_deaths = self.kill_player(most_voted, killed_during_day=True)
        
        # Vérifier les conditions de victoire
        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {"success": True, "winner": winner, "eliminated": most_voted, "all_deaths": all_deaths}
        
        # Passer à la nuit suivante
        self.night_count += 1
        self._start_night()
        
        return {"success": True, "eliminated": most_voted, "all_deaths": all_deaths}
    
    # ==================== Conditions de victoire ====================
    
    def check_win_condition(self) -> Optional[Team]:
        """Vérifie les conditions de victoire.
        
        Ordre de priorité :
        1. Couple (2 derniers vivants sont amoureux)
        2. Loup Blanc (seul survivant)
        3. Village (plus aucun loup vivant)
        4. Loups (il ne reste QUE des loups vivants)
        
        Note : Le maire et le corbeau peuvent retourner la situation,
        donc les loups ne gagnent que quand il n'y a plus un seul
        non-loup en vie.
        
        Returns:
            Team gagnante ou None si la partie continue.
        """
        living_players = self.get_living_players()
        
        if not living_players:
            return Team.NEUTRE  # Égalité - tout le monde est mort
        
        wolves = [p for p in living_players if p.get_team() == Team.MECHANT]
        non_wolves = [p for p in living_players if p.get_team() != Team.MECHANT]
        
        # 1. Couple gagne (les 2 derniers vivants sont amoureux)
        if len(living_players) == 2:
            lovers = [p for p in living_players if p.lover and p.lover.is_alive]
            if len(lovers) == 2:
                return Team.COUPLE
        
        # 2. Loup Blanc seul survivant
        if len(living_players) == 1:
            sole = living_players[0]
            if sole.role and sole.role.role_type == RoleType.LOUP_BLANC:
                return Team.NEUTRE  # Victoire solo du Loup Blanc
        
        # 3. Village gagne (plus aucun loup vivant)
        if not wolves:
            return Team.GENTIL
        
        # 4. Loups gagnent (il ne reste QUE des loups)
        # Le Loup Blanc seul ne déclenche PAS la victoire des loups
        if not non_wolves:
            regular_wolves = [
                p for p in wolves
                if not p.role or p.role.role_type != RoleType.LOUP_BLANC
            ]
            if regular_wolves:
                return Team.MECHANT
            # Sinon il reste des loups blancs uniquement → pas encore gagné
        
        return None
    
    def check_victory(self) -> Optional[Team]:
        """Alias pour check_win_condition (interface bot)."""
        return self.check_win_condition()
    
    def get_cupidon_player(self) -> Optional[Player]:
        """Retourne le joueur Cupidon (vivant ou mort), ou None."""
        for p in self.players.values():
            if p.role and p.role.role_type == RoleType.CUPIDON:
                return p
        return None
    
    def has_evil_role(self) -> bool:
        """Vérifie qu'il y a au moins un rôle méchant dans la partie."""
        return any(
            p.role and p.get_team() == Team.MECHANT
            for p in self.players.values()
        )
    
    # ==================== Voleur ====================
    
    def _auto_resolve_voleur(self):
        """Auto-résout le Voleur en fin de nuit si nécessaire."""
        for player in list(self.players.values()):
            if (player.role and 
                player.role.role_type == RoleType.VOLEUR and
                not player.role.has_used_power):
                voleur_role = player.role
                if voleur_role.drawn_roles:
                    # A tiré 2 cartes mais n'a pas choisi → auto-assigner la première
                    chosen_role = voleur_role.drawn_roles[0]
                    chosen_role.assign_to_player(player)
                    self.log(f"{player.pseudo} n'a pas choisi, "
                            f"il reçoit automatiquement le rôle {chosen_role.name}")
                else:
                    # N'a rien fait → reste Voleur (comme un Villageois)
                    voleur_role.has_used_power = True
                    self.log(f"{player.pseudo} reste Voleur (sans pouvoir)")
    
    # ==================== Résumé des rôles ====================
    
    def get_roles_summary(self) -> dict:
        """Retourne un résumé des rôles en jeu (pour l'annonce).
        
        Returns:
            Dict[RoleType, dict] avec 'count', 'name', 'description', 'team'
        """
        from collections import Counter
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
            # Transformer les votes pour la DB (target → [voters])
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
    
    def cancel_player_actions(self, user_id: str):
        """Annule tous les votes et actions d'un joueur."""
        logger.info(f"Annulation des actions de {user_id}")
        
        # Retirer les votes du joueur
        self.vote_manager.remove_voter(user_id)
        
        # Annuler les actions nocturnes
        self.action_manager.cancel_player_actions(user_id)
        
        # Sauvegarder l'état
        self.save_state()
    
    def kill_player(self, player: Player, killed_during_day: bool = False) -> List[Player]:
        """Tue un joueur avec gestion complète de la chaîne de mort.
        
        Gère : kill → mute → retrait salon loups → notifications rôles.
        Inclut automatiquement l'amoureux si applicable.
        
        Args:
            player: Le joueur à tuer.
            killed_during_day: True si tué par vote/exécution de jour.
        
        Returns:
            Liste de tous les joueurs morts (incluant l'amoureux).
        """
        if not player.is_alive:
            return []
        
        # Sauvegarder l'amoureux avant le kill (Player.kill cascade sur le lover)
        lover = player.lover if player.lover and player.lover.is_alive else None
        
        # Tuer le joueur (et son amoureux via Player.kill())
        player.kill()
        
        dead_players = [player]
        if lover and not lover.is_alive:
            dead_players.append(lover)
        
        # Muter et retirer du salon des loups pour chaque mort
        for dead in dead_players:
            self.mute_dead_player(dead.user_id)
            if dead.role and dead.role.can_vote_with_wolves():
                self.remove_wolf_from_room(dead.user_id)
        
        # Notifier TOUS les rôles (y compris morts) pour chaque mort
        # Important : les morts sont notifiés aussi (ex: Chasseur doit savoir qu'il est mort)
        for dead in dead_players:
            for p in self.players.values():
                if p.role:
                    p.role.on_player_death(self, dead, killed_during_day=killed_during_day)
        
        return dead_players
    
    def remove_wolf_from_room(self, user_id: str):
        """Retire un loup mort du salon des loups."""
        if self.on_remove_wolf_from_room:
            try:
                self.on_remove_wolf_from_room(user_id)
                logger.info(f"Loup {user_id} retiré du salon")
            except Exception as e:
                logger.error(f"Erreur lors du retrait du loup: {e}")
    
    def mute_dead_player(self, user_id: str):
        """Mute un joueur mort dans les salons."""
        if self.on_mute_player:
            try:
                self.on_mute_player(user_id)
                logger.info(f"Joueur {user_id} muté")
            except Exception as e:
                logger.error(f"Erreur lors du mute: {e}")
    
    def check_hunter_shot(self):
        """Vérifie si le chasseur peut tirer et active sa permission."""
        for player in self.players.values():
            if (player.role and 
                player.role.role_type == RoleType.CHASSEUR and 
                not player.is_alive and 
                not player.role.has_shot):
                
                # Tué le jour → tire la nuit (phase actuelle = NIGHT)
                # Tué la nuit → tire le jour (phase actuelle = DAY)
                if player.role.killed_during_day and self.phase == GamePhase.NIGHT:
                    player.role.can_shoot_now = True
                    logger.info(f"Chasseur {player.pseudo} peut tirer (tué le jour)")
                elif not player.role.killed_during_day and self.phase == GamePhase.DAY:
                    player.role.can_shoot_now = True
                    logger.info(f"Chasseur {player.pseudo} peut tirer (tué la nuit)")
    
    def end_game(self, winner: Team):
        """Termine la partie et sauvegarde les statistiques."""
        self.phase = GamePhase.ENDED
        end_time = datetime.now()
        
        try:
            self.db.save_game_result(
                game_id=self.game_id,
                start_time=self.start_time,
                end_time=end_time,
                winner_team=winner,
                players=self.players,
                total_days=self.day_count
            )
            logger.info(f"Partie {self.game_id} terminée, gagnant: {winner.value}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des résultats: {e}")
        
        # Nettoyer l'état du jeu en cours
        self.db.clear_current_game()
