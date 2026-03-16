"""Mixin pour le cycle de vie du jeu.

Contient : conditions de victoire, kill chain, fin de partie,
auto-résolution des rôles spéciaux, gestion du maire.
"""

import random
import logging
from typing import Optional, List, Dict, TYPE_CHECKING
from datetime import datetime

from models.enums import GamePhase, Team, RoleType
from models.player import Player
from roles import RoleFactory

if TYPE_CHECKING:
    from game.game_manager import GameManager

logger = logging.getLogger(__name__)


class GameLifecycleMixin:
    """Mixin gérant le cycle de vie : victoire, mort, fin de partie."""

    # ==================== Conditions de victoire ====================

    def check_win_condition(self: 'GameManager') -> Optional[Team]:
        """Vérifie les conditions de victoire.

        Ordre de priorité :
        0. Chasseur de Têtes (cible éliminée par vote, CDT vivant)
        1. Couple (2 derniers vivants sont amoureux)
        2. Loup Blanc (seul survivant)
        3. Village (plus aucun loup vivant)
        4. Loups (il ne reste QUE des loups vivants)
        """
        living_players = self.get_living_players()

        if not living_players:
            return Team.NEUTRE

        # 0. Chasseur de Têtes gagne seul
        for p in living_players:
            if (p.role and p.role.role_type == RoleType.CHASSEUR_DE_TETES
                    and hasattr(p.role, 'has_won') and p.role.has_won):
                return Team.NEUTRE

        wolves = [p for p in living_players if p.get_team() == Team.MECHANT]
        gentils = [p for p in living_players if p.get_team() == Team.GENTIL]

        # 1. Couple gagne (tous les vivants sont amoureux, groupe >= 2)
        if len(living_players) >= 2:
            start = next((p for p in living_players if p.get_lovers()), None)
            group = self.get_love_group(start, alive_only=True) if start else set()
            if len(group) >= 2 and len(group) == len(living_players):
                teams = {p.get_team() for p in group}
                if len(teams) == 1:
                    return next(iter(teams))
                return Team.COUPLE

        # 1b. Couple + Cupidon gagnent (si option activée)
        if self.cupidon_wins_with_couple and len(living_players) >= 3:
            start = next((p for p in living_players if p.get_lovers()), None)
            group = self.get_love_group(start, alive_only=True) if start else set()
            if len(group) >= 2 and len(group) < len(living_players):
                non_lovers = [p for p in living_players if p not in group]
                if (len(non_lovers) == 1 and non_lovers[0].role
                        and non_lovers[0].role.role_type == RoleType.CUPIDON):
                    teams = {p.get_team() for p in group}
                    if len(teams) == 1:
                        return next(iter(teams))
                    return Team.COUPLE

        # 2. Tueur solo survivant
        if len(living_players) == 1:
            sole = living_players[0]
            if sole.role and sole.role.role_type in {
                RoleType.LOUP_BLANC, RoleType.ASSASSIN, RoleType.PYROMANE
            }:
                return Team.NEUTRE

        # 3. Village gagne (plus aucun loup vivant ET au moins un gentil vivant)
        if not wolves and gentils:
            return Team.GENTIL

        # 4. Loups gagnent (plus aucun GENTIL vivant ET au moins un loup vivant)
        if not gentils and wolves:
            regular_wolves = [
                p for p in wolves
                if not p.role or p.role.role_type != RoleType.LOUP_BLANC
            ]
            if regular_wolves:
                return Team.MECHANT

        return None

    def check_victory(self: 'GameManager') -> Optional[Team]:
        """Alias pour check_win_condition (interface bot)."""
        return self.check_win_condition()

    # ==================== Gestion du maire ====================

    def get_cupidon_player(self: 'GameManager') -> Optional[Player]:
        """Retourne le joueur Cupidon (vivant ou mort), ou None."""
        for p in self.players.values():
            if p.role and p.role.role_type == RoleType.CUPIDON:
                return p
        return None

    def get_mayor(self: 'GameManager') -> Optional[Player]:
        """Retourne le joueur maire vivant, ou None."""
        for p in self.players.values():
            if p.is_mayor and p.is_alive:
                return p
        return None

    def designate_mayor(self: 'GameManager', target: Player) -> dict:
        """Désigne un nouveau maire (succession)."""
        if not self._pending_mayor_succession:
            return {"success": False, "message": "Aucune succession de maire en cours"}

        if not target.is_alive:
            return {"success": False, "message": "Le successeur doit être vivant"}

        old_mayor = self._pending_mayor_succession
        target.is_mayor = True
        self._pending_mayor_succession = None
        self.log(f"{target.pseudo} est le nouveau maire (désigné par {old_mayor.pseudo})")

        return {"success": True, "message": f"{target.pseudo} est le nouveau maire", "new_mayor": target}

    def auto_designate_mayor(self: 'GameManager') -> Optional[Player]:
        """Désigne automatiquement un maire aléatoire parmi les vivants."""
        if not self._pending_mayor_succession:
            return None

        living = self.get_living_players()
        if not living:
            self._pending_mayor_succession = None
            return None

        new_mayor = random.choice(living)
        new_mayor.is_mayor = True
        self._pending_mayor_succession = None
        self.log(f"{new_mayor.pseudo} est désigné maire par défaut")

        return new_mayor

    def has_evil_role(self: 'GameManager') -> bool:
        """Vérifie qu'il y a au moins un rôle méchant dans la partie."""
        return any(
            p.role and p.get_team() == Team.MECHANT
            for p in self.players.values()
        )

    # ==================== Kill chain ====================

    def kill_player(self: 'GameManager', player: Player, killed_during_day: bool = False, voted_out: bool = False) -> List[Player]:
        """Tue un joueur avec gestion complète de la chaîne de mort.

        Gère : kill → mute → retrait salon loups → notifications rôles.
        Inclut automatiquement l'amoureux si applicable.

        Returns:
            Liste de tous les joueurs morts (incluant l'amoureux).
        """
        if not player.is_alive:
            return []

        group = self.get_love_group(player)
        alive_group = [p for p in group if p.is_alive]
        player.kill()

        dead_players = [p for p in alive_group if not p.is_alive]

        for dead in dead_players:
            self.mute_dead_player(dead.user_id)
            if dead.role and dead.role.can_vote_with_wolves():
                self.remove_wolf_from_room(dead.user_id)

        for dead in dead_players:
            # voted_out ne s'applique qu'au joueur directement voté,
            # pas aux morts en cascade (ex: amoureux).
            is_primary = (dead == player)
            for p in self.players.values():
                if p.role:
                    p.role.on_player_death(
                        self, dead,
                        killed_during_day=killed_during_day,
                        voted_out=voted_out and is_primary,
                    )

        for dead in dead_players:
            if dead.is_mayor:
                dead.is_mayor = False
                self._pending_mayor_succession = dead
                self.log(f"Le maire {dead.pseudo} est mort.e ! Succession nécessaire.")
                break

        return dead_players

    def remove_wolf_from_room(self: 'GameManager', user_id: str):
        """Retire un loup mort du salon des loups."""
        if self.on_remove_wolf_from_room:
            try:
                self.on_remove_wolf_from_room(user_id)
                logger.info(f"Loup {user_id} retiré du salon")
            except Exception as e:
                logger.error(f"Erreur lors du retrait du loup: {e}")

    def mute_dead_player(self: 'GameManager', user_id: str):
        """Mute un joueur mort dans les salons."""
        if self.on_mute_player:
            try:
                self.on_mute_player(user_id)
                logger.info(f"Joueur {user_id} muté")
            except Exception as e:
                logger.error(f"Erreur lors du mute: {e}")

    def check_hunter_shot(self: 'GameManager'):
        """Vérifie si le chasseur peut tirer et active sa permission."""
        for player in self.players.values():
            if (player.role
                    and player.role.role_type == RoleType.CHASSEUR
                    and not player.is_alive
                    and not player.role.has_shot):
                player.role.can_shoot_now = True
                logger.info(f"Chasseur {player.pseudo} peut tirer")

    def cancel_player_actions(self: 'GameManager', user_id: str):
        """Annule tous les votes et actions d'un joueur."""
        logger.info(f"Annulation des actions de {user_id}")
        self.vote_manager.remove_voter(user_id)
        self.action_manager.cancel_player_actions(user_id)
        self.save_state()

    # ==================== Auto-résolution des rôles ====================

    def _auto_resolve_voleur(self: 'GameManager'):
        """Auto-résout le Voleur en fin de nuit si nécessaire."""
        for player in list(self.players.values()):
            if (player.role
                    and player.role.role_type == RoleType.VOLEUR
                    and not player.role.has_used_power):
                voleur_role = player.role
                if voleur_role.drawn_roles:
                    chosen_role = voleur_role.drawn_roles[0]
                    chosen_role.assign_to_player(player)
                    chosen_role.on_game_start(self)
                    self.log(f"{player.pseudo} n'a pas choisi, "
                             f"il reçoit automatiquement le rôle {chosen_role.name}")
                else:
                    voleur_role.has_used_power = True
                    self.log(f"{player.pseudo} reste Voleur (sans pouvoir)")

    def _auto_resolve_cupidon(self: 'GameManager'):
        """Consomme le pouvoir du Cupidon à la fin de la première nuit."""
        for player in list(self.players.values()):
            if (player.role
                    and player.role.role_type == RoleType.CUPIDON
                    and player.is_alive
                    and not player.role.has_used_power):
                player.role.has_used_power = True
                self.log(f"{player.pseudo} (Cupidon) n'a pas marié de couple — "
                         f"pouvoir perdu.")

    def _auto_resolve_enfant_sauvage(self: 'GameManager'):
        """Auto-résout l'Enfant Sauvage en fin de première nuit."""
        for player in list(self.players.values()):
            if (player.role
                    and player.role.role_type == RoleType.ENFANT_SAUVAGE
                    and player.is_alive
                    and not player.role.has_chosen_mentor):
                candidates = [p for p in self.get_living_players() if p != player]
                if candidates:
                    mentor = random.choice(candidates)
                    player.mentor = mentor
                    player.role.has_chosen_mentor = True
                    self.log(f"{player.pseudo} (Enfant Sauvage) n'a pas choisi — "
                             f"mentor auto-assigné : {mentor.pseudo}")

    # ==================== Fin de partie ====================

    def end_game(self: 'GameManager', winner: Team):
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
                total_days=self.day_count,
                cupidon_wins_with_couple=self.cupidon_wins_with_couple
            )
            logger.info(f"Partie {self.game_id} terminée, gagnant: {winner.value}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des résultats: {e}")

        self.db.clear_current_game()
