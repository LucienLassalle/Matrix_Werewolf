"""Mixin : gestion des événements liés aux rôles spéciaux.

Regroupe les effets Matrix post-mort, les changements de salon
(enfant sauvage, voleur, loup voyant, loup noir), les timeouts
(chasseur, succession de maire) et le traitement des morts
instantanées (commandes tuer / dictateur).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict

from models.enums import GamePhase, RoleType

if TYPE_CHECKING:
    from models.player import Player
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class RoleHandlersMixin:
    """Événements liés aux rôles spéciaux — mixé dans WerewolfBot."""

    # Message DM envoyé au nouveau maire (dédupliqué)
    _NEW_MAYOR_DM = (
        "👑 **Vous êtes le nouveau maire !**\n\n"
        "Votre vote compte désormais double et vous départagez les égalités."
    )

    # ── Helper : ajout au salon des loups ─────────────────────────────

    async def _add_to_wolf_room(self: WerewolfBot, player, dm_message: str):
        """Invite un joueur dans le salon des loups, l'informe en DM et annonce à la meute.

        Centralise le pattern invite + DM + annonce pour éviter la duplication
        (Enfant Sauvage, Voleur, Loup Voyant, Loup Noir).
        Ne fait rien si le salon des loups n'existe pas ou si le joueur y est déjà.
        """
        if not self.room_manager.wolves_room:
            return
        if player.user_id in self._wolves_in_room:
            return

        try:
            await self.client.invite_user(self.room_manager.wolves_room, player.user_id)
            self._wolves_in_room.add(player.user_id)

            await self.client.send_dm(player.user_id, dm_message)

            await self.client.send_message(
                self.room_manager.wolves_room,
                f"🐺 **{player.display_name}** rejoint la meute !",
                formatted=True,
            )
        except Exception as e:
            logger.error(f"Erreur ajout de {player.display_name} au salon des loups: {e}")

    # ── Enfant Sauvage ────────────────────────────────────────────────

    async def _check_enfant_sauvage_conversion(self: WerewolfBot):
        """Détecte si un Enfant Sauvage a été converti en loup et gère les effets Matrix.

        Après la mort d'un joueur, l'Enfant Sauvage dont le mentor est mort
        est automatiquement converti en Loup-Garou par on_player_death().
        Cette méthode détecte la conversion et :
        - Invite le joueur dans le salon des loups
        - Lui envoie un DM d'information
        - Informe la meute
        """
        for player in self.game_manager.players.values():
            if (player.is_alive
                    and player.mentor is not None
                    and player.role
                    and player.role.role_type == RoleType.LOUP_GAROU
                    and player.user_id not in self._wolves_in_room):

                logger.info(f"🐺 {player.display_name} (ex-Enfant Sauvage) devient loup-garou !")

                self._game_events.append(
                    f"Nuit {self.game_manager.night_count} — 🧒🐺 "
                    f"**{player.display_name}** (Enfant Sauvage) "
                    f"converti en Loup-Garou (mentor mort)"
                )

                await self._add_to_wolf_room(
                    player,
                    "🐺 **Votre mentor est mort !**\n\n"
                    "Votre instinct sauvage prend le dessus... "
                    "Vous êtes désormais un **Loup-Garou** !\n"
                    "Rejoignez la meute dans le salon des loups et votez chaque nuit."
                )

    # ── Vote des loups (Sorcière) ─────────────────────────────────────

    async def _check_wolf_vote_complete(self: WerewolfBot):
        """Vérifie si tous les loups ont voté et notifie la Sorcière le cas échéant.

        Quand tous les loups ont voté :
        - Les votes sont verrouillés (plus de changement possible)
        - La Sorcière est notifiée de la cible (gain de temps)
        """
        # Compter les loups vivants
        living_wolves = [
            p for p in self.game_manager.players.values()
            if p.is_alive and p.role and p.role.can_vote_with_wolves()
        ]

        # Vérifier si tous ont voté
        wolf_votes = self.game_manager.vote_manager.wolf_votes
        wolves_who_voted = [w for w in living_wolves if w.user_id in wolf_votes]

        if len(wolves_who_voted) >= len(living_wolves) and living_wolves:
            # Verrouiller les votes
            self._wolf_votes_locked = True

            # Notifier les loups que le vote est acquis
            target = self.game_manager.vote_manager.get_most_voted(is_wolf_vote=True)
            if target and self.room_manager.wolves_room:
                await self.client.send_message(
                    self.room_manager.wolves_room,
                    f"🔒 **Vote verrouillé !** La meute a décidé de dévorer **{target.display_name}** cette nuit.",
                    formatted=True
                )

            # Notifier la Sorcière
            await self._notify_sorciere_wolf_target()

    # ── Voleur ────────────────────────────────────────────────────────

    async def _handle_voleur_swap_rooms(self: WerewolfBot, voleur: Player, swapped: Player):
        """Gère les salons loups après un échange Voleur ↔ joueur.

        Si le Voleur a volé un rôle loup, il doit être ajouté au salon des loups.
        Si l'ex-loup est devenu Voleur, il doit être retiré du salon des loups.
        """
        if not self.room_manager.wolves_room:
            return

        # Le Voleur (qui a maintenant le rôle de la cible) est-il un loup ?
        if voleur.role and voleur.role.can_vote_with_wolves():
            await self._add_to_wolf_room(
                voleur,
                "🐺 **Vous avez rejoint la meute !**\n\n"
                "Vous pouvez désormais communiquer et voter avec les loups "
                "dans le salon des loups."
            )

        # L'ex-loup (qui est maintenant Voleur) doit être muté dans le salon
        if swapped.user_id in self._wolves_in_room:
            try:
                await self.client.set_power_level(
                    self.room_manager.wolves_room, swapped.user_id, -1
                )
                self._wolves_in_room.discard(swapped.user_id)
            except Exception as e:
                logger.error(f"Erreur mute ex-loup du salon des loups: {e}")

    async def _check_voleur_new_role_rooms(self: WerewolfBot, player: Player):
        """Gère l'ajout au salon des loups si le Voleur a choisi un rôle loup via voleur-choisir.

        Appelé après voleur-choisir (tirage de 2 cartes puis choix).
        """
        if not self.room_manager.wolves_room:
            return

        if (player.role and player.role.can_vote_with_wolves()
                and player.user_id not in self._wolves_in_room):
            await self._add_to_wolf_room(
                player,
                "🐺 **Vous avez rejoint la meute !**\n\n"
                "En choisissant ce rôle, vous êtes maintenant un loup.\n"
                "Communiquez et votez avec les loups dans le salon des loups."
            )

    # ── Loup Voyant ───────────────────────────────────────────────────

    async def _check_loup_voyant_room(self: WerewolfBot):
        """Vérifie si un Loup Voyant a rejoint la meute et l'ajoute au salon des loups.

        Le Loup Voyant rejoint la meute quand :
        - Il utilise !lg (BECOME_WEREWOLF)
        - Il est le dernier loup vivant (auto-conversion dans on_night_start)
        """
        for player in self.game_manager.players.values():
            if (player.is_alive and player.role
                    and player.role.role_type == RoleType.LOUP_VOYANT
                    and hasattr(player.role, '_can_vote_with_pack')
                    and player.role._can_vote_with_pack
                    and player.user_id not in self._wolves_in_room):

                await self._add_to_wolf_room(
                    player,
                    "🐺 **Vous rejoignez la meute !**\n\n"
                    "Vous pouvez désormais communiquer et voter avec les loups "
                    "dans le salon des loups."
                )

    # ── Maire (succession) ────────────────────────────────────────────

    async def _check_mayor_succession(self: WerewolfBot):
        """Vérifie si une succession de maire est nécessaire et la lance."""
        if not self.game_manager._pending_mayor_succession:
            return

        dead_mayor = self.game_manager._pending_mayor_succession

        # Annoncer dans le village
        await self.room_manager.send_to_village(
            f"👑 **Le maire {dead_mayor.display_name} est mort !**\n"
            f"Il doit désigner son successeur parmi les vivants..."
        )

        # Calculer le timeout : temps jusqu'à la prochaine transition de phase
        remaining = self.scheduler.get_time_until_next_phase()
        if remaining is None:
            timeout_seconds = 300  # Fallback 5 minutes
        else:
            # Au minimum 60 secondes pour être fair
            timeout_seconds = max(60, remaining.total_seconds())

        minutes = int(timeout_seconds // 60)
        if minutes >= 60:
            hours = round(minutes / 60)
            time_str = f"{hours} heure{'s' if hours > 1 else ''}"
        else:
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''}"

        # DM au maire mort avec la liste des vivants
        living = self.game_manager.get_living_players()
        living_list = ", ".join(f"**{p.pseudo}**" for p in living)
        await self.client.send_dm(
            dead_mayor.user_id,
            f"👑 **Vous êtes mort.e en tant que maire.**\n\n"
            f"Désignez votre successeur avec `{self.command_prefix}maire {{pseudo}}`.\n\n"
            f"Joueurs vivants : {living_list}\n\n"
            f"⏰ Vous avez **{time_str}** pour choisir, sinon un successeur sera désigné au hasard."
        )

        # Lancer le timeout
        if self._mayor_succession_task and not self._mayor_succession_task.done():
            self._mayor_succession_task.cancel()
        self._mayor_succession_task = asyncio.create_task(
            self._mayor_succession_timeout(timeout_seconds)
        )

    # ── Geolier (prison) ───────────────────────────────────────────

    async def _apply_jailer_night(self: WerewolfBot):
        """Mute le prisonnier du geolier et envoie les instructions en DM."""
        jailer, prisoner = self.game_manager.get_jailer_and_prisoner()
        if not jailer or not prisoner or not prisoner.is_alive:
            self._jailed_user_id = None
            return

        if self._jailed_user_id == prisoner.user_id:
            return

        self._jailed_user_id = prisoner.user_id
        await self._jail_player(prisoner.user_id)

        await self.room_manager.send_to_village(
            f"🔒 **{prisoner.display_name}** a ete emprisonne par le Geolier, "
            "il ne pourra faire aucune action cette nuit."
        )

        await self.client.send_dm(
            jailer.user_id,
            "🔒 **Vous interrogez un prisonnier cette nuit.**\n\n"
            f"Prisonnier: **{prisoner.display_name}**\n\n"
            f"Pour lui parler, utilisez `{self.command_prefix}msg {{message}}`.\n"
            f"Si vous le jugez suspect, vous pouvez l'executer une fois avec `{self.command_prefix}geolier-tuer`."
        )

        await self.client.send_dm(
            prisoner.user_id,
            "🔒 **Vous etes emprisonne cette nuit.**\n\n"
            "Vous ne pouvez pas agir et vous etes isole.\n"
            f"Pour parler au geolier, utilisez `{self.command_prefix}msg {{message}}`."
        )

    async def _release_jailer_day(self: WerewolfBot):
        """Libere le prisonnier et retire le mute temporaire."""
        if not self._jailed_user_id:
            return

        user_id = self._jailed_user_id
        player = self.game_manager.get_player(user_id)
        if player and player.is_alive:
            await self._unjail_player(user_id)

        self._jailed_user_id = None

    async def _mayor_succession_timeout(self: WerewolfBot, timeout_seconds: float = 300):
        """Timeout pour la succession du maire (jusqu'à la prochaine phase)."""
        try:
            await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            return

        if not self.game_manager._pending_mayor_succession:
            return  # Déjà résolu

        if self.game_manager.phase == GamePhase.ENDED:
            return

        new_mayor = self.game_manager.auto_designate_mayor()
        if new_mayor:
            await self.room_manager.send_to_village(
                f"👑 **{new_mayor.display_name}** est désigné maire par défaut "
                f"(le maire sortant n'a pas choisi à temps)."
            )
            await self.client.send_dm(
                new_mayor.user_id,
                self._NEW_MAYOR_DM
            )

    # ── Chasseur (timeout tir) ────────────────────────────────────────

    async def _check_and_start_chasseur_timeouts(self: WerewolfBot):
        """Démarre un timeout pour chaque Chasseur mort qui peut encore tirer.

        Appelé après chaque lot de morts (résolution de nuit, vote, commandes
        instantanées) pour vérifier s'il y a un Chasseur mort non géré.
        Le Chasseur dispose du temps restant jusqu'à la prochaine transition
        de phase (= le reste de la phase courante).
        """
        for player in self.game_manager.players.values():
            if (player.role
                    and player.role.role_type == RoleType.CHASSEUR
                    and not player.is_alive
                    and player.role.can_shoot_now
                    and not player.role.has_shot
                    and player.user_id not in self._chasseur_timeout_tasks):

                # Calculer le timeout : temps jusqu'à la prochaine transition de phase
                remaining = self.scheduler.get_time_until_next_phase()
                if remaining is None:
                    timeout_seconds = 300  # Fallback 5 minutes
                else:
                    # Au minimum 60 secondes pour être fair
                    timeout_seconds = max(60, remaining.total_seconds())

                minutes = int(timeout_seconds // 60)
                if minutes >= 60:
                    hours = round(minutes / 60)
                    time_str = f"{hours} heure{'s' if hours > 1 else ''}"
                else:
                    time_str = f"{minutes} minute{'s' if minutes > 1 else ''}"
                living_players = self.game_manager.get_living_players()
                living_list = ", ".join(p.pseudo for p in living_players)

                await self.client.send_dm(
                    player.user_id,
                    f"💀 **Vous êtes mort.e !** Mais en tant que Chasseur, "
                    f"vous pouvez tirer une dernière balle.\n\n"
                    f"Utilisez `{self.command_prefix}tuer {{pseudo}}` pour viser quelqu'un.\n\n"
                    f"Joueurs vivants : {living_list}\n\n"
                    f"⏰ Vous avez **{time_str}** "
                    f"pour tirer, sinon votre tir sera perdu."
                )

                task = asyncio.create_task(
                    self._chasseur_timeout_expired(player, timeout_seconds)
                )
                self._chasseur_timeout_tasks[player.user_id] = task

                logger.info(
                    f"🔫 Chasseur {player.pseudo} a {minutes}min pour tirer "
                    f"(timeout={timeout_seconds:.0f}s)"
                )

    async def _chasseur_timeout_expired(self: WerewolfBot, player, timeout_seconds: float):
        """Timeout du Chasseur — son tir est perdu s'il n'a pas agi à temps."""
        try:
            await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            return

        # Vérifier que c'est toujours applicable
        if (not player.role
                or player.role.has_shot
                or not player.role.can_shoot_now):
            self._chasseur_timeout_tasks.pop(player.user_id, None)
            return

        if self.game_manager.phase == GamePhase.ENDED:
            self._chasseur_timeout_tasks.pop(player.user_id, None)
            return

        # Le Chasseur n'a pas tiré — perdre le tir
        player.role.has_shot = True
        player.role.can_shoot_now = False

        self._chasseur_timeout_tasks.pop(player.user_id, None)

        await self.client.send_dm(
            player.user_id,
            "⏰ **Temps écoulé !** Vous n'avez pas tiré à temps. "
            "Votre dernière balle est perdue."
        )

        await self.room_manager.send_to_village(
            f"🔫 Le Chasseur **{player.display_name}** n'a pas tiré à temps. "
            f"Sa dernière balle est perdue."
        )

        try:
            await self.room_manager.add_to_dead(player.user_id)
            logger.info("☠️ %s invité au cimetière (tir perdu)", player.user_id)
        except Exception as e:
            logger.error("Erreur invitation cimetière (tir perdu) pour %s: %s", player.user_id, e)

        logger.info(f"⏰ Chasseur {player.pseudo} — tir perdu (timeout)")

    def _cancel_chasseur_timeout(self: WerewolfBot, user_id: str):
        """Annule le timeout du Chasseur (appelé quand il tire avec succès)."""
        task = self._chasseur_timeout_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    # ── Morts instantanées (tuer / dictateur) ─────────────────────────

    async def _process_command_deaths(self: WerewolfBot, result: dict, command: str, actor_id: str):
        """Traite les effets Matrix des morts causées par des commandes instantanées.

        Appelé après la commande tuer (Chasseur) ou dictateur. Ces commandes tuent
        immédiatement via game.kill_player() (mute + retrait loups déjà gérés
        par les callbacks), mais il reste à :
        - Annoncer la mort dans le village
        - Ajouter au cimetière
        - Vérifier les conversions (Enfant Sauvage)
        - Vérifier les conditions de victoire
        """
        deaths = result.get('deaths', [])
        if not deaths:
            return

        actor = self.game_manager.get_player(actor_id)

        for dead in deaths:
            # Construire l'annonce selon le contexte
            if (command == 'tuer' and actor and actor.role
                    and actor.role.role_type == RoleType.CHASSEUR):
                # Mort par amoureux cascade
                if dead.get_lovers() and any(not l.is_alive for l in dead.get_lovers()) and dead != actor:
                    msg = (
                        f"💔 **{dead.display_name}** meurt de chagrin (amoureux/se) !\n"
                        f"Son rôle était : **{dead.role.name}**"
                    )
                    self._game_events.append(
                        f"💔 **{dead.display_name}** meurt de chagrin ({dead.role.name})"
                    )
                elif dead.user_id == actor_id:
                    # Le chasseur s'est tiré dessus? Improbable mais sûr.
                    continue
                else:
                    msg = (
                        f"💥 **Le Chasseur tire sa dernière balle !** "
                        f"**{dead.display_name}** s'effondre !\n"
                        f"Son rôle était : **{dead.role.name}**"
                    )
                    self._game_events.append(
                        f"🔫 **{actor.display_name}** (Chasseur) tire sur "
                        f"**{dead.display_name}** ({dead.role.name})"
                    )
            elif command == 'dictateur':
                if dead.user_id == actor_id:
                    msg = (
                        f"⚔️ **Le Dictateur {dead.display_name}** paie le prix "
                        f"de son erreur et meurt à son tour !"
                    )
                    self._game_events.append(
                        f"⚔️ **{dead.display_name}** (Dictateur) meurt de son erreur"
                    )
                else:
                    msg = (
                        f"⚔️ **Le Dictateur a pris le pouvoir !** "
                        f"**{dead.display_name}** est éliminé sans procès !\n"
                        f"Son rôle était : **{dead.role.name}**"
                    )
                    self._game_events.append(
                        f"⚔️ Le Dictateur élimine **{dead.display_name}** ({dead.role.name})"
                    )
            elif command == 'admin-kill':
                if dead.get_lovers() and any(not l.is_alive for l in dead.get_lovers()) and dead.user_id != actor_id:
                    msg = (
                        f"💔 **{dead.display_name}** meurt de chagrin (amoureux/se) !\n"
                        f"Son rôle était : **{dead.role.name}**"
                    )
                    self._game_events.append(
                        f"💔 **{dead.display_name}** meurt de chagrin ({dead.role.name})"
                    )
                else:
                    reason = getattr(self, '_admin_kill_reason', 'Tué par un administrateur')
                    msg = (
                        f"⚡ **{dead.display_name}** a été foudroyé par les dieux !\n"
                        f"Son rôle était : **{dead.role.name}**\n"
                    )
                    self._game_events.append(
                        f"⚡ **{dead.display_name}** foudroyé par les dieux ({dead.role.name})"
                    )
            else:
                msg = (
                    f"💀 **{dead.display_name}** est mort.e !\n"
                    f"Son rôle était : **{dead.role.name}**"
                )

            await self.room_manager.send_to_village(msg)
            await self.room_manager.add_to_dead(dead.user_id)

        # Envoyer les DM de mort
        if self.notification_manager:
            for dead in deaths:
                await self.notification_manager.send_death_notification(
                    dead.user_id, dead.role
                )

        await self._update_seating_message()

        # Vérifier conversion Enfant Sauvage
        await self._check_enfant_sauvage_conversion()

        # Vérifier conditions de victoire
        await self._check_victory()

        # Vérifier succession de maire (si le jeu n'est pas terminé)
        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_mayor_succession()

        # Vérifier si un Chasseur mort doit tirer (lancer le timeout)
        if self.game_manager.phase != GamePhase.ENDED:
            await self._check_and_start_chasseur_timeouts()
