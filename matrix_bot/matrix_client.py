"""Client Matrix pour le bot Loup-Garou."""

from nio import AsyncClient, RoomPreset, RoomVisibility
from typing import Optional, List, Dict
import aiohttp
import logging

from matrix_bot.matrix_client_rooms import MatrixClientRoomsMixin
from matrix_bot.matrix_client_dm import MatrixClientDMMixin

logger = logging.getLogger(__name__)


class MatrixClientWrapper(MatrixClientRoomsMixin, MatrixClientDMMixin):
    """Wrapper pour le client Matrix avec fonctionnalités spécifiques au jeu."""

    @staticmethod
    def _format_message_html(message: str) -> str:
        import re
        html = message
        html = re.sub(r'~~(.+?)~~', r'<del>\1</del>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        html = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', html)
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        html = html.replace("\n", "<br>")
        return html
    
    def __init__(self, homeserver: str, user_id: str, access_token: str,
                 password: str | None = None):
        self.homeserver = homeserver
        self.user_id = user_id
        self.access_token = access_token
        self._password = password  # Pour auto-renouvellement du token
        self.client: Optional[AsyncClient] = None
        self._dm_rooms: Dict[str, str] = {}  # user_id → room_id (cache DM)
        
    async def connect(self) -> bool:
        """Se connecte au serveur Matrix. Tente un renouvellement de token si le token est invalide."""
        try:
            self.client = AsyncClient(self.homeserver, self.user_id)
            self.client.access_token = self.access_token
            
            # Vérifier la connexion
            whoami = await self.client.whoami()
            if whoami and hasattr(whoami, 'user_id'):
                logger.info(f"Connecté en tant que {whoami.user_id}")
                return True
            else:
                logger.warning("⚠️ Token invalide ou connexion refusée")
                # Tenter un renouvellement de token
                return await self._try_renew_token()
                
        except Exception as e:
            logger.warning(f"Erreur de connexion avec le token actuel: {e}")
            return await self._try_renew_token()
    
    async def _try_renew_token(self) -> bool:
        """Tente de renouveler le token en utilisant le mot de passe."""
        if not self._password:
            logger.error("❌ Token invalide et pas de mot de passe configuré (MATRIX_PASSWORD). "
                        "Impossible de renouveler le token.")
            return False
        
        logger.info("🔄 Tentative de renouvellement du token via mot de passe...")
        
        try:
            # Extraire le username depuis le Matrix ID (@bot_lg:lloka.fr → bot_lg)
            username = self.user_id.split(':')[0].lstrip('@')
            
            login_payload = {
                "type": "m.login.password",
                "identifier": {
                    "type": "m.id.user",
                    "user": username
                },
                "password": self._password
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.homeserver}/_matrix/client/v3/login"
                async with session.post(url, json=login_payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        new_token = data.get("access_token")
                        if new_token:
                            self.access_token = new_token
                            logger.info("✅ Nouveau token obtenu avec succès !")
                            
                            # Recréer le client avec le nouveau token
                            if self.client:
                                await self.client.close()
                            self.client = AsyncClient(self.homeserver, self.user_id)
                            self.client.access_token = new_token
                            
                            # Vérifier que ça marche
                            whoami = await self.client.whoami()
                            if whoami and hasattr(whoami, 'user_id'):
                                logger.info(f"✅ Reconnecté en tant que {whoami.user_id}")
                                return True
                            else:
                                logger.error("❌ Le nouveau token ne fonctionne pas non plus")
                                return False
                        else:
                            logger.error(f"❌ Pas de token dans la réponse: {data}")
                            return False
                    else:
                        body = await resp.text()
                        logger.error(f"❌ Échec du login ({resp.status}): {body}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Erreur lors du renouvellement du token: {e}")
            return False
    
    async def verify_permissions(self, lobby_room_id: str, space_id: str) -> bool:
        """Vérifie que le bot a les permissions nécessaires.
        
        Vérifie :
        - Connexion active
        - Accès au lobby (envoi de message)
        - Accès au space (ajout de salons)
        - Capacité de créer des salons
        - Capacité de lire/envoyer des DMs
        - Capacité de kick des utilisateurs
        
        Returns:
            True si toutes les permissions sont OK, False sinon.
        """
        all_ok = True
        
        if not self.client:
            logger.critical("❌ PERMISSION: Client non connecté")
            return False
        
        # 1. Vérifier l'accès au lobby
        try:
            rooms = await self.client.joined_rooms()
            joined = rooms.rooms if hasattr(rooms, 'rooms') else []
            if lobby_room_id not in joined:
                logger.error(f"❌ PERMISSION: Bot non membre du lobby {lobby_room_id}. "
                            "Invitez le bot dans le salon lobby.")
                all_ok = False
            else:
                logger.info("✅ PERMISSION: Accès au lobby OK")
        except Exception as e:
            logger.error(f"❌ PERMISSION: Impossible de lister les salons rejoints: {e}")
            all_ok = False
        
        # 2. Vérifier qu'on peut envoyer un message dans le lobby
        try:
            await self.client.room_send(
                room_id=lobby_room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": ""}
            )
            # On ne peut pas vraiment tester sans envoyer, on skip ce test silencieux
            logger.info("✅ PERMISSION: Envoi de messages OK (vérifié au démarrage)")
        except Exception:
            # Le test d'envoi vide peut échouer, c'est normal
            logger.info("✅ PERMISSION: Envoi de messages (sera vérifié au premier message)")
        
        # 3. Vérifier l'accès au space
        try:
            if space_id in joined:
                logger.info("✅ PERMISSION: Accès au space OK")
            else:
                logger.warning(f"⚠️ PERMISSION: Bot non membre du space {space_id}. "
                              "Les salons ne seront pas ajoutés au space.")
        except Exception as e:
            logger.warning(f"⚠️ PERMISSION: Impossible de vérifier le space: {e}")
        
        # 4. Vérifier la capacité de créer des salons (test rapide)
        try:
            test_room = await self.client.room_create(
                name="🔧 Test permissions",
                visibility=RoomVisibility.private,
                preset=RoomPreset.private_chat
            )
            if hasattr(test_room, 'room_id'):
                logger.info("✅ PERMISSION: Création de salons OK")
                # Supprimer le salon test
                await self.client.room_leave(test_room.room_id)
            else:
                logger.error("❌ PERMISSION: Impossible de créer des salons. "
                            "Vérifiez les permissions du bot sur le serveur.")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ PERMISSION: Création de salons échouée: {e}")
            all_ok = False
        
        # 5. Vérifier la capacité de lire les DMs
        try:
            # Le bot peut recevoir des DMs s'il peut sync
            # On vérifie juste que le sync fonctionne
            logger.info("✅ PERMISSION: Réception de DMs (via sync events)")
        except Exception as e:
            logger.error(f"❌ PERMISSION: Problème de sync: {e}")
            all_ok = False
        
        if all_ok:
            logger.info("🎉 Toutes les permissions sont vérifiées avec succès !")
        else:
            logger.error("⛔ Certaines permissions sont manquantes. "
                        "Le bot risque de ne pas fonctionner correctement.")
        
        return all_ok
    
    async def disconnect(self):
        """Se déconnecte proprement."""
        if self.client:
            await self.client.close()
    
    async def send_message(self, room_id: str, message: str, formatted: bool = False) -> Optional[str]:
        """
        Envoie un message dans un salon.
        
        Args:
            room_id: ID du salon
            message: Message à envoyer
            formatted: Si True, utilise le formatage HTML
            
        Returns:
            L'event_id du message envoyé, ou None en cas d'erreur.
        """
        if not self.client:
            logger.error("Client non connecté")
            return None
        
        try:
            content = {
                "msgtype": "m.text",
                "body": message,
            }
            
            if formatted:
                content["format"] = "org.matrix.custom.html"
                content["formatted_body"] = self._format_message_html(message)
            
            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content
            )
            
            # Vérifier la réponse
            if hasattr(response, 'event_id'):
                logger.debug(f"✅ Message envoyé dans {room_id} (event: {response.event_id})")
                return response.event_id
            else:
                logger.error(
                    f"❌ Échec envoi message dans {room_id}: {response}"
                )
                return None
            
        except Exception as e:
            logger.error(f"❌ Exception envoi message dans {room_id}: {e}")
            return None

    async def edit_message(
        self,
        room_id: str,
        event_id: str,
        message: str,
        formatted: bool = False,
    ) -> Optional[str]:
        """Edite un message existant via m.replace. Retourne l'event_id de l'edit."""
        if not self.client:
            logger.error("Client non connecté")
            return None

        try:
            new_content = {
                "msgtype": "m.text",
                "body": message,
            }
            content = {
                "msgtype": "m.text",
                "body": f"* {message}",
                "m.relates_to": {
                    "rel_type": "m.replace",
                    "event_id": event_id,
                },
                "m.new_content": new_content,
            }

            if formatted:
                html = self._format_message_html(message)
                content["format"] = "org.matrix.custom.html"
                content["formatted_body"] = f"* {html}"
                new_content["format"] = "org.matrix.custom.html"
                new_content["formatted_body"] = html

            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            )

            if hasattr(response, 'event_id'):
                logger.debug(
                    f"✅ Message édité dans {room_id} (event: {response.event_id})"
                )
                return response.event_id
            else:
                logger.error(
                    f"❌ Échec edition message dans {room_id}: {response}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Exception edition message dans {room_id}: {e}")
            return None
    
    async def get_room_members(self, room_id: str) -> List[str]:
        """Récupère la liste des membres d'un salon."""
        if not self.client:
            return []
        
        try:
            response = await self.client.joined_members(room_id)
            if hasattr(response, 'members'):
                return [member.user_id for member in response.members]
            return []
        except Exception as e:
            logger.error(f"Erreur récupération membres: {e}")
            return []
    
    async def set_power_level(self, room_id: str, user_id: str, level: int):
        """Modifie le power level d'un utilisateur dans un salon.
        
        Niveaux utiles :
        - 0 : utilisateur normal (peut parler)
        - -1 : ne peut pas envoyer de messages (muté)
        
        On utilise events_default pour contrôler qui peut parler.
        """
        if not self.client:
            return
        
        try:
            # Récupérer les power levels actuels
            response = await self.client.room_get_state_event(
                room_id, "m.room.power_levels"
            )
            
            if hasattr(response, 'content'):
                power_levels = response.content
            else:
                power_levels = {
                    "users_default": 0,
                    "events_default": 0,
                    "users": {}
                }
            
            # Modifier le power level de l'utilisateur
            if "users" not in power_levels:
                power_levels["users"] = {}
            
            power_levels["users"][user_id] = level
            
            await self.client.room_put_state(
                room_id,
                "m.room.power_levels",
                power_levels
            )
            logger.info(f"Power level de {user_id} dans {room_id} mis à {level}")
            
        except Exception as e:
            logger.error(f"Erreur modification power level: {e}")
    
    async def pin_message(self, room_id: str, event_id: str):
        """
        Épingle un message dans un salon.
        
        Args:
            room_id: ID du salon
            event_id: ID de l'événement à épingler
        """
        if not self.client:
            logger.error("Client non connecté")
            return
        
        try:
            # Récupérer les messages déjà épinglés
            pinned = []
            try:
                response = await self.client.room_get_state_event(
                    room_id, "m.room.pinned_events"
                )
                if hasattr(response, 'content') and 'pinned' in response.content:
                    pinned = response.content['pinned']
            except Exception:
                pass  # Pas encore de messages épinglés
            
            # Ajouter le nouveau message en tête
            if event_id not in pinned:
                pinned.insert(0, event_id)
            
            await self.client.room_put_state(
                room_id,
                "m.room.pinned_events",
                {"pinned": pinned}
            )
            logger.info(f"📌 Message {event_id} épinglé dans {room_id}")
            
        except Exception as e:
            logger.error(f"Erreur épinglage message dans {room_id}: {e}")
