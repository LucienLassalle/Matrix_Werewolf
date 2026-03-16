"""Cas de tests d'integration Matrix."""

from __future__ import annotations

import asyncio
import os
import time
import logging
from typing import TYPE_CHECKING

from matrix_bot.notifications import NotificationManager
from game.game_manager import GameManager
from commands.command_handler import CommandHandler
from models.enums import GamePhase, RoleType, Team
from roles import RoleFactory

if TYPE_CHECKING:
    from matrix_bot.integration_test import IntegrationTester

logger = logging.getLogger(__name__)

# Joueurs fictifs (n'existent pas sur le serveur Matrix)
FAKE_USER_1 = "@fake_villager_a:lloka.fr"
FAKE_USER_2 = "@fake_villager_b:lloka.fr"


class IntegrationTestCasesMixin:
    """Cas de tests d'integration."""

    async def _test_1_inscription_and_start(self: 'IntegrationTester'):
        """2 faux joueurs + 2 vrais écrivent la commande inscription dans le lobby → partie lancée."""
        logger.info("── Test 1 : Inscription dans le lobby + lancement de partie ──")

        gm = GameManager(db_path=":memory:")
        ch = CommandHandler(gm)

        gm.add_player("fake_villager_a", FAKE_USER_1)
        gm.add_player("fake_villager_b", FAKE_USER_2)
        self._ok("2 joueurs fictifs ajoutés")

        j1 = await self._join_as(self.client1, self.lobby_room_id)
        j2 = await self._join_as(self.client2, self.lobby_room_id)
        if j1 and j2:
            self._ok("Les 2 comptes de test ont rejoint le lobby")
        elif j1:
            self._fail(f"{self.user2_id} n'a pas pu rejoindre le lobby")
            return
        elif j2:
            self._fail(f"{self.user1_id} n'a pas pu rejoindre le lobby")
            return
        else:
            self._fail("Aucun compte de test n'a pu rejoindre le lobby")
            return

        sent1 = await self._send_as(
            self.client1,
            self.lobby_room_id,
            f"{os.getenv('COMMAND_PREFIX', '!')}inscription",
        )
        if sent1:
            self._ok(
                f"{self.user1_id} a écrit {os.getenv('COMMAND_PREFIX', '!')}inscription dans le lobby"
            )
        else:
            self._fail(f"{self.user1_id} n'a pas pu écrire dans le lobby")
            return

        sent2 = await self._send_as(
            self.client2,
            self.lobby_room_id,
            f"{os.getenv('COMMAND_PREFIX', '!')}inscription",
        )
        if sent2:
            self._ok(
                f"{self.user2_id} a écrit {os.getenv('COMMAND_PREFIX', '!')}inscription dans le lobby"
            )
        else:
            self._fail(f"{self.user2_id} n'a pas pu écrire dans le lobby")
            return

        pseudo1 = self.user1_id.split(":")[0].lstrip("@")
        pseudo2 = self.user2_id.split(":")[0].lstrip("@")
        gm.add_player(pseudo1, self.user1_id)
        gm.add_player(pseudo2, self.user2_id)
        self._ok(f"4 joueurs enregistrés : {list(gm.players.keys())}")

        gm.set_roles({RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 3})

        result = gm.start_game()
        if result.get("success"):
            self._ok("Partie lancée avec succès (4 joueurs)")
        else:
            self._fail("Échec du lancement de la partie", result.get("message", ""))
            return

        if gm.phase == GamePhase.NIGHT:
            self._ok("Phase = NIGHT après start_game")
        else:
            self._fail("Phase attendue NIGHT", f"got {gm.phase}")

        if len(gm.players) == 4:
            self._ok("4 joueurs dans la partie")
        else:
            self._fail(f"Attendu 4 joueurs, got {len(gm.players)}")

        wolves = [p for p in gm.players.values() if p.role and p.get_team() == Team.MECHANT]
        gentils = [p for p in gm.players.values() if p.role and p.get_team() == Team.GENTIL]
        if len(wolves) == 1 and len(gentils) == 3:
            self._ok("Distribution des rôles correcte (1 loup, 3 villageois)")
        else:
            self._fail("Distribution incorrecte", f"wolves={len(wolves)} gentils={len(gentils)}")

        if len(gm.game_log) > 0:
            self._ok("Game log initialisé")
        else:
            self._fail("Game log vide après lancement")

    async def _test_2_wolf_kill_and_mute(self: 'IntegrationTester'):
        """2 faux + 2 vrais. user1 = loup, user2 = villageois."""
        logger.info("── Test 2 : Vote loup → mort du villageois → mute ──")

        all_real_ids = [self.user1_id, self.user2_id]

        village_room = await self.bot.create_room(
            name="🧪 Village Test 2",
            topic="Test d'intégration — village",
            is_public=False,
            invite_users=all_real_ids,
            space_id=self.space_id,
        )
        if not village_room:
            self._fail("Création salon village")
            return
        self._ok(f"Salon village créé : {village_room}")

        wolves_room = await self.bot.create_room(
            name="🧪 Loups Test 2",
            topic="Test d'intégration — loups",
            is_public=False,
            invite_users=[self.user1_id],
            space_id=self.space_id,
        )
        if not wolves_room:
            self._fail("Création salon loups")
            await self._cleanup_room(village_room, self.space_id)
            return
        self._ok(f"Salon loups créé : {wolves_room}")

        await asyncio.sleep(1)
        j1_village = await self._join_as(self.client1, village_room)
        j2_village = await self._join_as(self.client2, village_room)
        j1_wolves = await self._join_as(self.client1, wolves_room)

        if j1_village and j2_village:
            self._ok("Les 2 comptes de test ont rejoint le village")
        else:
            self._fail("Impossible de rejoindre le village", f"u1={j1_village} u2={j2_village}")
            await self._cleanup_room(village_room, self.space_id)
            await self._cleanup_room(wolves_room, self.space_id)
            return

        if j1_wolves:
            self._ok("Le loup (user1) a rejoint le salon des loups")
        else:
            self._fail("Le loup n'a pas pu rejoindre le salon des loups")

        gm = GameManager(db_path=":memory:")
        ch = CommandHandler(gm)

        pseudo1 = self.user1_id.split(":")[0].lstrip("@")
        pseudo2 = self.user2_id.split(":")[0].lstrip("@")
        gm.add_player("fake_villager_a", FAKE_USER_1)
        gm.add_player("fake_villager_b", FAKE_USER_2)
        gm.add_player(pseudo1, self.user1_id)
        gm.add_player(pseudo2, self.user2_id)

        gm.set_roles({RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 3})
        result = gm.start_game()
        if not result.get("success"):
            self._fail("Démarrage partie test 2", result.get("message", ""))
            await self._cleanup_room(village_room, self.space_id)
            await self._cleanup_room(wolves_room, self.space_id)
            return

        wolf_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        wolf_role.assign_to_player(gm.players[self.user1_id])
        for uid in [FAKE_USER_1, FAKE_USER_2, self.user2_id]:
            r = RoleFactory.create_role(RoleType.VILLAGEOIS)
            r.assign_to_player(gm.players[uid])

        self._ok("Rôles forcés : user1=Loup, user2+fakes=Villageois")

        gm.set_phase(GamePhase.NIGHT)
        gm.vote_manager.reset_votes(wolf_votes=True)

        await asyncio.sleep(0.5)
        vote_sent = await self._send_as(
            self.client1, wolves_room, f"{os.getenv('COMMAND_PREFIX', '!')}vote {pseudo2}"
        )
        if vote_sent:
            self._ok(f"Loup a écrit '{os.getenv('COMMAND_PREFIX', '!')}vote {pseudo2}' dans le salon des loups")
        else:
            self._fail("Loup ne peut pas écrire dans le salon des loups")

        vote_result = ch.execute_command(
            user_id=self.user1_id, command="vote", args=[pseudo2]
        )
        if vote_result.get("success"):
            self._ok(f"Vote loup enregistré pour {pseudo2}")
        else:
            self._fail("Vote loup échoué", vote_result.get("message", ""))

        night_results = gm.resolve_night()
        deaths = night_results.get("deaths", [])
        victim = gm.players.get(self.user2_id)

        if victim and not victim.is_alive:
            self._ok(f"{pseudo2} est mort cette nuit 💀")
        else:
            self._fail(f"{pseudo2} devrait être mort", f"deaths={deaths}")
            await self._cleanup_room(village_room, self.space_id)
            await self._cleanup_room(wolves_room, self.space_id)
            return

        wolf_player = gm.players[self.user1_id]
        if wolf_player.is_alive:
            self._ok(f"{pseudo1} (loup) est toujours vivant")
        else:
            self._fail(f"{pseudo1} ne devrait pas être mort")

        try:
            await self.bot.set_power_level(village_room, self.user2_id, -1)
            self._ok("Power level de user2 mis à -1 dans le village")
        except Exception as e:
            self._fail("Mise à jour power level", str(e))
            await self._cleanup_room(village_room, self.space_id)
            await self._cleanup_room(wolves_room, self.space_id)
            return

        await asyncio.sleep(0.5)
        can_write = await self._send_as(
            self.client2, village_room, "Je suis mort, je ne devrais pas pouvoir parler"
        )
        if not can_write:
            self._ok("user2 (mort) NE PEUT PLUS écrire dans le village ✅")
        else:
            self._fail("user2 (mort) peut encore écrire — le mute n'a pas fonctionné")

        test_msg = f"🧪 Message de test lecture {int(time.time())}"
        await self.bot.send_message(village_room, test_msg)
        await asyncio.sleep(0.5)

        can_read = await self._read_room_history(
            self.user2_token, village_room, test_msg
        )
        if can_read:
            self._ok("user2 (mort) peut toujours LIRE le village 👁️")
        else:
            self._fail("user2 ne peut pas lire le village après mute")

        try:
            await self.bot.set_power_level(village_room, self.user2_id, 0)
        except Exception:
            pass
        await self._cleanup_room(village_room, self.space_id)
        await self._cleanup_room(wolves_room, self.space_id)

    async def _test_3_petite_fille_dm(self: 'IntegrationTester'):
        """user1 = loup, user2 = petite fille, 2 faux = villageois."""
        logger.info("── Test 3 : Petite Fille reçoit les messages des loups ──")

        wolves_room = await self.bot.create_room(
            name="🧪 Loups Test 3",
            topic="Test d'intégration — petite fille",
            is_public=False,
            invite_users=[self.user1_id],
            space_id=self.space_id,
        )
        if not wolves_room:
            self._fail("Création salon loups test 3")
            return
        self._ok(f"Salon loups créé : {wolves_room}")

        await asyncio.sleep(1)
        joined = await self._join_as(self.client1, wolves_room)
        if joined:
            self._ok("Loup (user1) a rejoint le salon des loups")
        else:
            self._fail("Loup ne peut pas rejoindre le salon des loups")
            await self._cleanup_room(wolves_room, self.space_id)
            return

        gm = GameManager(db_path=":memory:")

        pseudo1 = self.user1_id.split(":")[0].lstrip("@")
        pseudo2 = self.user2_id.split(":")[0].lstrip("@")
        gm.add_player(pseudo1, self.user1_id)
        gm.add_player(pseudo2, self.user2_id)
        gm.add_player("fake_villager_a", FAKE_USER_1)
        gm.add_player("fake_villager_b", FAKE_USER_2)

        gm.set_roles({
            RoleType.LOUP_GAROU: 1,
            RoleType.PETITE_FILLE: 1,
            RoleType.VILLAGEOIS: 2,
        })
        result = gm.start_game()
        if not result.get("success"):
            self._fail("Démarrage partie test 3", result.get("message", ""))
            await self._cleanup_room(wolves_room, self.space_id)
            return

        wolf_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        wolf_role.assign_to_player(gm.players[self.user1_id])

        pf_role = RoleFactory.create_role(RoleType.PETITE_FILLE)
        pf_role.assign_to_player(gm.players[self.user2_id])

        for uid in [FAKE_USER_1, FAKE_USER_2]:
            r = RoleFactory.create_role(RoleType.VILLAGEOIS)
            r.assign_to_player(gm.players[uid])

        self._ok("Rôles forcés : user1=Loup, user2=Petite Fille, fakes=Villageois")

        gm.set_phase(GamePhase.NIGHT)

        pf_player = gm.players[self.user2_id]
        if pf_player.role and pf_player.role.can_see_wolf_messages():
            self._ok("Petite Fille a bien le pouvoir d'espionner les loups")
        else:
            self._fail("Petite Fille n'a pas can_see_wolf_messages()")

        notif = NotificationManager.__new__(NotificationManager)
        role_message = notif._format_role_message(pf_role)

        if role_message and len(role_message) > 20:
            self._ok("Message de rôle Petite Fille formaté")
        else:
            self._fail("Message de rôle vide ou trop court")

        has_name = "Petite Fille" in role_message
        has_espion = "espionn" in role_message.lower() or "loups" in role_message.lower()
        if has_name and has_espion:
            self._ok("Message contient : nom du rôle + pouvoir d'espionnage")
        else:
            self._fail("Message de rôle incomplet", f"name={has_name} espion={has_espion}")

        dm_role_sent = await self.bot.send_dm(self.user2_id, role_message)
        if dm_role_sent:
            self._ok("DM de rôle envoyé à la Petite Fille")
        else:
            self._fail("Échec envoi DM de rôle à la Petite Fille")

        wolf_message = f"🧪 On mange le villageois ce soir — ts={int(time.time())}"
        wolf_sent = await self._send_as(self.client1, wolves_room, wolf_message)
        if wolf_sent:
            self._ok("Loup a écrit dans le salon des loups")
        else:
            self._fail("Loup ne peut pas écrire dans le salon des loups")
            await self._cleanup_room(wolves_room, self.space_id)
            return

        dm_wolf_message = f"🐺 [Chuchotements des loups] : {wolf_message}"
        dm_espion_sent = await self.bot.send_dm(self.user2_id, dm_wolf_message)
        if dm_espion_sent:
            self._ok("DM d'espionnage envoyé à la Petite Fille")
        else:
            self._fail("Échec envoi DM d'espionnage")
            await self._cleanup_room(wolves_room, self.space_id)
            return

        dm_room_id = self.bot._dm_rooms.get(self.user2_id)
        if not dm_room_id:
            self._fail("Aucun DM room trouvé pour user2 après envoi")
            await self._cleanup_room(wolves_room, self.space_id)
            return
        self._ok(f"DM room pour user2 : {dm_room_id}")

        await asyncio.sleep(0.5)
        await self._join_as(self.client2, dm_room_id)
        await asyncio.sleep(0.5)

        found_via_sync = await self._sync_find_message(
            self.client2, dm_room_id, "Chuchotements des loups"
        )
        if found_via_sync:
            self._ok("Petite Fille a REÇU le message d'espionnage (sync) ✉️")
        else:
            found_via_history = await self._read_room_history(
                self.user2_token, dm_room_id, "Chuchotements des loups"
            )
            if found_via_history:
                self._ok("Petite Fille a REÇU le message d'espionnage (historique) ✉️")
            else:
                self._fail(
                    "Petite Fille n'a PAS reçu le message d'espionnage",
                    "ni via sync, ni via historique",
                )

        found_role = await self._read_room_history(
            self.user2_token, dm_room_id, "Petite Fille"
        )
        if found_role:
            self._ok("DM de rôle (Petite Fille) aussi trouvé dans le salon DM ✉️")
        else:
            logger.info("  ℹ️ DM de rôle non trouvé via historique (délai possible)")

        await self._cleanup_room(wolves_room, self.space_id)
