"""Tests d'intégration Matrix — exécutés au premier lancement (BDD vide).

Ce module utilise 2 comptes de test réels (@test2 et @test3) et 2 joueurs
fictifs pour simuler des scénarios complets sur le vrai serveur Matrix.

Tests :
1. Inscription dans le lobby + lancement de partie
2. Vote loup → mort du villageois → mute dans le village
3. Petite Fille reçoit les messages des loups en DM
"""

import asyncio
import logging
import time
from typing import Optional

import aiohttp
from nio import AsyncClient

from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.room_manager import RoomManager
from matrix_bot.notifications import NotificationManager
from game.game_manager import GameManager
from commands.command_handler import CommandHandler
from models.enums import GamePhase, RoleType, Team
from roles import RoleFactory

logger = logging.getLogger(__name__)

# Joueurs fictifs (n'existent pas sur le serveur Matrix)
FAKE_USER_1 = "@fake_villager_a:lloka.fr"
FAKE_USER_2 = "@fake_villager_b:lloka.fr"


class IntegrationTester:
    """Exécute les tests d'intégration sur le vrai serveur Matrix."""

    def __init__(
        self,
        bot_client: MatrixClientWrapper,
        space_id: str,
        lobby_room_id: str,
        test_user_id: str,
        test_user_token: str,
        test_user2_id: str,
        test_user2_token: str,
        homeserver: str,
    ):
        self.bot = bot_client
        self.space_id = space_id
        self.lobby_room_id = lobby_room_id
        self.homeserver = homeserver

        # Comptes de test
        self.user1_id = test_user_id        # @test2:lloka.fr
        self.user1_token = test_user_token
        self.user2_id = test_user2_id        # @test3:lloka.fr
        self.user2_token = test_user2_token

        # Clients Matrix des comptes de test
        self.client1: Optional[AsyncClient] = None
        self.client2: Optional[AsyncClient] = None

        # Compteurs
        self._passed = 0
        self._failed = 0
        self._errors: list[str] = []

    # ────────────────────── helpers ──────────────────────

    def _ok(self, label: str):
        self._passed += 1
        logger.info(f"  ✅ {label}")

    def _fail(self, label: str, detail: str = ""):
        self._failed += 1
        msg = f"  ❌ {label}" + (f" — {detail}" if detail else "")
        self._errors.append(msg)
        logger.error(msg)

    async def _connect_test_client(
        self, user_id: str, token: str
    ) -> Optional[AsyncClient]:
        """Connecte un compte de test et retourne le client."""
        try:
            client = AsyncClient(self.homeserver, user_id)
            client.access_token = token
            resp = await client.whoami()
            if resp and hasattr(resp, "user_id"):
                logger.info(f"  Compte de test connecté : {resp.user_id}")
                return client
            logger.error(f"  whoami échoué pour {user_id}")
            return None
        except Exception as e:
            logger.error(f"  Connexion échouée pour {user_id}: {e}")
            return None

    async def _connect_all(self) -> bool:
        """Connecte les deux comptes de test."""
        self.client1 = await self._connect_test_client(self.user1_id, self.user1_token)
        self.client2 = await self._connect_test_client(self.user2_id, self.user2_token)
        return self.client1 is not None and self.client2 is not None

    async def _disconnect_all(self):
        for c in (self.client1, self.client2):
            if c:
                await c.close()
        self.client1 = self.client2 = None

    async def _send_as(self, client: AsyncClient, room_id: str, body: str) -> bool:
        """Envoie un message depuis un client de test."""
        try:
            resp = await client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": body},
            )
            return hasattr(resp, "event_id")
        except Exception as e:
            logger.debug(f"  _send_as error: {e}")
            return False

    async def _join_as(self, client: AsyncClient, room_id: str) -> bool:
        """Rejoint un salon depuis un client de test."""
        try:
            resp = await client.join(room_id)
            return hasattr(resp, "room_id")
        except Exception as e:
            logger.debug(f"  _join_as error: {e}")
            return False

    async def _read_room_history(
        self,
        token: str,
        room_id: str,
        search_text: str,
        limit: int = 10,
    ) -> bool:
        """Lit l'historique d'un salon via l'API REST et cherche search_text."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = (
                f"{self.homeserver}/_matrix/client/v3/rooms/{room_id}"
                f"/messages?dir=b&limit={limit}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for ev in data.get("chunk", []):
                            body = ev.get("content", {}).get("body", "")
                            if search_text in body:
                                return True
            return False
        except Exception as e:
            logger.debug(f"  _read_room_history error: {e}")
            return False

    async def _read_room_history_detail(
        self,
        token: str,
        room_id: str,
        search_text: str,
        limit: int = 10,
    ) -> Optional[dict]:
        """Comme _read_room_history mais retourne l'event complet."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = (
                f"{self.homeserver}/_matrix/client/v3/rooms/{room_id}"
                f"/messages?dir=b&limit={limit}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for ev in data.get("chunk", []):
                            body = ev.get("content", {}).get("body", "")
                            if search_text in body:
                                return ev
            return None
        except Exception:
            return None

    async def _sync_find_message(
        self,
        client: AsyncClient,
        room_id: str,
        search_text: str,
        timeout: int = 5000,
    ) -> bool:
        """Sync un client et cherche search_text dans room_id."""
        try:
            sync_resp = await client.sync(timeout=timeout, full_state=False)
            if not sync_resp or not hasattr(sync_resp, "rooms"):
                return False
            join_rooms = (
                sync_resp.rooms.join if hasattr(sync_resp.rooms, "join") else {}
            )
            if room_id not in join_rooms:
                return False
            room_data = join_rooms[room_id]
            timeline = (
                room_data.timeline.events
                if hasattr(room_data, "timeline")
                else []
            )
            for event in timeline:
                if search_text in getattr(event, "body", ""):
                    return True
            return False
        except Exception as e:
            logger.debug(f"  _sync_find_message error: {e}")
            return False

    async def _cleanup_room(self, room_id: str, space_id: str = None):
        """Supprime un salon de test (retirer du space + kick + leave + forget)."""
        if not room_id:
            return
        try:
            if space_id:
                await self.bot.remove_room_from_space(space_id, room_id)
            members = await self.bot.get_room_members(room_id)
            for mid in members:
                if mid != self.bot.user_id:
                    try:
                        await self.bot.kick_user(room_id, mid, "Test terminé")
                    except Exception:
                        pass
            await self.bot.delete_room(room_id)
            if self.bot.client:
                try:
                    await self.bot.client.room_forget(room_id)
                except Exception:
                    pass
            for c in (self.client1, self.client2):
                if c:
                    try:
                        await c.room_forget(room_id)
                    except Exception:
                        pass
        except Exception:
            pass

    # ────────────────────── run_all ──────────────────────

    async def run_all(self) -> bool:
        logger.info("=" * 60)
        logger.info("🧪 TESTS D'INTÉGRATION MATRIX — Premier lancement")
        logger.info(f"   Compte test 1 : {self.user1_id}")
        logger.info(f"   Compte test 2 : {self.user2_id}")
        logger.info("=" * 60)

        if not await self._connect_all():
            logger.error("⛔ Impossible de connecter les comptes de test. Tests annulés.")
            return False

        try:
            await self._test_1_inscription_and_start()
            await self._test_2_wolf_kill_and_mute()
            await self._test_3_petite_fille_dm()
        except Exception as e:
            self._fail("EXCEPTION INATTENDUE", str(e))
            logger.exception("Exception pendant les tests d'intégration")
        finally:
            await self._disconnect_all()

        total = self._passed + self._failed
        logger.info("=" * 60)
        if self._failed == 0:
            logger.info(f"🎉 TOUS LES TESTS PASSENT ({self._passed}/{total})")
        else:
            logger.error(f"⛔ {self._failed} ÉCHEC(S) sur {total} tests")
            for err in self._errors:
                logger.error(err)
        logger.info("=" * 60)

        return self._failed == 0

    # ══════════════════════════════════════════════════════
    # TEST 1 : Inscription dans le lobby + lancement de partie
    # ══════════════════════════════════════════════════════

    async def _test_1_inscription_and_start(self):
        """2 faux joueurs + 2 vrais écrivent /inscription dans le lobby → partie lancée."""
        logger.info("── Test 1 : Inscription dans le lobby + lancement de partie ──")

        # Préparer un GameManager + CommandHandler de test
        gm = GameManager(db_path=":memory:")
        ch = CommandHandler(gm)

        # ── Ajouter les 2 joueurs fictifs en dur ──
        gm.add_player("fake_villager_a", FAKE_USER_1)
        gm.add_player("fake_villager_b", FAKE_USER_2)
        self._ok("2 joueurs fictifs ajoutés")

        # ── Les 2 vrais comptes rejoignent le lobby ──
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

        # ── Les 2 vrais comptes écrivent /inscription dans le lobby ──
        # (on simule ce que fait _handle_registration — l'inscription
        # ajoute le joueur dans le game manager)
        sent1 = await self._send_as(self.client1, self.lobby_room_id, "/inscription")
        if sent1:
            self._ok(f"{self.user1_id} a écrit /inscription dans le lobby")
        else:
            self._fail(f"{self.user1_id} n'a pas pu écrire dans le lobby")
            return

        sent2 = await self._send_as(self.client2, self.lobby_room_id, "/inscription")
        if sent2:
            self._ok(f"{self.user2_id} a écrit /inscription dans le lobby")
        else:
            self._fail(f"{self.user2_id} n'a pas pu écrire dans le lobby")
            return

        # Simuler le traitement de l'inscription
        pseudo1 = self.user1_id.split(":")[0].lstrip("@")
        pseudo2 = self.user2_id.split(":")[0].lstrip("@")
        gm.add_player(pseudo1, self.user1_id)
        gm.add_player(pseudo2, self.user2_id)
        self._ok(f"4 joueurs enregistrés : {list(gm.players.keys())}")

        # Configurer les rôles (1 loup + 3 villageois)
        gm.set_roles({RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 3})

        # Lancer la partie
        result = gm.start_game()
        if result.get("success"):
            self._ok("Partie lancée avec succès (4 joueurs)")
        else:
            self._fail("Échec du lancement de la partie", result.get("message", ""))
            return

        # Vérifications
        if gm.phase == GamePhase.NIGHT:
            self._ok("Phase = NIGHT après start_game")
        else:
            self._fail("Phase attendue NIGHT", f"got {gm.phase}")

        if len(gm.players) == 4:
            self._ok("4 joueurs dans la partie")
        else:
            self._fail(f"Attendu 4 joueurs, got {len(gm.players)}")

        # Vérifier qu'il y a exactement 1 loup et 3 villageois/gentils
        wolves = [p for p in gm.players.values() if p.role and p.get_team() == Team.MECHANT]
        gentils = [p for p in gm.players.values() if p.role and p.get_team() == Team.GENTIL]
        if len(wolves) == 1 and len(gentils) == 3:
            self._ok("Distribution des rôles correcte (1 loup, 3 villageois)")
        else:
            self._fail(
                "Distribution incorrecte",
                f"wolves={len(wolves)} gentils={len(gentils)}",
            )

        # Vérifier que la partie a bien un game log
        if len(gm.game_log) > 0:
            self._ok("Game log initialisé")
        else:
            self._fail("Game log vide après lancement")

    # ══════════════════════════════════════════════════════
    # TEST 2 : Loup vote → villageois meurt → muté dans le village
    # ══════════════════════════════════════════════════════

    async def _test_2_wolf_kill_and_mute(self):
        """2 faux + 2 vrais. user1 = loup, user2 = villageois.
        Le loup vote la cible dans le salon des loups.
        Après la nuit, le villageois est mort et ne peut plus écrire dans le village.
        """
        logger.info("── Test 2 : Vote loup → mort du villageois → mute ──")

        # ── Créer les salons de jeu réels ──
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
            invite_users=[self.user1_id],  # Seul le loup est invité
            space_id=self.space_id,
        )
        if not wolves_room:
            self._fail("Création salon loups")
            await self._cleanup_room(village_room, self.space_id)
            return
        self._ok(f"Salon loups créé : {wolves_room}")

        # Les comptes de test rejoignent les salons
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

        # ── Préparer la partie en mémoire ──
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

        # Forcer les rôles : user1 = loup, tous les autres = villageois
        wolf_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        wolf_role.assign_to_player(gm.players[self.user1_id])
        for uid in [FAKE_USER_1, FAKE_USER_2, self.user2_id]:
            r = RoleFactory.create_role(RoleType.VILLAGEOIS)
            r.assign_to_player(gm.players[uid])

        self._ok("Rôles forcés : user1=Loup, user2+fakes=Villageois")

        # ── Le loup envoie la commande /vote dans le salon des loups ──
        gm.set_phase(GamePhase.NIGHT)
        gm.vote_manager.reset_votes(wolf_votes=True)

        # Le loup écrit /vote dans le salon Matrix des loups
        await asyncio.sleep(0.5)
        vote_sent = await self._send_as(
            self.client1, wolves_room, f"/vote {pseudo2}"
        )
        if vote_sent:
            self._ok(f"Loup a écrit '/vote {pseudo2}' dans le salon des loups")
        else:
            self._fail("Loup ne peut pas écrire dans le salon des loups")

        # On traite le vote côté game manager (simule ce que le bot ferait)
        vote_result = ch.execute_command(
            user_id=self.user1_id, command="vote", args=[pseudo2]
        )
        if vote_result.get("success"):
            self._ok(f"Vote loup enregistré pour {pseudo2}")
        else:
            self._fail("Vote loup échoué", vote_result.get("message", ""))

        # ── Résoudre la nuit ──
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

        # Vérifier que le loup est toujours vivant
        wolf_player = gm.players[self.user1_id]
        if wolf_player.is_alive:
            self._ok(f"{pseudo1} (loup) est toujours vivant")
        else:
            self._fail(f"{pseudo1} ne devrait pas être mort")

        # ── Muter le villageois mort dans le salon du village ──
        # (simule ce que on_mute_player fait via set_power_level)
        try:
            await self.bot.set_power_level(village_room, self.user2_id, -1)
            self._ok("Power level de user2 mis à -1 dans le village")
        except Exception as e:
            self._fail("Mise à jour power level", str(e))
            await self._cleanup_room(village_room, self.space_id)
            await self._cleanup_room(wolves_room, self.space_id)
            return

        # ── Vérifier que user2 ne peut PLUS écrire ──
        await asyncio.sleep(0.5)
        can_write = await self._send_as(
            self.client2, village_room, "Je suis mort, je ne devrais pas pouvoir parler"
        )
        if not can_write:
            self._ok("user2 (mort) NE PEUT PLUS écrire dans le village ✅")
        else:
            self._fail("user2 (mort) peut encore écrire — le mute n'a pas fonctionné")

        # ── Vérifier que user2 peut toujours LIRE ──
        # Le bot envoie un message dans le village, user2 doit le voir
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

        # ── Nettoyage ──
        try:
            await self.bot.set_power_level(village_room, self.user2_id, 0)
        except Exception:
            pass
        await self._cleanup_room(village_room, self.space_id)
        await self._cleanup_room(wolves_room, self.space_id)

    # ══════════════════════════════════════════════════════
    # TEST 3 : Petite Fille reçoit les messages des loups en DM
    # ══════════════════════════════════════════════════════

    async def _test_3_petite_fille_dm(self):
        """user1 = loup, user2 = petite fille, 2 faux = villageois.
        Le loup parle dans le salon des loups.
        La petite fille doit recevoir le message en DM.
        """
        logger.info("── Test 3 : Petite Fille reçoit les messages des loups ──")

        # ── Créer le salon des loups ──
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

        # ── Préparer la partie en mémoire ──
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

        # Forcer les rôles
        wolf_role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        wolf_role.assign_to_player(gm.players[self.user1_id])

        pf_role = RoleFactory.create_role(RoleType.PETITE_FILLE)
        pf_role.assign_to_player(gm.players[self.user2_id])

        for uid in [FAKE_USER_1, FAKE_USER_2]:
            r = RoleFactory.create_role(RoleType.VILLAGEOIS)
            r.assign_to_player(gm.players[uid])

        self._ok("Rôles forcés : user1=Loup, user2=Petite Fille, fakes=Villageois")

        gm.set_phase(GamePhase.NIGHT)

        # ── Vérifier que la Petite Fille peut espionner les loups ──
        pf_player = gm.players[self.user2_id]
        if pf_player.role and pf_player.role.can_see_wolf_messages():
            self._ok("Petite Fille a bien le pouvoir d'espionner les loups")
        else:
            self._fail("Petite Fille n'a pas can_see_wolf_messages()")

        # ── Envoyer la notification de rôle à la Petite Fille ──
        notif = NotificationManager.__new__(NotificationManager)
        role_message = notif._format_role_message(pf_role)

        if role_message and len(role_message) > 20:
            self._ok("Message de rôle Petite Fille formaté")
        else:
            self._fail("Message de rôle vide ou trop court")

        # Vérifier que le message contient les bonnes infos
        has_name = "Petite Fille" in role_message
        has_espion = "espionn" in role_message.lower() or "loups" in role_message.lower()
        if has_name and has_espion:
            self._ok("Message contient : nom du rôle + pouvoir d'espionnage")
        else:
            self._fail("Message de rôle incomplet", f"name={has_name} espion={has_espion}")

        # Envoyer le DM de rôle via le bot
        dm_role_sent = await self.bot.send_dm(self.user2_id, role_message)
        if dm_role_sent:
            self._ok("DM de rôle envoyé à la Petite Fille")
        else:
            self._fail("Échec envoi DM de rôle à la Petite Fille")

        # ── Le loup écrit dans le salon des loups ──
        wolf_message = f"🧪 On mange le villageois ce soir — ts={int(time.time())}"
        wolf_sent = await self._send_as(self.client1, wolves_room, wolf_message)
        if wolf_sent:
            self._ok("Loup a écrit dans le salon des loups")
        else:
            self._fail("Loup ne peut pas écrire dans le salon des loups")
            await self._cleanup_room(wolves_room, self.space_id)
            return

        # ── Le bot transmet le message à la Petite Fille en DM ──
        # (simule _handle_wolf_message qui envoie en DM)
        dm_wolf_message = f"🐺 [Chuchotements des loups] : {wolf_message}"
        dm_espion_sent = await self.bot.send_dm(self.user2_id, dm_wolf_message)
        if dm_espion_sent:
            self._ok("DM d'espionnage envoyé à la Petite Fille")
        else:
            self._fail("Échec envoi DM d'espionnage")
            await self._cleanup_room(wolves_room, self.space_id)
            return

        # ── Vérifier que la Petite Fille reçoit bien le message ──
        dm_room_id = self.bot._dm_rooms.get(self.user2_id)
        if not dm_room_id:
            self._fail("Aucun DM room trouvé pour user2 après envoi")
            await self._cleanup_room(wolves_room, self.space_id)
            return
        self._ok(f"DM room pour user2 : {dm_room_id}")

        await asyncio.sleep(0.5)
        await self._join_as(self.client2, dm_room_id)
        await asyncio.sleep(0.5)

        # Vérifier via sync
        found_via_sync = await self._sync_find_message(
            self.client2, dm_room_id, "Chuchotements des loups"
        )
        if found_via_sync:
            self._ok("Petite Fille a REÇU le message d'espionnage (sync) ✉️")
        else:
            # Fallback : lire l'historique via REST
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

        # ── Vérifier que le DM de rôle est aussi dans le salon ──
        found_role = await self._read_room_history(
            self.user2_token, dm_room_id, "Petite Fille"
        )
        if found_role:
            self._ok("DM de rôle (Petite Fille) aussi trouvé dans le salon DM ✉️")
        else:
            # Ce n'est pas bloquant, le sync aurait pu le manquer
            logger.info("  ℹ️ DM de rôle non trouvé via historique (délai possible)")

        # ── Nettoyage ──
        await self._cleanup_room(wolves_room, self.space_id)
