"""Gestion de fin de partie et victoire."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, Team, RoleType
from matrix_bot.scheduler import day_name_fr

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class PhaseEndgameHandlersMixin:
    """Callbacks de fin de partie et victoire."""

    async def _end_game(self: 'WerewolfBot'):
        """Termine la partie et nettoie les salons."""
        logger.info("Fin de la partie")

        if self._mayor_succession_task and not self._mayor_succession_task.done():
            self._mayor_succession_task.cancel()

        if self._vote_reminder_task and not self._vote_reminder_task.done():
            self._vote_reminder_task.cancel()

        if self.game_manager.phase != GamePhase.ENDED:
            self.game_manager.set_phase(GamePhase.ENDED)

        await self.room_manager.cleanup_rooms()

        self._accepting_registrations = True

        jour = day_name_fr(self._game_start_day)
        await self.client.send_message(
            self.lobby_room_id,
            "Les salons de jeu ont été supprimés.\n"
            f"Tapez `{self.command_prefix}inscription` pour participer à la prochaine partie "
            f"**{jour} à {self._game_start_hour}h**.",
            formatted=True,
        )

    async def _check_victory(self: 'WerewolfBot'):
        """Vérifie si une équipe a gagné."""
        winner = self.game_manager.check_victory()

        if winner:
            await self._announce_victory(winner)
            self.scheduler.stop()

    async def _announce_victory(self: 'WerewolfBot', winner: Team):
        """Annonce la victoire avec statistiques détaillées."""
        self.game_manager.end_game(winner)

        team_names = {
            Team.GENTIL: "🏘️ **Les Villageois**",
            Team.MECHANT: "🐺 **Les Loups-Garous**",
        }

        if winner == Team.NEUTRE:
            living = self.game_manager.get_living_players()
            cdt_winner = next(
                (p for p in living
                 if p.role and p.role.role_type == RoleType.CHASSEUR_DE_TETES
                 and hasattr(p.role, 'has_won') and p.role.has_won),
                None,
            )
            if cdt_winner:
                team_display = f"🎯 **{cdt_winner.display_name} (Chasseur de Têtes)**"
            elif living and living[0].role and living[0].role.role_type == RoleType.LOUP_BLANC:
                team_display = "🐺⚪ **Le Loup Blanc**"
            else:
                team_display = "☠️ **Personne** (égalité)"
        elif winner == Team.COUPLE:
            cupidon = self.game_manager.get_cupidon_player()
            living = self.game_manager.get_living_players()
            groups = self.game_manager.get_love_groups(alive_only=True)
            lovers = list(groups[0]) if groups else []
            cupidon_in_couple = cupidon and cupidon in lovers
            cupidon_wins = (cupidon and cupidon.is_alive
                            and (cupidon_in_couple or self._cupidon_wins_with_couple))
            if cupidon_wins and not cupidon_in_couple:
                team_display = "💕 **Le Couple + Cupidon**"
            else:
                team_display = "💕 **Le Couple**"
        else:
            team_display = team_names.get(winner, winner.value)

        message = f"🎉 **Partie terminée !**\n\n{team_display} a gagné !\n\n"

        message += "📋 **Rôles:**\n"
        for player in self.game_manager.players.values():
            status = "💀" if not player.is_alive else "✅"
            extras = []
            if player.is_mayor:
                extras.append("👑 Maire")
            if player.get_lovers():
                partner_names = ", ".join(p.display_name for p in player.get_lovers())
                extras.append(f"💕 couple avec {partner_names}")
            if player.original_role_name:
                extras.append(f"🎭 ex-{player.original_role_name}")
            if (player.role and player.role.role_type == RoleType.CUPIDON
                    and player.original_role_name == "Voleur"):
                extras.append("💘 Cupidon (ex-Voleur)")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            message += f"{status} **{player.display_name}**: {player.role.name}{extra_str}\n"

        message += "\n📊 **Statistiques de la partie:**\n"
        message += (
            f"• Durée : {self.game_manager.day_count} jour"
            f"{'s' if self.game_manager.day_count > 1 else ''}, "
            f"{self.game_manager.night_count} nuit"
            f"{'s' if self.game_manager.night_count > 1 else ''}\n"
        )

        living = self.game_manager.get_living_players()
        message += f"• Survivants : {len(living)} / {len(self.game_manager.players)}\n"

        if self._game_events:
            message += "\n📜 **Chronologie de la partie:**\n"

            current_phase = None
            for event in self._game_events:
                phase_label = None
                for prefix in ("Nuit ", "Jour "):
                    if event.startswith(prefix):
                        dash_pos = event.find(" — ")
                        if dash_pos != -1:
                            phase_label = event[:dash_pos]
                            event_text = event[dash_pos + 3:]
                        break

                if phase_label and phase_label != current_phase:
                    current_phase = phase_label
                    message += f"\n**{phase_label}**\n"

                if phase_label:
                    message += f"  • {event_text}\n"
                else:
                    message += f"  • {event}\n"

        await self.client.send_message(
            self.lobby_room_id,
            message,
            formatted=True,
        )
