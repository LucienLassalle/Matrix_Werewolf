"""Mixin de persistance du jeu."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

from models.enums import GamePhase, RoleType
from models.player import Player
from roles import RoleFactory

if TYPE_CHECKING:
    from game.game_manager import GameManager

logger = logging.getLogger(__name__)


class GamePersistenceMixin:
    """Mixin pour sauvegarder et restaurer l'etat du jeu."""

    def get_game_state(self: 'GameManager') -> dict:
        """Retourne l'etat actuel de la partie."""
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
                    "can_vote": p.can_vote,
                }
                for p in self.players.values()
            ],
        }

    def save_state(self: 'GameManager'):
        """Sauvegarde l'etat du jeu dans la base de donnees."""
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

            mayor_votes = dict(self.vote_manager.mayor_votes_for)

            self.db.save_game_state(
                phase=self.phase,
                day_count=self.day_count,
                start_time=self.start_time,
                players=self.players,
                votes=votes_by_target,
                wolf_votes=wolf_votes_by_target,
                additional_data={
                    'game_id': self.game_id,
                    'night_count': self.night_count,
                    'player_order': self._player_order,
                    'mayor_election_done': self.mayor_election_done,
                    'cupidon_wins_with_couple': self.cupidon_wins_with_couple,
                    'mayor_votes': mayor_votes,
                    'pending_mayor_succession_uid': (
                        self._pending_mayor_succession.user_id
                        if self._pending_mayor_succession else None
                    ),
                    'game_log': self.game_log,
                    'extra_roles': [
                        r.role_type.value for r in self.extra_roles
                    ],
                }
            )
            logger.info("Etat du jeu sauvegarde")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")

    def load_state(self: 'GameManager') -> bool:
        """Restaure l'etat complet du jeu depuis la base de donnees."""
        try:
            data = self.db.load_game_state()
            if not data:
                logger.info("Aucun etat de jeu a restaurer")
                return False

            self.phase = GamePhase(data['phase'])
            self.day_count = data['day_count']
            if data.get('start_time'):
                self.start_time = datetime.fromisoformat(data['start_time'])

            additional = data.get('game_data', {}).get('additional', {})
            self.night_count = additional.get('night_count', 0)
            self.game_id = additional.get('game_id', self.game_id)
            self.mayor_election_done = additional.get('mayor_election_done', False)
            self.cupidon_wins_with_couple = additional.get(
                'cupidon_wins_with_couple', self.cupidon_wins_with_couple
            )
            self.game_log = additional.get('game_log', [])

            self.players.clear()
            self._player_order.clear()

            for p_data in data['players']:
                uid = p_data['user_id']
                pseudo = p_data['pseudo']
                player = Player(pseudo, uid)
                player.is_alive = bool(p_data['is_alive'])
                player.is_mayor = bool(p_data['is_mayor'])
                player.is_protected = bool(p_data['is_protected'])
                player.votes_against = p_data.get('votes_against', 0)

                player_extra = {}
                if p_data.get('player_data'):
                    import json
                    player_extra = (
                        json.loads(p_data['player_data'])
                        if isinstance(p_data['player_data'], str)
                        else p_data['player_data']
                    )
                player.has_been_pardoned = player_extra.get('has_been_pardoned', False)
                player.can_vote = player_extra.get('can_vote', True)
                player.is_jailed = player_extra.get('is_jailed', False)
                if player_extra.get('display_name'):
                    player.display_name = player_extra['display_name']
                if player_extra.get('original_role_name'):
                    player.original_role_name = player_extra['original_role_name']

                if p_data.get('role_type'):
                    role_type = RoleType(p_data['role_type'])
                    role = RoleFactory.create_role(role_type)
                    role.assign_to_player(player)

                    role_state = player_extra.get('role_state', {})
                    if role_state:
                        role.restore_state(role_state, {})

                self.players[uid] = player
                self.vote_manager.register_player(player)

            saved_order = additional.get('player_order', [])
            if saved_order:
                self._player_order = [
                    uid for uid in saved_order if uid in self.players
                ]
            else:
                self._player_order = list(self.players.keys())

            for p_data in data['players']:
                uid = p_data['user_id']
                player = self.players.get(uid)
                if not player:
                    continue

                player_extra = {}
                if p_data.get('player_data'):
                    import json
                    player_extra = (
                        json.loads(p_data['player_data'])
                        if isinstance(p_data['player_data'], str)
                        else p_data['player_data']
                    )

                lover_ids = player_extra.get('lover_ids')
                if not lover_ids and p_data.get('lover_id'):
                    lover_ids = [p_data.get('lover_id')]

                if lover_ids:
                    for lover_uid in lover_ids:
                        if lover_uid and lover_uid in self.players:
                            other = self.players[lover_uid]
                            player.add_lover(other)
                            other.add_lover(player)

                mentor_uid = player_extra.get('mentor_user_id')
                if mentor_uid and mentor_uid in self.players:
                    player.mentor = self.players[mentor_uid]

                target_uid = player_extra.get('target_user_id')
                if target_uid and target_uid in self.players:
                    player.target = self.players[target_uid]

                if player.role:
                    role_state = player_extra.get('role_state', {})
                    if role_state:
                        player.role.restore_state(role_state, self.players)

            self.vote_manager.votes.clear()
            self.vote_manager.wolf_votes.clear()
            self.vote_manager.mayor_votes_for.clear()

            self._jailed_user_id = None
            for player in self.players.values():
                if player.is_jailed:
                    self._jailed_user_id = player.user_id
                    break

            for vote_row in data.get('village_votes', []):
                voter_id = vote_row['voter_id']
                target_id = vote_row['target_id']
                self.vote_manager.votes[voter_id] = target_id

            for vote_row in data.get('wolf_votes', []):
                voter_id = vote_row['voter_id']
                target_id = vote_row['target_id']
                self.vote_manager.wolf_votes[voter_id] = target_id

            saved_mayor_votes = additional.get('mayor_votes', {})
            for voter_uid, target_uid in saved_mayor_votes.items():
                self.vote_manager.mayor_votes_for[voter_uid] = target_uid

            pending_uid = additional.get('pending_mayor_succession_uid')
            if pending_uid and pending_uid in self.players:
                self._pending_mayor_succession = self.players[pending_uid]

            self.extra_roles.clear()
            for rt_val in additional.get('extra_roles', []):
                try:
                    self.extra_roles.append(RoleFactory.create_role(RoleType(rt_val)))
                except (ValueError, KeyError):
                    pass

            logger.info(
                "Etat du jeu restaure (phase=%s, jour=%d, nuit=%d, joueurs=%d)",
                self.phase.value, self.day_count, self.night_count, len(self.players),
            )
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la restauration de l'etat: {e}", exc_info=True)
            return False
