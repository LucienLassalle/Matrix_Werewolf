"""Mixin : gestion des transitions de phase (nuit → jour → vote → nuit).

Regroupe les callbacks du scheduler et leurs helpers directs
(résolution de nuit, vote, annonce de victoire, rappels, etc.).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from models.enums import GamePhase, Team, RoleType
from matrix_bot.scheduler import day_name_fr

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class PhaseHandlersMixin:
    """Callbacks de phase et helpers associés — mixé dans WerewolfBot."""

    # ── Nuit ──────────────────────────────────────────────────────────

    async def _on_night_start(self: WerewolfBot, phase: GamePhase):
        """Appelé au début de chaque nuit.

        Selon la phase actuelle :
        - VOTE → résout le vote du village (et l'élection du maire si applicable),
          puis démarre la nuit (end_vote_phase() appelle _start_night() en interne).
        - DAY (ou autre) → démarre la nuit directement via begin_night()
          (cas de la première nuit, ou reprise après un état inattendu).
        """
        logger.info("🌙 Début de la nuit")

        # ── 1. Résoudre le vote du village (VOTE → NIGHT) ──
        if self.game_manager.phase == GamePhase.VOTE:
            # Annuler les rappels de vote
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

                # Annoncer les morts d'amoureux
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

            # Annoncer le résultat de l'élection du maire (si elle était ouverte)
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

            # Envoyer les DM de mort
            if eliminated and self.notification_manager:
                await self.notification_manager.send_death_notification(
                    eliminated.user_id, eliminated.role
                )
                for dead in all_deaths:
                    if dead != eliminated:
                        await self.notification_manager.send_death_notification(
                            dead.user_id, dead.role
                        )

            # Vérifier conversion Enfant Sauvage (le mentor a peut-être été éliminé)
            await self._check_enfant_sauvage_conversion()

            # Vérifier victoire après le vote
            if vote_result.get("winner"):
                await self._announce_victory(vote_result["winner"])
                self.scheduler.stop()
                return
            else:
                # Ajouter les morts au cimetière (Sauf si la partie est terminé)
                if eliminated:
                    await self.room_manager.add_to_dead(eliminated.user_id)
                if all_deaths:
                    for dead in all_deaths:
                        if dead != eliminated:
                            await self.room_manager.add_to_dead(dead.user_id)

            # Vérifier succession de maire
            await self._check_mayor_succession()

            # Vérifier si un Chasseur éliminé par vote doit tirer
            if self.game_manager.phase != GamePhase.ENDED:
                await self._check_and_start_chasseur_timeouts()
        else:
            # ── Pas de vote à résoudre (première nuit ou état inattendu) ──
            result = self.game_manager.begin_night()
            if result.get("winner"):
                await self._announce_victory(result["winner"])
                self.scheduler.stop()
                return

        # ── 2. Phase NIGHT déjà configurée par end_vote_phase / begin_night ──

        # Calculer la deadline des loups pour l'affichage
        wolf_deadline = self.scheduler.wolf_vote_deadline

        await self.room_manager.send_to_village(
            "🌙 **La nuit tombe sur le village...**\n\n"
            "Tout le monde s'endort. Les rôles nocturnes peuvent agir.\n"
            "Les loups-garous se réveillent pour choisir leur victime.\n\n"
            f"⏰ Les loups ont jusqu'à **{wolf_deadline.strftime('%Hh%M')}** pour voter."
        )

        # Informer les loups de leur deadline dans le salon des loups
        if self.room_manager.wolves_room:
            await self.client.send_message(
                self.room_manager.wolves_room,
                f"🌙 **C'est la nuit !** Votez pour choisir votre victime.\n\n"
                f"⏰ **Deadline : {wolf_deadline.strftime('%Hh%M')}** — "
                f"Passé cette heure, le vote sera verrouillé automatiquement.",
                formatted=True
            )

        # Lancer le timer de deadline des loups
        # Annuler un éventuel timer précédent
        if self._wolf_deadline_task and not self._wolf_deadline_task.done():
            self._wolf_deadline_task.cancel()
        self._wolf_deadline_task = asyncio.create_task(self._wolf_vote_deadline_timer())

        # Rappeler les actions nocturnes
        for player in self.game_manager.players.values():
            if player.is_alive:
                await self.notification_manager.send_night_reminder(
                    player.user_id,
                    player.role
                )

        # Vérifier si un Loup Voyant a rejoint la meute (auto-conversion dernier loup)
        await self._check_loup_voyant_room()

    # ── Deadline vote des loups ───────────────────────────────────────

    async def _wolf_vote_deadline_timer(self: WerewolfBot):
        """Attend jusqu'à la deadline du vote des loups puis verrouille.

        La deadline est calculée comme ``day_start - sorciere_min_hours``
        (par défaut 3h avant le lever du jour).  Si les loups ont déjà
        tous voté (``_wolf_votes_locked``), le timer n'a rien à faire.
        """
        from datetime import datetime as dt, timedelta

        deadline_time = self.scheduler.wolf_vote_deadline
        now = dt.now()
        target = dt.combine(now.date(), deadline_time)
        # Si la deadline est déjà passée aujourd'hui, c'est demain
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

        # Si les loups ont déjà voté, rien à faire
        if self._wolf_votes_locked:
            logger.info("Deadline loups atteinte, mais les votes étaient déjà verrouillés")
            return

        logger.info("⏰ Deadline loups atteinte — verrouillage automatique du vote")

        # Verrouiller les votes des loups
        self._wolf_votes_locked = True

        # Informer les loups dans leur salon
        if self.room_manager.wolves_room:
            target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
            if target:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    f"⏰ **Temps écoulé !** Le vote est verrouillé.\n"
                    f"La meute dévorera **{target.display_name}** cette nuit.",
                    formatted=True
                )
            else:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    "⏰ **Temps écoulé !** Aucun vote enregistré — "
                    "la meute ne dévore personne cette nuit.",
                    formatted=True
                )

        # Notifier la Sorcière de la cible des loups
        await self._notify_sorciere_wolf_target()

    # ── Jour ──────────────────────────────────────────────────────────

    async def _on_day_start(self: WerewolfBot, phase: GamePhase):
        """Appelé au début de chaque jour."""
        logger.info("☀️ Début du jour")

        # Annuler le timer deadline loups (la nuit est finie)
        if self._wolf_deadline_task and not self._wolf_deadline_task.done():
            self._wolf_deadline_task.cancel()

        # Garde-fou : si aucune nuit n'a eu lieu, rien à résoudre
        if self.game_manager.night_count < 1:
            logger.info("Pas de nuit à résoudre (première nuit pas encore jouée) — transition ignorée")
            return

        # Notifier la Sorcière de la cible des loups si elle n'a pas été notifiée
        # (cas où tous les loups n'ont pas voté — on notifie quand même avant résolution)
        if not self._sorciere_notified:
            await self._notify_sorciere_wolf_target()

        self.game_manager.set_phase(GamePhase.NIGHT)  # Remettre en NIGHT pour resolve_night

        # Créer le salon du couple AVANT la résolution (safety net)
        # pour ne pas perdre l'info si un amoureux meurt cette nuit
        await self._create_couple_room_if_needed()

        # Résolution de la nuit
        results = self.game_manager.resolve_night()

        # Gérer la conversion Loup Noir
        if results.get('converted'):
            await self._handle_conversion(results['converted'])

        # Tracer les sauvetages du Garde dans le journal
        if results.get('saved'):
            for saved_id in results['saved']:
                saved_player = self.game_manager.get_player(saved_id)
                if saved_player:
                    self._game_events.append(
                        f"Nuit {self.game_manager.night_count} — 🛡️ **{saved_player.display_name}** "
                        f"sauvé par la protection du Garde"
                    )

        # Vérifier conversion Enfant Sauvage (son mentor est peut-être mort cette nuit)
        await self._check_enfant_sauvage_conversion()

        # Annoncer les morts
        message = "☀️ **Le jour se lève sur le village...**\n\n"

        if results['deaths']:
            message += "💀 Cette nuit, les victimes sont:\n"
            for player_id in results['deaths']:
                player = self.game_manager.get_player(player_id)
                if player:
                    message += f"• **{player.display_name}** — **{player.role.name}**\n"
                    self._game_events.append(
                        f"Nuit {self.game_manager.night_count} — 💀 **{player.display_name}** "
                        f"tué durant la nuit ({player.role.name})"
                    )
                    # Ajouter au cimetière
                    await self.room_manager.add_to_dead(player_id)
        else:
            message += "🎉 Personne n'est mort cette nuit !\n"

        # Montreur d'ours
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.MONTREUR_OURS):
                if player.role.check_for_wolves(self.game_manager):
                    message += "\n🐻 **L'ours du montreur d'ours grogne !** Un loup est assis à côté de lui...\n"

        message += f"\n💬 Les villageois peuvent discuter jusqu'à {self._vote_hour}h00."

        await self.room_manager.send_to_village(message)

        # Envoyer les DM de mort
        if results['deaths'] and self.notification_manager:
            for player_id in results['deaths']:
                player = self.game_manager.get_player(player_id)
                if player:
                    await self.notification_manager.send_death_notification(
                        player.user_id, player.role
                    )

        # Réinitialiser le flag sorcière
        self._sorciere_notified = False
        self._wolf_votes_locked = False

        # Vérifier victoire
        if results.get('winner'):
            await self._announce_victory(results['winner'])
            self.scheduler.stop()
        else:
            await self._check_victory()

        # Vérifier succession de maire (si le jeu n'est pas terminé)
        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_mayor_succession()

        # Vérifier si un Chasseur mort cette nuit doit tirer (lancer le timeout)
        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_and_start_chasseur_timeouts()

    async def _handle_conversion(self: WerewolfBot, converted_user_id: str):
        """Gère l'ajout d'un joueur converti au salon des loups."""
        player = self.game_manager.get_player(converted_user_id)
        if not player:
            return

        logger.info(f"🐺 {player.display_name} a été converti en loup-garou par le Loup Noir")
        self._game_events.append(
            f"Nuit {self.game_manager.night_count} — 🐺 **{player.display_name}** "
            f"converti en Loup-Garou par le Loup Noir"
        )

        # Ajouter au salon des loups
        await self._add_to_wolf_room(
            player,
            "🐺 **Vous avez été infecté par le Loup Noir !**\n\n"
            "Vous êtes désormais un **Loup-Garou**. Vous rejoignez la meute.\n"
            "Votez avec les loups chaque nuit dans le salon des loups."
        )

    async def _notify_sorciere_wolf_target(self: WerewolfBot):
        """Notifie la Sorcière de la cible des loups (appelé après le vote des loups).

        La Sorcière doit toujours recevoir cette information, même si le Garde
        protège la cible. Elle ne sait pas ce que fait le Garde.
        """
        if self._sorciere_notified:
            return

        # Trouver la sorcière vivante
        sorciere = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.SORCIERE):
                sorciere = player
                break

        if not sorciere:
            return

        # Récupérer la cible des loups depuis le vote manager
        wolf_target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
        if not wolf_target:
            await self.client.send_dm(
                sorciere.user_id,
                "🌙 **Les loups n'ont pas choisi de victime cette nuit.**\n\n"
                "Vous pouvez tout de même utiliser votre potion de mort si vous le souhaitez.\n"
                f"• `{self.command_prefix}sorciere-tue {{pseudo}}` — Empoisonner quelqu'un"
            )
        else:
            msg = (
                f"🌙 **Les loups ont choisi de dévorer {wolf_target.display_name} cette nuit.**\n\n"
            )
            if sorciere.role.has_life_potion:
                msg += f"• `{self.command_prefix}sorciere-sauve {wolf_target.pseudo}` — Utiliser votre potion de vie pour le/la sauver\n"
            else:
                msg += "• (Potion de vie déjà utilisée)\n"

            if sorciere.role.has_death_potion:
                msg += f"• `{self.command_prefix}sorciere-tue {{pseudo}}` — Utiliser votre potion de mort\n"
            else:
                msg += "• (Potion de mort déjà utilisée)\n"

            msg += "\n💡 Vous pouvez utiliser les deux potions la même nuit."

            await self.client.send_dm(sorciere.user_id, msg)

        self._sorciere_notified = True

    # ── Vote ──────────────────────────────────────────────────────────

    async def _on_vote_start(self: WerewolfBot, phase: GamePhase):
        """Appelé au début de la phase de vote.

        Si day_start == vote_start (fusionnées), cette méthode résout aussi
        la nuit avant de démarrer le vote — sinon _on_day_start ne serait jamais
        appelée.
        """
        logger.info("🗳️ Début des votes")

        # Pas de vote avant la première nuit (ex: partie lancée à 12h, VOTE=19h)
        if self.game_manager.night_count < 1:
            logger.info("Pas de vote avant la première nuit — transition ignorée")
            return

        # Si DAY et VOTE sont fusionnés, résoudre la nuit d'abord
        if self._day_hour == self._vote_hour:
            logger.info("DAY_START_HOUR == VOTE_START_HOUR — résolution de la nuit avant le vote")
            await self._on_day_start(phase)
            # Vérifier si la partie est terminée après la résolution de la nuit
            if self.game_manager.phase == GamePhase.ENDED:
                return

        # start_vote_phase() reset les votes du village et met la phase à VOTE
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

        # Annoncer l'élection du maire si elle est ouverte
        if self.game_manager.can_vote_mayor():
            vote_msg += (
                f"\n\n👑 **Élection du maire** — Votez aussi pour un maire !\n"
                f"Utilisez `{self.command_prefix}vote-maire {{pseudo}}` pour voter."
            )

        await self.room_manager.send_to_village(vote_msg)

        # Planifier la notification du Mentaliste X heures avant la fin du vote (21h)
        asyncio.create_task(self._schedule_mentaliste_notification())

        # Planifier les rappels de vote
        self._last_vote_snapshot = {}
        if self._vote_reminder_task and not self._vote_reminder_task.done():
            self._vote_reminder_task.cancel()
        self._vote_reminder_task = asyncio.create_task(self._schedule_vote_reminders())

    # ── Élection du Maire ─────────────────────────────────────────────

    async def _check_mayor_election_progress(self: WerewolfBot):
        """Vérifie la progression du vote pour l'élection du maire.

        Annonce la progression dans le village après chaque vote.
        """
        if not self.game_manager.can_vote_mayor():
            return

        living = self.game_manager.get_living_players()
        voters = set(self.game_manager.vote_manager.mayor_votes_for.keys())
        total = len(living)
        voted = len([p for p in living if p.user_id in voters])

        # Résumé de la progression
        summary = self.game_manager.vote_manager.get_mayor_vote_summary()
        await self.room_manager.send_to_village(
            f"👑 **Élection du maire** — {voted}/{total} votes\n\n{summary}"
        )

    # ── Mentaliste ────────────────────────────────────────────────────

    async def _schedule_mentaliste_notification(self: WerewolfBot):
        """Envoie la prédiction du Mentaliste X heures avant la fin du vote."""
        from datetime import datetime, timedelta

        # Fin du vote = début de la nuit
        vote_end = datetime.combine(datetime.now().date(), self.scheduler.night_start)
        if vote_end < datetime.now():
            vote_end += timedelta(days=1)

        # Moment de notification = vote_end - MENTALISTE_ADVANCE_HOURS
        notify_time = vote_end - timedelta(hours=self.mentaliste_advance_hours)
        wait_seconds = (notify_time - datetime.now()).total_seconds()

        if wait_seconds > 0:
            logger.info(
                f"Mentaliste: notification dans {wait_seconds:.0f}s "
                f"({self.mentaliste_advance_hours}h avant fin du vote)"
            )
            await asyncio.sleep(wait_seconds)

        # Vérifier qu'on est toujours en phase de vote
        if self.game_manager.phase != GamePhase.VOTE:
            return

        await self._notify_mentaliste()

    async def _notify_mentaliste(self: WerewolfBot):
        """Envoie la prédiction du Mentaliste sur l'issue du vote en cours."""
        # Trouver le mentaliste vivant
        mentaliste = None
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.MENTALISTE):
                mentaliste = player
                break

        if not mentaliste:
            return

        # Récupérer le joueur le plus voté actuellement
        most_voted = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=False)

        if not most_voted:
            await self.client.send_dm(
                mentaliste.user_id,
                "🔮 **Intuition du Mentaliste**\n\n"
                "Personne n'a encore reçu de votes... Impossible de prédire l'issue."
            )
            return

        # Prédire l'issue
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
            f"💡 Cette information est basée sur les votes actuels — le résultat peut encore changer."
        )
        # Fournir la liste complète des votes au Mentaliste
        vote_summary = self.game_manager.vote_manager.get_vote_summary()
        await self.client.send_dm(
            mentaliste.user_id,
            f"📊 Joueur le plus voté actuellement : **{most_voted.display_name}**\n\n"
            f"**Résumé des votes :**\n{vote_summary}"
        )

        logger.info(f"Mentaliste notifié: issue du vote = {outcome}")

    # ── Rappels de vote ───────────────────────────────────────────────

    async def _schedule_vote_reminders(self: WerewolfBot):
        """Planifie les rappels de vote pendant la phase de vote.

        Logique :
        - Rappel toutes les heures (si les votes ont changé)
        - Rappel 30 minutes avant la fin
        - Rappel final 5 minutes avant la fin
        - DM aux joueurs qui n'ont pas encore voté à chaque rappel
        """
        from datetime import datetime, timedelta

        try:
            # Calculer la fin du vote (début de la nuit)
            vote_end = datetime.combine(datetime.now().date(), self.scheduler.night_start)
            if vote_end < datetime.now():
                vote_end += timedelta(days=1)

            # Phase 1 : Rappels toutes les heures (si votes ont changé)
            while True:
                if self.game_manager.phase != GamePhase.VOTE:
                    return

                remaining = (vote_end - datetime.now()).total_seconds()

                # Si on est dans les 30 dernières minutes, passer à la phase 2
                if remaining <= 1800:  # 30 minutes
                    break

                # Attendre 1 heure (ou jusqu'à 30 min avant la fin)
                wait = min(3600, remaining - 1800)
                await asyncio.sleep(wait)

                if self.game_manager.phase != GamePhase.VOTE:
                    return

                # Vérifier si les votes ont changé
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

            # Phase 2 : Rappel à 30 minutes avant la fin
            if self.game_manager.phase != GamePhase.VOTE:
                return

            remaining = (vote_end - datetime.now()).total_seconds()
            if remaining > 1800:
                await asyncio.sleep(remaining - 1800)

            if self.game_manager.phase != GamePhase.VOTE:
                return

            await self._send_vote_reminder("⏰ **Plus que 30 minutes pour voter !**")
            await self._remind_non_voters()

            # Phase 3 : Rappel final à 5 minutes avant la fin
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

    async def _send_vote_reminder(self: WerewolfBot, header_message: str):
        """Envoie un rappel de vote dans le village avec le résumé actuel."""
        summary = self.game_manager.vote_manager.get_vote_summary()
        message = f"{header_message}\n\n📊 {summary}"
        await self.room_manager.send_to_village(message)

    async def _remind_non_voters(self: WerewolfBot):
        """Envoie un DM aux joueurs vivants qui n'ont pas encore voté."""
        living = self.game_manager.get_living_players()
        voters = set(self.game_manager.vote_manager.votes.keys())

        for player in living:
            if player.user_id not in voters and player.can_vote:
                await self.client.send_dm(
                    player.user_id,
                    "⏰ **Rappel :** Vous n'avez pas encore voté !\n"
                    f"Utilisez `{self.command_prefix}vote {{pseudo}}` dans le salon du village."
                )

    # ── Fin de partie ─────────────────────────────────────────────────

    async def _end_game(self: WerewolfBot):
        """Termine la partie et nettoie les salons."""
        logger.info("Fin de la partie")

        # Annuler le timeout de succession du maire
        if self._mayor_succession_task and not self._mayor_succession_task.done():
            self._mayor_succession_task.cancel()

        # Annuler les rappels de vote
        if self._vote_reminder_task and not self._vote_reminder_task.done():
            self._vote_reminder_task.cancel()

        # S'assurer que la phase est bien ENDED
        if self.game_manager.phase != GamePhase.ENDED:
            self.game_manager.set_phase(GamePhase.ENDED)

        # Supprimer tous les salons de jeu (village, loups, couple, cimetière)
        await self.room_manager.cleanup_rooms()

        # Réouvrir les inscriptions dans le lobby
        self._accepting_registrations = True

        # Message dans le lobby (inscriptions)
        jour = day_name_fr(self._game_start_day)
        await self.client.send_message(
            self.lobby_room_id,
            "Les salons de jeu ont été supprimés.\n"
            f"Tapez `{self.command_prefix}inscription` pour participer à la prochaine partie "
            f"**{jour} à {self._game_start_hour}h**.",
            formatted=True
        )

    async def _check_victory(self: WerewolfBot):
        """Vérifie si une équipe a gagné."""
        winner = self.game_manager.check_victory()

        if winner:
            await self._announce_victory(winner)
            self.scheduler.stop()

    async def _announce_victory(self: WerewolfBot, winner: Team):
        """Annonce la victoire avec statistiques détaillées."""
        # Sauvegarder les résultats de la partie dans la BDD
        # (leaderboard, stats joueurs, historique)
        self.game_manager.end_game(winner)

        team_names = {
            Team.GENTIL: "🏘️ **Les Villageois**",
            Team.MECHANT: "🐺 **Les Loups-Garous**",
        }

        # Loup Blanc solo ou égalité
        if winner == Team.NEUTRE:
            living = self.game_manager.get_living_players()
            if living and living[0].role and living[0].role.role_type == RoleType.LOUP_BLANC:
                team_display = "🐺⚪ **Le Loup Blanc**"
            else:
                team_display = "☠️ **Personne** (égalité)"
        elif winner == Team.COUPLE:
            cupidon = self.game_manager.get_cupidon_player()
            living = self.game_manager.get_living_players()
            lovers = [p for p in living if p.lover and p.lover.is_alive]
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

        # Révéler tous les rôles
        message += "📋 **Rôles:**\n"
        for player in self.game_manager.players.values():
            status = "💀" if not player.is_alive else "✅"
            extras = []
            if player.is_mayor:
                extras.append("👑 Maire")
            if player.lover:
                extras.append(f"💕 couple avec {player.lover.display_name}")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            message += f"{status} **{player.display_name}**: {player.role.name}{extra_str}\n"

        # Statistiques détaillées
        message += "\n📊 **Statistiques de la partie:**\n"
        message += f"• Durée : {self.game_manager.day_count} jour{'s' if self.game_manager.day_count > 1 else ''}, "
        message += f"{self.game_manager.night_count} nuit{'s' if self.game_manager.night_count > 1 else ''}\n"

        living = self.game_manager.get_living_players()
        dead = [p for p in self.game_manager.players.values() if not p.is_alive]
        message += f"• Survivants : {len(living)} / {len(self.game_manager.players)}\n"

        # Résumé des événements marquants (journal groupé par phase)
        if self._game_events:
            message += "\n📜 **Chronologie de la partie:**\n"

            current_phase = None
            for event in self._game_events:
                # Extraire le préfixe de phase ("Nuit N" ou "Jour N")
                phase_label = None
                for prefix in ("Nuit ", "Jour "):
                    if event.startswith(prefix):
                        # Extraire "Nuit N" ou "Jour N" (jusqu'au tiret)
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
                    # Événements sans phase (chasseur, maire succession…)
                    message += f"  • {event}\n"

        await self.client.send_message(
            self.lobby_room_id,
            message,
            formatted=True
        )
