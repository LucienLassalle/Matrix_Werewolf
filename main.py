"""Point d'entrée du bot Matrix Loup-Garou."""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from matrix_bot.bot_controller import WerewolfBot
from models.enums import RoleType


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
    # override=True : le fichier .env est toujours prioritaire sur les
    # variables d'environnement déjà définies (ex: Docker env_file).
    # Sans cela, modifier le .env puis redémarrer le container ne prend
    # pas effet car Docker conserve les anciennes valeurs en mémoire.
    load_dotenv(override=True)
    
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
    
    # ── Validation des rôles désactivés ──
    disabled_roles = set()
    role_disable_str = os.getenv('ROLE_DISABLE', '').strip()
    if role_disable_str:
        valid_role_names = {rt.value for rt in RoleType}
        for raw_name in role_disable_str.split(','):
            name = raw_name.strip()
            if not name:
                continue
            if name not in valid_role_names:
                logger.error(
                    f"❌ ROLE_DISABLE : rôle invalide '{name}'. "
                    f"Rôles valides : {', '.join(sorted(valid_role_names))}"
                )
                sys.exit(1)
            disabled_roles.add(RoleType(name))
        if disabled_roles:
            from models.role import ROLE_DISPLAY_NAMES
            names = ', '.join(ROLE_DISPLAY_NAMES.get(rt, rt.value) for rt in disabled_roles)
            logger.info(f"🚫 Rôles désactivés : {names}")
    
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
        runtests=runtests,
        disabled_roles=disabled_roles
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
