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
from typing import Optional

from nio import AsyncClient

from matrix_bot.matrix_client import MatrixClientWrapper
from matrix_bot.integration_test_helpers import IntegrationTestHelpersMixin
from matrix_bot.integration_test_cases import IntegrationTestCasesMixin

logger = logging.getLogger(__name__)


class IntegrationTester(IntegrationTestHelpersMixin, IntegrationTestCasesMixin):
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

