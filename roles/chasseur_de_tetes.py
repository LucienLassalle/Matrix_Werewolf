"""Rôle Chasseur de Têtes (Headhunter)."""

import random
from models.role import Role
from models.enums import RoleType, Team, ActionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_manager import GameManager
    from models.player import Player


class ChasseurDeTetes(Role):
    """Chasseur de Têtes - Gagne seul si le village élimine sa cible au vote.

    Lors de la première nuit, une cible lui est désignée aléatoirement.
    - Tant qu'il est en vie et que sa cible est vivante, il gagne seul
      si le village élimine sa cible au vote diurne.
    - Si la cible meurt d'une autre façon (loups, sorcière, chasseur…),
      le Chasseur de Têtes rejoint l'alliance du mal : il gagne si les
      loups-garous ou un tueur solo remportent la partie.
    """
    emoji = "🎯💀"

    def __init__(self):
        super().__init__(RoleType.CHASSEUR_DE_TETES, Team.NEUTRE)
        self.target_assigned = False
        self.target_dead_other = False  # Cible morte autrement que par vote
        self.has_won = False

    def get_description(self) -> str:
        return (
            "Chasseur de Têtes — Lors de la première nuit, une cible vous est "
            "désignée. Vous gagnez seul si votre cible se fait éliminer par "
            "le vote du village (et que vous êtes toujours en vie). "
            "Si votre cible meurt d'une autre façon, vous rejoignez "
            "l'alliance du mal (vous gagnez si les loups-garous gagnent)."
        )

    def on_game_start(self, game: 'GameManager'):
        """Assigne une cible aléatoire au début de la partie."""
        if not self.target_assigned:
            living_players = game.get_living_players()
            # Exclure soi-même et les loups-garous (la cible doit être un villageois)
            possible_targets = [
                p for p in living_players
                if p != self.player and p.get_team() != Team.MECHANT
            ]
            if not possible_targets:
                # Fallback : n'importe qui sauf soi-même
                possible_targets = [p for p in living_players if p != self.player]

            if possible_targets:
                self.player.target = random.choice(possible_targets)
                self.target_assigned = True

    def on_player_death(self, game: 'GameManager', dead_player: 'Player', **kwargs):
        """Vérifie si la cible est morte par vote ou autrement."""
        if not self.player or not self.player.target:
            return
        if dead_player != self.player.target:
            return

        voted_out = kwargs.get('voted_out', False)

        if voted_out and self.player.is_alive:
            # Victoire ! La cible a été éliminée par le vote du village.
            self.has_won = True
            game.log(
                f"{self.player.pseudo} (Chasseur de Têtes) a accompli sa "
                f"mission ! Sa cible {dead_player.pseudo} a été éliminée par le vote."
            )
        elif not voted_out:
            # La cible est morte autrement → rejoint l'alliance du mal
            self.target_dead_other = True
            self.team = Team.MECHANT
            game.log(
                f"La cible du Chasseur de Têtes ({dead_player.pseudo}) est morte "
                f"autrement que par vote. {self.player.pseudo} rejoint l'alliance du mal."
            )

    def can_act_at_night(self) -> bool:
        return False

    def can_vote_with_wolves(self) -> bool:
        """Le Chasseur de Têtes ne vote jamais avec les loups."""
        return False

    def get_state(self) -> dict:
        return {
            'target_assigned': self.target_assigned,
            'target_dead_other': self.target_dead_other,
            'has_won': self.has_won,
            'target_user_id': (
                self.player.target.user_id
                if self.player and self.player.target else None
            ),
            'team': self.team.value,
        }

    def restore_state(self, data: dict, players: dict):
        self.target_assigned = data.get('target_assigned', False)
        self.target_dead_other = data.get('target_dead_other', False)
        self.has_won = data.get('has_won', False)
        target_uid = data.get('target_user_id')
        if target_uid and self.player:
            self.player.target = players.get(target_uid)
        team_val = data.get('team')
        if team_val:
            self.team = Team(team_val)
