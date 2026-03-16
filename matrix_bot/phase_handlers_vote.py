"""Gestion des callbacks de vote et rappels."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class PhaseVoteHandlersMixin:
    """Callbacks de vote, mentaliste et rappels."""

    async def _on_vote_start(self: 'WerewolfBot', phase: GamePhase):
        """Appelé au début de la phase de vote."""
        logger.info("🗳️ Début des votes")

        if self.game_manager.night_count < 1:
            logger.info("Pas de vote avant la première nuit — transition ignorée")
            return

        if self._day_hour == self._vote_hour:
            logger.info("DAY_START_HOUR == VOTE_START_HOUR — résolution de la nuit avant le vote")
            await self._on_day_start(phase)
            if self.game_manager.phase == GamePhase.ENDED:
                return

        result = self.game_manager.start_vote_phase()
        if not result.get("success"):
            logger.warning("Phase de vote refusée: %s", result.get("message"))
            return

        vote_msg = (
            "🗳️ **Phase de vote !**\n\n"
            "Les villageois doivent voter pour éliminer un suspect.\n"
            f"Utilisez `{self.command_prefix}vote {{pseudo}}` pour voter.\n\n"
            f"⏰ Vous avez jusqu'à **{self.scheduler.vote_end.strftime('%Hh%M')}** (début de la nuit)."
        )

        if self.game_manager.can_vote_mayor():
            vote_msg += (
                f"\n\n👑 **Élection du maire** — Votez aussi pour un maire !\n"
                f"Utilisez `{self.command_prefix}vote-maire {{pseudo}}` pour voter."
            )

        await self.room_manager.send_to_village(vote_msg)

        asyncio.create_task(self._schedule_mentaliste_notification())

        self._last_vote_snapshot = {}
        if self._vote_reminder_task and not self._vote_reminder_task.done():
            self._vote_reminder_task.cancel()
        self._vote_reminder_task = asyncio.create_task(self._schedule_vote_reminders())

    async def _check_mayor_election_progress(self: 'WerewolfBot'):
        """Vérifie la progression du vote pour l'élection du maire."""
        if not self.game_manager.can_vote_mayor():
            return

        living = self.game_manager.get_living_players()
        voters = set(self.game_manager.vote_manager.mayor_votes_for.keys())
        total = len(living)
        voted = len([p for p in living if p.user_id in voters])

        summary = self.game_manager.vote_manager.get_mayor_vote_summary()
        await self.room_manager.send_to_village(
            f"👑 **Élection du maire** — {voted}/{total} votes\n\n{summary}"
        )

    async def _schedule_mentaliste_notification(self: 'WerewolfBot'):
        """Envoie la prédiction du Mentaliste X heures avant la fin du vote."""
        from datetime import datetime, timedelta

        vote_end = datetime.combine(datetime.now().date(), self.scheduler.night_start)
        if vote_end < datetime.now():
            vote_end += timedelta(days=1)

        notify_time = vote_end - timedelta(hours=self.mentaliste_advance_hours)
        wait_seconds = (notify_time - datetime.now()).total_seconds()

        if wait_seconds > 0:
            logger.info(
                "Mentaliste: notification dans %0.f s (%sh avant fin du vote)",
                wait_seconds, self.mentaliste_advance_hours,
            )
            await asyncio.sleep(wait_seconds)

        if self.game_manager.phase != GamePhase.VOTE:
            return

        await self._notify_mentaliste()

    async def _notify_mentaliste(self: 'WerewolfBot'):
        """Envoie la prédiction du Mentaliste sur l'issue du vote en cours."""
        mentaliste = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.MENTALISTE):
                mentaliste = player
                break

        if not mentaliste:
            return

        most_voted = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=False)

        if not most_voted:
            await self.client.send_dm(
                mentaliste.user_id,
                "🔮 **Intuition du Mentaliste**\n\n"
                "Personne n'a encore reçu de votes... Impossible de prédire l'issue."
            )
            return

        outcome = mentaliste.role.predict_vote_outcome(self.game_manager, most_voted)

        if outcome == "positif":
            emoji = "✅"
            description = "**positif** — le joueur le plus voté est du côté des loups."
        elif outcome == "négatif":
            emoji = "❌"
            description = "**négatif** — le joueur le plus voté est du côté du village."
        else:
            emoji = "⚖️"
            description = "**neutre** — impossible de déterminer."

        hours_text = (
            f"{self.mentaliste_advance_hours:.0f}h"
            if self.mentaliste_advance_hours == int(self.mentaliste_advance_hours)
            else f"{self.mentaliste_advance_hours}h"
        )

        await self.client.send_dm(
            mentaliste.user_id,
            f"🔮 **Intuition du Mentaliste** ({hours_text} avant la fin du vote)\n\n"
            f"{emoji} Le vote semble être {description}\n\n"
            "💡 Cette information est basée sur les votes actuels — le résultat peut encore changer."
        )

        vote_summary = self.game_manager.vote_manager.get_vote_summary()
        await self.client.send_dm(
            mentaliste.user_id,
            f"📊 Joueur le plus voté actuellement : **{most_voted.display_name}**\n\n"
            f"**Résumé des votes :**\n{vote_summary}"
        )

        logger.info("Mentaliste notifié: issue du vote = %s", outcome)

    async def _schedule_vote_reminders(self: 'WerewolfBot'):
        """Planifie les rappels de vote pendant la phase de vote."""
        from datetime import datetime, timedelta

        try:
            vote_end = datetime.combine(datetime.now().date(), self.scheduler.night_start)
            if vote_end < datetime.now():
                vote_end += timedelta(days=1)

            while True:
                if self.game_manager.phase != GamePhase.VOTE:
                    return

                remaining = (vote_end - datetime.now()).total_seconds()

                if remaining <= 1800:
                    break

                wait = min(3600, remaining - 1800)
                await asyncio.sleep(wait)

                if self.game_manager.phase != GamePhase.VOTE:
                    return

                current_votes = dict(self.game_manager.vote_manager.votes)
                if current_votes != self._last_vote_snapshot:
                    self._last_vote_snapshot = current_votes
                    remaining = (vote_end - datetime.now()).total_seconds()
                    minutes_left = int(remaining / 60)
                    if minutes_left >= 60:
                        hours_left = round(minutes_left / 60)
                        time_str = f"{hours_left} heure{'s' if hours_left > 1 else ''}"
                    else:
                        time_str = f"{minutes_left} minutes"
                    await self._send_vote_reminder(
                        f"⏰ Rappel — il reste environ **{time_str}** pour voter."
                    )
                    await self._remind_non_voters()

            if self.game_manager.phase != GamePhase.VOTE:
                return

            remaining = (vote_end - datetime.now()).total_seconds()
            if remaining > 1800:
                await asyncio.sleep(remaining - 1800)

            if self.game_manager.phase != GamePhase.VOTE:
                return

            await self._send_vote_reminder("⏰ **Plus que 30 minutes pour voter !**")
            await self._remind_non_voters()

            remaining = (vote_end - datetime.now()).total_seconds()
            if remaining > 300:
                await asyncio.sleep(remaining - 300)

            if self.game_manager.phase != GamePhase.VOTE:
                return

            await self._send_vote_reminder("⏰ **Dernières 5 minutes pour voter !** 🚨")
            await self._remind_non_voters()

        except asyncio.CancelledError:
            logger.debug("Vote reminders annulés")
        except Exception as e:
            logger.error(f"Erreur dans les rappels de vote: {e}")

    async def _send_vote_reminder(self: 'WerewolfBot', header_message: str):
        """Envoie un rappel de vote dans le village avec le resume actuel."""
        summary = self.game_manager.vote_manager.get_vote_summary()
        message = f"{header_message}\n\n📊 {summary}"
        await self.room_manager.send_to_village(message)

    async def _remind_non_voters(self: 'WerewolfBot'):
        """Envoie un DM aux joueurs vivants qui n'ont pas encore vote."""
        living = self.game_manager.get_living_players()
        voters = set(self.game_manager.vote_manager.votes.keys())

        for player in living:
            if player.user_id not in voters and player.can_vote:
                await self.client.send_dm(
                    player.user_id,
                    "⏰ **Rappel :** Vous n'avez pas encore voté !\n"
                    f"Utilisez `{self.command_prefix}vote {{pseudo}}` dans le salon du village."
                )
