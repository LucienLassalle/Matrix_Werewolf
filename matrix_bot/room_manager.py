"""Gestionnaire de salons Matrix pour le jeu."""

from typing import Dict, List, Optional
from matrix_bot.matrix_client import MatrixClientWrapper
import logging

logger = logging.getLogger(__name__)


class RoomManager:
    """Gère les salons Matrix pour une partie."""
    
    def __init__(self, client: MatrixClientWrapper, space_id: str):
        self.client = client
        self.space_id = space_id
        
        # IDs des salons
        self.lobby_room: Optional[str] = None
        self.village_room: Optional[str] = None
        self.wolves_room: Optional[str] = None
        self.couple_room: Optional[str] = None
        self.dead_room: Optional[str] = None
        
        # Salons DM par utilisateur
        self.dm_rooms: Dict[str, str] = {}
    
    async def create_all_rooms(self, player_ids: List[str]):
        """Crée tous les salons nécessaires pour une partie."""
        logger.info("Création des salons de jeu...")
        
        # 1. Salon du village (tous les joueurs)
        self.village_room = await self.client.create_room(
            name="🏘️ Village",
            topic="Salon principal du village. Discussion et votes publics.",
            is_public=False,
            invite_users=player_ids,
            space_id=self.space_id
        )
        
        # 2. Salon des morts (créé mais vide au départ)
        self.dead_room = await self.client.create_room(
            name="💀 Cimetière",
            topic="Les morts peuvent discuter ici.",
            is_public=False,
            space_id=self.space_id
        )
        
        logger.info(f"Salons créés: Village={self.village_room}, Cimetière={self.dead_room}")
        
        return {
            "village": self.village_room,
            "dead": self.dead_room
        }
    
    async def create_wolves_room(self, wolf_ids: List[str]) -> Optional[str]:
        """Crée le salon des loups."""
        if not wolf_ids:
            return None
        
        self.wolves_room = await self.client.create_room(
            name="🐺 Meute des Loups",
            topic="Salon secret des loups-garous. Votez pour votre victime nocturne.",
            is_public=False,
            invite_users=wolf_ids,
            space_id=self.space_id
        )
        
        if self.wolves_room:
            await self.client.send_message(
                self.wolves_room,
                "🐺 **Bienvenue dans la meute !**\n\n"
                "Vous êtes les loups-garous. Chaque nuit, vous devez voter ensemble "
                "pour éliminer un villageois.\n\n"
                "Utilisez `/vote {pseudo}` pour voter."
            )
        
        logger.info(f"Salon des loups créé: {self.wolves_room}")
        return self.wolves_room
    
    async def create_couple_room(self, lover_ids: List[str]) -> Optional[str]:
        """Crée le salon du couple."""
        if len(lover_ids) != 2:
            return None
        
        self.couple_room = await self.client.create_room(
            name="💕 Couple d'Amoureux",
            topic="Salon privé du couple. Vous gagnez ensemble.",
            is_public=False,
            invite_users=lover_ids,
            space_id=self.space_id
        )
        
        if self.couple_room:
            await self.client.send_message(
                self.couple_room,
                "💕 **Vous êtes en couple !**\n\n"
                "Vous pouvez communiquer librement dans ce salon.\n"
                "Si l'un de vous meurt, l'autre meurt aussi.\n\n"
                "⚠️ Vous gagnez ensemble si vous êtes les deux derniers survivants."
            )
        
        logger.info(f"Salon du couple créé: {self.couple_room}")
        return self.couple_room
    
    async def add_to_wolves(self, user_id: str):
        """Ajoute un joueur au salon des loups (conversion)."""
        if self.wolves_room:
            await self.client.invite_user(self.wolves_room, user_id)
            await self.client.send_message(
                self.wolves_room,
                f"🐺 Un nouveau loup rejoint la meute !"
            )
    
    async def add_to_dead(self, user_id: str):
        """Ajoute un joueur mort au cimetière."""
        if self.dead_room:
            await self.client.invite_user(self.dead_room, user_id)
    
    async def send_to_village(self, message: str):
        """Envoie un message dans le salon du village."""
        if self.village_room:
            await self.client.send_message(self.village_room, message, formatted=True)
    
    async def send_to_wolves(self, message: str):
        """Envoie un message dans le salon des loups."""
        if self.wolves_room:
            await self.client.send_message(self.wolves_room, message, formatted=True)
    
    async def send_to_couple(self, message: str):
        """Envoie un message dans le salon du couple."""
        if self.couple_room:
            await self.client.send_message(self.couple_room, message, formatted=True)
    
    async def send_to_dead(self, message: str):
        """Envoie un message dans le cimetière."""
        if self.dead_room:
            await self.client.send_message(self.dead_room, message, formatted=True)
    
    async def send_dm(self, user_id: str, message: str):
        """Envoie un message privé à un joueur."""
        await self.client.send_dm(user_id, message)
    
    def is_village_room(self, room_id: str) -> bool:
        """Vérifie si c'est le salon du village."""
        return room_id == self.village_room
    
    def is_wolves_room(self, room_id: str) -> bool:
        """Vérifie si c'est le salon des loups."""
        return room_id == self.wolves_room
    
    def is_couple_room(self, room_id: str) -> bool:
        """Vérifie si c'est le salon du couple."""
        return room_id == self.couple_room
    
    def is_dm_room(self, room_id: str) -> bool:
        """Vérifie si c'est un salon DM (ni village, ni loups, ni couple, ni lobby, ni cimetière)."""
        known_rooms = [self.village_room, self.wolves_room, self.couple_room, 
                       self.dead_room, self.lobby_room]
        return room_id not in known_rooms
    
    async def delete_room(self, room_id: str):
        """Supprime un salon proprement (retrait du space + kick + leave + forget)."""
        if not room_id:
            return
        try:
            # 1. Retirer du space pour ne pas laisser de #Unknown
            if self.space_id:
                await self.client.remove_room_from_space(self.space_id, room_id)

            # 2. Kick tous les membres
            members = await self.client.get_room_members(room_id)
            bot_id = self.client.user_id
            for member_id in members:
                if member_id != bot_id:
                    try:
                        await self.client.kick_user(room_id, member_id, "Partie terminée")
                    except Exception:
                        pass

            # 3. Quitter le salon
            await self.client.delete_room(room_id)

            # 4. Forget (ne plus le voir dans la liste)
            if self.client.client:
                try:
                    await self.client.client.room_forget(room_id)
                except Exception:
                    pass

            logger.info(f"Salon {room_id} supprimé")
        except Exception as e:
            logger.error(f"Erreur suppression salon {room_id}: {e}")
    
    async def cleanup_rooms(self):
        """Supprime tous les salons de jeu à la fin de la partie."""
        logger.info("Suppression des salons de jeu...")
        
        rooms_to_delete = [
            self.village_room,
            self.wolves_room,
            self.couple_room,
            self.dead_room
        ]
        
        for room_id in rooms_to_delete:
            if room_id:
                await self.delete_room(room_id)
        
        # Réinitialiser les IDs
        self.village_room = None
        self.wolves_room = None
        self.couple_room = None
        self.dead_room = None
        
        logger.info("Salons de jeu supprimés")
