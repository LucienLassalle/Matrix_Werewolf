"""Gestionnaire de messages et callbacks Matrix."""

import re
import time
import logging
from typing import Callable, Dict, Optional
from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomMemberEvent

logger = logging.getLogger(__name__)


class MessageHandler:
    """Gère les callbacks et le parsing des messages Matrix."""
    
    def __init__(self, client: AsyncClient, bot_user_id: str):
        self.client = client
        self.bot_user_id = bot_user_id
        
        # Timestamp de démarrage (ms) pour ignorer les messages historiques
        # Lors du premier sync, Matrix renvoie TOUT l'historique.
        # On ne traite que les messages reçus APRÈS le démarrage du handler.
        self._start_time_ms = int(time.time() * 1000)
        logger.info(f"MessageHandler initialisé — ignore les messages avant timestamp {self._start_time_ms}")
        
        # Callbacks personnalisés
        self.on_command: Optional[Callable] = None
        self.on_registration: Optional[Callable] = None
        self.on_wolf_message: Optional[Callable] = None  # Messages des loups
        self.on_village_message: Optional[Callable] = None  # Messages du village (Loup Bavard)
        
        # Pour suivre les salons
        self.wolves_room_id: Optional[str] = None
        self.village_room_id: Optional[str] = None
        
        # Enregistrer les callbacks
        self.client.add_event_callback(self._on_message, RoomMessageText)
        self.client.add_event_callback(self._on_member_join, RoomMemberEvent)
    
    async def _on_message(self, room: MatrixRoom, event: RoomMessageText):
        """Callback appelé quand un message est reçu."""
        # Ignorer les messages du bot
        if event.sender == self.bot_user_id:
            return
        
        # Ignorer les messages HISTORIQUES (envoyés avant le démarrage du bot)
        # server_timestamp est en millisecondes depuis l'epoch
        event_ts = getattr(event, 'server_timestamp', 0)
        if event_ts < self._start_time_ms:
            logger.debug(
                f"⏭️ Message ignoré (historique): {event.sender} dans {room.display_name} "
                f"— ts={event_ts} < start={self._start_time_ms} — contenu: {event.body[:50]!r}"
            )
            return
        
        message = event.body.strip()
        sender = event.sender
        room_id = room.room_id
        event_id = getattr(event, 'event_id', None)
        
        logger.info(f"📨 Message LIVE de {sender} dans {room.display_name}: {message[:80]!r}")
        
        # Si c'est un message dans le salon des loups, le transmettre à la Petite Fille
        if room_id == self.wolves_room_id and self.on_wolf_message:
            try:
                await self.on_wolf_message(message, sender)
            except Exception as e:
                logger.error(f"Erreur lors de la transmission à la Petite Fille: {e}")
        
        # Si c'est un message dans le village, vérifier le mot du Loup Bavard
        if room_id == self.village_room_id and self.on_village_message:
            try:
                await self.on_village_message(message, sender)
            except Exception as e:
                logger.error(f"Erreur village message handler: {e}")
        
        # Détecter les commandes (commence par /)
        if message.startswith('/'):
            # Commande d'inscription : /inscription
            cmd_lower = message.split()[0].lower()
            if cmd_lower == '/inscription':
                logger.info(f"📝 Inscription détectée de {sender} dans {room.display_name}")
                if self.on_registration:
                    try:
                        await self.on_registration(room_id, sender)
                    except Exception as e:
                        logger.error(f"Erreur lors de l'inscription: {e}")
            else:
                await self._handle_command(room_id, sender, message, event_id)
    
    async def _on_member_join(self, room: MatrixRoom, event: RoomMemberEvent):
        """Callback appelé quand un membre rejoint un salon."""
        if event.membership == "join" and event.sender != self.bot_user_id:
            # Ignorer les événements historiques (replay du sync initial)
            event_ts = getattr(event, 'server_timestamp', 0)
            if event_ts < self._start_time_ms:
                return
            logger.info(f"{event.sender} a rejoint {room.display_name}")
    
    async def _handle_command(self, room_id: str, sender: str, message: str, event_id: Optional[str] = None):
        """Parse et traite une commande."""
        parts = message.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        logger.info(f"Commande: {command} avec args: {args}")
        
        # Extraire le nom de la commande sans le /
        command_name = command[1:] if command.startswith('/') else command
        
        # Appeler le callback si défini
        if self.on_command:
            try:
                result = await self.on_command(room_id, sender, command_name, args, event_id)
                
                # Confirmer avec un emoji 👍
                if result is not None and result.get('success') and event_id:
                    await self._acknowledge_command(room_id, event_id)
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de {command}: {e}")
                await self._send_error(room_id, str(e))
    
    async def _acknowledge_command(self, room_id: str, event_id: Optional[str] = None):
        """Ajoute une réaction 👍 pour confirmer la commande."""
        if not event_id:
            return
        
        try:
            await self.client.room_send(
                room_id,
                message_type="m.reaction",
                content={
                    "m.relates_to": {
                        "rel_type": "m.annotation",
                        "event_id": event_id,
                        "key": "👍"
                    }
                }
            )
        except Exception as e:
            logger.error(f"Erreur ajout réaction 👍: {e}")
    
    async def _send_error(self, room_id: str, error: str):
        """Envoie un message d'erreur."""
        await self.client.room_send(
            room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": f"❌ Erreur: {error}"
            }
        )
    
    @staticmethod
    def parse_target(args: list) -> Optional[str]:
        """Extrait une cible (pseudo) des arguments."""
        if not args:
            return None
        
        # Joindre tous les args en cas de pseudo avec espaces
        target = ' '.join(args)
        
        # Retirer @ si présent
        if target.startswith('@'):
            target = target[1:]
        
        return target.strip()
    
    @staticmethod
    def extract_user_id(matrix_id: str) -> str:
        """Extrait le nom d'utilisateur de l'ID Matrix complet."""
        # @username:server.com -> username
        match = re.match(r'@([^:]+):', matrix_id)
        if match:
            return match.group(1)
        return matrix_id
