"""Gestion des callbacks de nuit."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class PhaseNightHandlersMixin:
    """Callbacks de nuit et helpers associes."""

    async def _on_night_start(self: 'WerewolfBot', phase: GamePhase):
        """Appelé au début de chaque nuit."""
        logger.info("🌙 Début de la nuit")

        if self.game_manager.phase == GamePhase.VOTE:
            if self._vote_reminder_task and not self._vote_reminder_task.done():
                self._vote_reminder_task.cancel()

            vote_result = self.game_manager.end_vote_phase()

            eliminated = vote_result.get("eliminated")
            all_deaths = vote_result.get("all_deaths", [])
            if eliminated:
                self._game_events.append(
                    f"Jour {self.game_manager.day_count} — 🗳️ **{eliminated.display_name}** "
                    f"éliminé par le vote ({eliminated.role.name})"
                )
                await self.room_manager.send_to_village(
                    f"🗳️ **Résultat du vote :** **{eliminated.display_name}** "
                    f"a été éliminé par le village !\n"
                    f"Son rôle était : **{eliminated.role.name}**"
                )

                for dead in all_deaths:
                    if dead != eliminated:
                        self._game_events.append(
                            f"Jour {self.game_manager.day_count} — 💔 **{dead.display_name}** "
                            f"meurt de chagrin ({dead.role.name})"
                        )
                        await self.room_manager.send_to_village(
                            f"💔 **{dead.display_name}** meurt de chagrin (amoureux/se) !\n"
                            f"Son rôle était : **{dead.role.name}**"
                        )
            elif vote_result.get("pardoned_idiot"):
                idiot = vote_result["pardoned_idiot"]
                await self.room_manager.send_to_village(
                    f"🗳️ **Résultat du vote :** **{idiot.display_name}** a été désigné... "
                    f"mais c'est **l'Idiot du village** ! Il est gracié mais perd son droit de vote."
                )
            else:
                await self.room_manager.send_to_village(
                    "🗳️ **Résultat du vote :** Pas d'élimination "
                    "(égalité ou aucun vote)."
                )

            mayor_result = vote_result.get("mayor_result")
            if mayor_result:
                elected = mayor_result.get("elected")
                if elected:
                    await self.room_manager.send_to_village(
                        f"👑 **{elected.display_name}** est élu **maire** du village !\n\n"
                        f"Son vote comptera **double** et il départagera les égalités."
                    )
                    await self.client.send_dm(elected.user_id, self._NEW_MAYOR_DM)
                    self._game_events.append(
                        f"Jour {self.game_manager.day_count} — 👑 **{elected.display_name}** élu maire"
                    )
                else:
                    await self.room_manager.send_to_village(
                        "👑 Aucun maire n'a été élu (aucun vote ou égalité).\n"
                        "Le village n'a pas de maire pour le moment."
                    )

            if eliminated and self.notification_manager:
                await self.notification_manager.send_death_notification(
                    eliminated.user_id, eliminated.role
                )
                for dead in all_deaths:
                    if dead != eliminated:
                        await self.notification_manager.send_death_notification(
                            dead.user_id, dead.role
                        )

            await self._check_enfant_sauvage_conversion()

            if vote_result.get("winner"):
                await self._announce_victory(vote_result["winner"])
                self.scheduler.stop()
                return
            else:
                if eliminated:
                    await self.room_manager.add_to_dead(eliminated.user_id)
                if all_deaths:
                    for dead in all_deaths:
                        if dead != eliminated:
                            await self.room_manager.add_to_dead(dead.user_id)

            if eliminated or all_deaths:
                await self._update_seating_message()

            await self._check_mayor_succession()

            if self.game_manager.phase != GamePhase.ENDED:
                await self._check_and_start_chasseur_timeouts()
        else:
            result = self.game_manager.begin_night()
            if result.get("winner"):
                await self._announce_victory(result["winner"])
                self.scheduler.stop()
                return

        wolf_deadline = self.scheduler.wolf_vote_deadline

        await self.room_manager.send_to_village(
            "🌙 **La nuit tombe sur le village...**\n\n"
            "Tout le monde s'endort. Les rôles nocturnes peuvent agir.\n"
            "Les loups-garous se réveillent pour choisir leur victime.\n\n"
            f"⏰ Les loups ont jusqu'à **{wolf_deadline.strftime('%Hh%M')}** pour voter."
        )

        if self.room_manager.wolves_room:
            await self.client.send_message(
                self.room_manager.wolves_room,
                f"🌙 **C'est la nuit !** Votez pour choisir votre victime.\n\n"
                f"⏰ **Deadline : {wolf_deadline.strftime('%Hh%M')}** — "
                f"Passé cette heure, le vote sera verrouillé automatiquement.",
                formatted=True,
            )

        if self._wolf_deadline_task and not self._wolf_deadline_task.done():
            self._wolf_deadline_task.cancel()
        self._wolf_deadline_task = asyncio.create_task(self._wolf_vote_deadline_timer())

        await self._apply_jailer_night()

        for player in self.game_manager.players.values():
            if player.is_alive:
                if player.is_jailed:
                    continue
                await self.notification_manager.send_night_reminder(
                    player.user_id,
                    player.role,
                )

        await self._check_loup_voyant_room()

    async def _wolf_vote_deadline_timer(self: 'WerewolfBot'):
        """Attend jusqu'a la deadline du vote des loups puis verrouille."""
        from datetime import datetime as dt, timedelta

        deadline_time = self.scheduler.wolf_vote_deadline
        now = dt.now()
        target = dt.combine(now.date(), deadline_time)
        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info(
            "⏳ Deadline loups dans %.0f secondes (%.1fh) — %s",
            wait_seconds, wait_seconds / 3600,
            target.strftime('%Hh%M'),
        )

        try:
            await asyncio.sleep(wait_seconds)
        except asyncio.CancelledError:
            logger.debug("Timer deadline loups annulé")
            return

        if self._wolf_votes_locked:
            logger.info("Deadline loups atteinte, mais les votes etaient deja verrouilles")
            return

        logger.info("⏰ Deadline loups atteinte — verrouillage automatique du vote")

        self._wolf_votes_locked = True

        if self.room_manager.wolves_room:
            target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
            if target:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    f"⏰ **Temps écoulé !** Le vote est verrouillé.\n"
                    f"La meute dévorera **{target.display_name}** cette nuit.",
                    formatted=True,
                )
            else:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    "⏰ **Temps écoulé !** Aucun vote enregistré — "
                    "la meute ne dévore personne cette nuit.",
                    formatted=True,
                )

        await self._notify_sorciere_wolf_target()

    async def _handle_conversion(self: 'WerewolfBot', converted_user_id: str):
        """Gere l'ajout d'un joueur converti au salon des loups."""
        player = self.game_manager.get_player(converted_user_id)
        if not player:
            return

        logger.info(
            "🐺 %s a été converti en loup-garou par le Loup Noir",
            player.display_name,
        )
        self._game_events.append(
            f"Nuit {self.game_manager.night_count} — 🐺 **{player.display_name}** "
            f"converti en Loup-Garou par le Loup Noir"
        )

        await self._add_to_wolf_room(
            player,
            "🐺 **Vous avez été infecté par le Loup Noir !**\n\n"
            "Vous êtes désormais un **Loup-Garou**. Vous rejoignez la meute.\n"
            "Votez avec les loups chaque nuit dans le salon des loups.",
        )

    async def _notify_sorciere_wolf_target(self: 'WerewolfBot'):
        """Notifie la Sorciere de la cible des loups."""
        if self._sorciere_notified:
            return

        sorciere = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.SORCIERE):
                sorciere = player
                break

        if not sorciere:
            return

        wolf_target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
        if not wolf_target:
            await self.client.send_dm(
                sorciere.user_id,
                "🌙 **Les loups n'ont pas choisi de victime cette nuit.**\n\n"
                "Vous pouvez tout de même utiliser votre potion de mort si vous le souhaitez.\n"
                f"• `{self.command_prefix}sorciere-tue {{pseudo}}` — Empoisonner quelqu'un",
            )
        else:
            msg = (
                f"🌙 **Les loups ont choisi de dévorer {wolf_target.display_name} cette nuit.**\n\n"
            )
            if sorciere.role.has_life_potion:
                msg += (
                    f"• `{self.command_prefix}sorciere-sauve {wolf_target.pseudo}` "
                    "— Utiliser votre potion de vie pour le/la sauver\n"
                )
            else:
                msg += "• (Potion de vie déjà utilisée)\n"

            if sorciere.role.has_death_potion:
                msg += (
                    f"• `{self.command_prefix}sorciere-tue {{pseudo}}` "
                    "— Utiliser votre potion de mort\n"
                )
            else:
                msg += "• (Potion de mort déjà utilisée)\n"

            msg += "\n💡 Vous pouvez utiliser les deux potions la même nuit."

            await self.client.send_dm(sorciere.user_id, msg)

        self._sorciere_notified = True
