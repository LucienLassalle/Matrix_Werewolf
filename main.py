"""Point d'entrée du bot Matrix Loup-Garou."""

import asyncio
import logging
import os
from dotenv import load_dotenv

from matrix_bot.bot_controller import WerewolfBot


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('werewolf_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Fonction principale."""
    # Charger les variables d'environnement
    load_dotenv()
    
    # Récupérer la configuration
    homeserver = os.getenv('MATRIX_HOMESERVER')
    user_id = os.getenv('MATRIX_USER_ID')
    access_token = os.getenv('MATRIX_ACCESS_TOKEN')
    password = os.getenv('MATRIX_PASSWORD')  # Optionnel : pour renouveler le token
    space_id = os.getenv('MATRIX_SPACE_ID')
    lobby_room_id = os.getenv('MATRIX_LOBBY_ROOM_ID')
    runtests = os.getenv('MATRIX_RUN_TESTS', 'false').lower() == 'true'
    
    # Vérifier que tout est configuré
    if not all([homeserver, user_id, access_token, space_id, lobby_room_id]):
        logger.error("Configuration incomplète. Vérifiez votre fichier .env")
        logger.error("Variables requises : MATRIX_HOMESERVER, MATRIX_USER_ID, "
                     "MATRIX_ACCESS_TOKEN, MATRIX_SPACE_ID, MATRIX_LOBBY_ROOM_ID")
        logger.error("Variable optionnelle : MATRIX_PASSWORD (pour renouvellement auto du token)")
        return
    
    if not password:
        logger.warning("⚠️ MATRIX_PASSWORD non configuré. Le renouvellement auto du token est désactivé.")
    
    # Configuration des comptes de test (pour les tests d'intégration)
    test_user_id = os.getenv('MATRIX_TESTUSER_ID')
    test_user_password = os.getenv('MATRIX_TESTUSER_PASSWORD')
    test_user_token = os.getenv('MATRIX_TESTUSER_TOKEN')
    test_user2_id = os.getenv('MATRIX_TESTUSER2_ID')
    test_user2_password = os.getenv('MATRIX_TESTUSER2_PASSWORD')
    test_user2_token = os.getenv('MATRIX_TESTUSER2_TOKEN')
    
    logger.info("🐺 Démarrage du bot Loup-Garou Matrix...")
    logger.info(f"Server: {homeserver}")
    logger.info(f"User: {user_id}")
    logger.info(f"Space: {space_id}")
    logger.info(f"Lobby: {lobby_room_id}")
    
    # Créer et démarrer le bot
    bot = WerewolfBot(
        homeserver=homeserver,
        user_id=user_id,
        access_token=access_token,
        space_id=space_id,
        lobby_room_id=lobby_room_id,
        password=password,
        test_user_id=test_user_id,
        test_user_password=test_user_password,
        test_user_token=test_user_token,
        test_user2_id=test_user2_id,
        test_user2_password=test_user2_password,
        test_user2_token=test_user2_token,
        runtests=runtests
    )
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Interruption utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
    finally:
        await bot.stop()


if __name__ == '__main__':
    asyncio.run(main())
