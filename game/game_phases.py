"""Mixin pour la gestion des phases de jeu.

Contient la logique de transition entre les phases :
nuit → jour → vote → nuit, et l'élection du maire.
"""

import random
import logging
from typing import Optional, List, Dict, TYPE_CHECKING
from datetime import datetime

from models.enums import GamePhase, Team, RoleType
from models.player import Player
from models.role import Role
from roles import RoleFactory

if TYPE_CHECKING:
    from game.game_manager import GameManager

logger = logging.getLogger(__name__)


class PhaseManagerMixin:
    """Mixin gérant les transitions de phases du jeu."""

    def start_game(self: 'GameManager', player_ids: Optional[List[str]] = None, immediate_night: bool = True) -> dict:
        """Démarre la partie.

        Args:
            player_ids: Liste optionnelle d'user_ids. Si fournie, crée les
                       joueurs automatiquement. Sinon, utilise les joueurs
                       déjà ajoutés via add_player().
            immediate_night: Si True (défaut), la phase NIGHT démarre immédiatement
                            (pour les tests et le mode autonome). Si False, la partie
                            démarre en phase DAY d'attente et c'est le scheduler qui
                            déclenchera la première nuit à NIGHT_START_HOUR.
        """
        if self.phase != GamePhase.SETUP:
            return {"success": False, "message": "La partie a déjà commencé"}

        # Créer les joueurs depuis les IDs si fournis
        if player_ids:
            for uid in player_ids:
                if uid not in self.players:
                    pseudo = uid.split(':')[0].lstrip('@') if ':' in uid else uid
                    self.add_player(pseudo, uid)

        if len(self.players) < 5:
            return {"success": False, "message": "Il faut au moins 5 joueurs pour commencer"}

        # Auto-configurer les rôles si non définis
        if not self.available_roles:
            self._auto_configure_roles()

        # Compléter avec des villageois si nécessaire
        while len(self.available_roles) < len(self.players):
            self.available_roles.append(RoleFactory.create_role(RoleType.VILLAGEOIS))

        # Valider les rôles obligatoires avant de distribuer
        validation = self._validate_mandatory_roles(self.available_roles)
        if not validation["valid"]:
            return {"success": False, "message": " ; ".join(validation["errors"])}

        # Distribuer les rôles aléatoirement
        players_list = list(self.players.values())
        random.shuffle(players_list)
        random.shuffle(self.available_roles)

        # Mélanger l'ordre d'assise (cercle)
        random.shuffle(self._player_order)

        for i, player in enumerate(players_list):
            if i < len(self.available_roles):
                self.available_roles[i].assign_to_player(player)
                self.vote_manager.register_player(player)

        # Appeler les callbacks de début de partie
        for player in self.players.values():
            if player.role:
                player.role.on_game_start(self)

        # Si un Voleur est présent, ajouter 2 cartes supplémentaires
        has_voleur = any(
            p.role and p.role.role_type == RoleType.VOLEUR
            for p in self.players.values()
        )
        if has_voleur:
            excluded_from_pool = {RoleType.VOLEUR}
            extra_pool = [
                rt for rt in RoleFactory.get_available_roles()
                if rt not in excluded_from_pool and rt not in self.disabled_roles
            ]
            extras = random.sample(extra_pool, min(2, len(extra_pool)))
            for rt in extras:
                self.extra_roles.append(RoleFactory.create_role(rt))

        self.log("La partie commence !")
        self.day_count = 0
        self.start_time = datetime.now()

        if immediate_night:
            self.phase = GamePhase.NIGHT
            self.night_count = 1
            self._start_night()
        else:
            self.phase = GamePhase.DAY
            self.night_count = 0
            self.vote_manager.reset_mayor_votes()
            self.mayor_election_done = False

        self.save_state()
        return {"success": True, "message": "La partie a commencé !"}

    # ==================== Nuit ====================

    def begin_night(self: 'GameManager') -> dict:
        """Démarre une nouvelle nuit (API publique pour le bot)."""
        if self.phase == GamePhase.ENDED:
            return {"success": False, "message": "La partie est terminée"}

        dictator_deaths: List[Player] = []
        if self.phase == GamePhase.DAY:
            dictator_deaths = self.resolve_dictator_indecision()

        self.night_count += 1
        self._start_night()

        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {"success": True, "winner": winner, "dictator_deaths": dictator_deaths}

        return {"success": True, "dictator_deaths": dictator_deaths}

    def _start_night(self: 'GameManager'):
        """Commence une nouvelle nuit (logique interne)."""
        self.log(f"=== Nuit {self.night_count} ===")
        self.phase = GamePhase.NIGHT
        self.action_manager.reset()
        self.vote_manager.reset_votes(wolf_votes=True)

        self.check_hunter_shot()

        for player in self.players.values():
            player.votes_against = 0
            player.reset_daily_data()

        self._pending_kills = []

        for player in self.players.values():
            if player.role and player.is_alive:
                player.role.on_night_start(self)

        jailer, prisoner = self.get_jailer_and_prisoner()
        self.set_jailed_player(prisoner)

        for pending_player in self._pending_kills:
            if pending_player.is_alive:
                self.kill_player(pending_player, killed_during_day=False)
        self._pending_kills = []

        self.save_state()

    def end_night(self: 'GameManager') -> dict:
        """Termine la nuit et exécute les actions."""
        if self.phase != GamePhase.NIGHT:
            return {"success": False, "message": "Ce n'est pas la nuit"}

        self._auto_resolve_voleur()
        self._auto_resolve_enfant_sauvage()
        self._auto_resolve_cupidon()

        results = self.action_manager.execute_night_actions(self)

        if results["deaths"]:
            for dead in results["deaths"]:
                self.log(f"{dead.pseudo} est mort.e cette nuit")
                self.mute_dead_player(dead.user_id)
                if dead.role and dead.role.can_vote_with_wolves():
                    self.remove_wolf_from_room(dead.user_id)
                for player in self.players.values():
                    if player.role:
                        player.role.on_player_death(self, dead, killed_during_day=False)

            for dead in results["deaths"]:
                if dead.is_mayor:
                    dead.is_mayor = False
                    self._pending_mayor_succession = dead
                    self.log(f"Le maire {dead.pseudo} est mort.e ! Succession nécessaire.")
                    break
        else:
            self.log("Personne n'est mort.e cette nuit")

        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {"success": True, "winner": winner, "results": results}

        self.day_count += 1
        self._start_day()

        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {"success": True, "winner": winner, "results": results}

        return {"success": True, "results": results}

    def resolve_night(self: 'GameManager') -> dict:
        """Résout les actions de nuit et retourne les résultats.

        Wrapper autour de end_night() pour l'interface du bot.
        """
        if self.phase != GamePhase.NIGHT:
            return {
                "deaths": [],
                "saved": [],
                "guard_saved": [],
                "wolf_target": None,
                "converted": None,
                "winner": None,
            }

        result = self.end_night()

        deaths = []
        saved = []
        guard_saved = []
        wolf_target = None
        converted = None

        if result.get("results"):
            deaths = [p.user_id for p in result["results"].get("deaths", [])]
            saved = [p.user_id for p in result["results"].get("saved", [])]
            guard_saved = [p.user_id for p in result["results"].get("guard_saved", [])]
            if result["results"].get("wolf_target"):
                wolf_target = result["results"]["wolf_target"].user_id
            if result["results"].get("converted"):
                converted = result["results"]["converted"].user_id

        return {
            "deaths": deaths,
            "saved": saved,
            "guard_saved": guard_saved,
            "wolf_target": wolf_target,
            "converted": converted,
            "winner": result.get("winner")
        }

    # ==================== Jour ====================

    def _start_day(self: 'GameManager'):
        """Commence un nouveau jour."""
        self.log(f"=== Jour {self.day_count} ===")
        self.phase = GamePhase.DAY

        self.set_jailed_player(None)

        self.check_hunter_shot()

        self._pending_kills = []
        for player in self.players.values():
            if player.role and player.is_alive:
                player.role.on_day_start(self)

        for pending_player in self._pending_kills:
            if pending_player.is_alive:
                self.kill_player(pending_player, killed_during_day=True)
        self._pending_kills = []

        for player in self.players.values():
            if player.role and player.role.role_type == RoleType.MONTREUR_OURS:
                if player.role.check_for_wolves(self):
                    self.log("L'ours du montreur d'ours grogne !")

        self.save_state()

    # ==================== Vote ====================

    def start_vote_phase(self: 'GameManager') -> dict:
        """Commence la phase de vote."""
        if self.phase not in (GamePhase.DAY, GamePhase.VOTE):
            return {"success": False, "message": "Ce n'est pas le jour"}

        if self.night_count < 1:
            return {"success": False, "message": "La première nuit n'a pas encore eu lieu"}

        self.phase = GamePhase.VOTE
        self.vote_manager.reset_votes()
        self.log("Phase de vote commencée")

        return {"success": True, "message": "Phase de vote commencée"}

    # ==================== Élection du Maire ====================

    def resolve_mayor_election(self: 'GameManager') -> dict:
        """Résout l'élection du maire (appelé à la fin de la première phase de vote).

        Le candidat avec le plus de votes est élu.
        En cas d'égalité → pas de maire.
        Si aucun vote → pas de maire.
        Ne change PAS la phase courante.
        """
        if self.mayor_election_done:
            return {"success": False, "message": "L'élection du maire a déjà eu lieu"}

        if self.get_mayor():
            self.mayor_election_done = True
            return {"success": False, "message": "Un maire existe déjà"}

        counts = self.vote_manager.count_mayor_votes()
        elected = None

        if counts:
            max_score = max(counts.values())
            if max_score > 0:
                most_voted_uids = [uid for uid, c in counts.items() if c == max_score]

                if len(most_voted_uids) == 1:
                    elected = self.vote_manager._player_cache.get(most_voted_uids[0])
                else:
                    self.log("Égalité pour l'élection du maire — pas de maire élu")

        if not elected:
            self.log("Pas de maire élu (aucun vote ou égalité)")

        if elected:
            elected.is_mayor = True
            self.log(f"{elected.pseudo} est élu maire !")

        self.vote_manager.reset_mayor_votes()
        self.mayor_election_done = True

        return {
            "success": True,
            "elected": elected,
            "message": f"{elected.pseudo} est élu maire !" if elected else "Aucun maire élu"
        }

    def can_vote_mayor(self: 'GameManager') -> bool:
        """Vérifie si l'élection du maire est en cours (vote-maire disponible)."""
        if self.mayor_election_done:
            return False
        if self.get_mayor():
            return False
        if self.night_count < 1:
            return False
        if self.phase not in (GamePhase.DAY, GamePhase.VOTE):
            return False
        return True

    def end_vote_phase(self: 'GameManager') -> dict:
        """Termine la phase de vote et élimine le joueur le plus voté.
        
        Résout aussi l'élection du maire si c'est la première phase de vote
        et qu'il n'y a pas encore de maire.
        """
        if self.phase != GamePhase.VOTE:
            return {"success": False, "message": "Ce n'est pas la phase de vote"}

        # Résoudre l'élection du maire en parallèle si applicable
        mayor_result = None
        if not self.mayor_election_done and not self.get_mayor():
            mayor_result = self.resolve_mayor_election()

        most_voted = self.vote_manager.get_most_voted()
        all_deaths = []

        pardoned_idiot = None

        if not most_voted:
            self.log("Aucun joueur n'a été éliminé (égalité ou pas de votes)")
        else:
            if most_voted.role and most_voted.role.role_type == RoleType.IDIOT:
                if most_voted.role.on_voted_out(self):
                    self.log(f"{most_voted.pseudo} est l'idiot ! Il est gracié mais perd son droit de vote.")
                    pardoned_idiot = most_voted
                    most_voted = None

            if most_voted:
                self.log(f"{most_voted.pseudo} a été éliminé par vote")
                all_deaths = self.kill_player(most_voted, killed_during_day=True, voted_out=True)

        dictator_deaths = self.resolve_dictator_indecision()

        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {
                "success": True,
                "winner": winner,
                "eliminated": most_voted,
                "all_deaths": all_deaths,
                "dictator_deaths": dictator_deaths,
                "pardoned_idiot": pardoned_idiot,
                "mayor_result": mayor_result
            }

        self.night_count += 1
        self._start_night()

        winner = self.check_win_condition()
        if winner:
            self.phase = GamePhase.ENDED
            return {
                "success": True,
                "winner": winner,
                "eliminated": most_voted,
                "all_deaths": all_deaths,
                "dictator_deaths": dictator_deaths,
                "pardoned_idiot": pardoned_idiot,
                "mayor_result": mayor_result
            }

        return {
            "success": True,
            "eliminated": most_voted,
            "all_deaths": all_deaths,
            "dictator_deaths": dictator_deaths,
            "pardoned_idiot": pardoned_idiot,
            "mayor_result": mayor_result
        }

    # ==================== Dictateur ====================

    def resolve_dictator_indecision(self: 'GameManager') -> List[Player]:
        """Tue le Dictateur s'il a arme son pouvoir et n'a pas frappe avant la nuit."""
        deaths: List[Player] = []
        for player in self.players.values():
            if not player.is_alive or not player.role:
                continue
            if player.role.role_type != RoleType.DICTATEUR:
                continue
            if not getattr(player.role, 'is_armed', False):
                continue
            if player.role.has_used_power:
                continue
            player.role.is_armed = False
            player.role.has_used_power = True
            deaths.extend(self.kill_player(player, killed_during_day=True))

        return deaths
