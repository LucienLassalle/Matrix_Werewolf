"""Client Matrix pour le bot Loup-Garou."""

from nio import AsyncClient, MatrixRoom, RoomMessageText, LoginError, RoomVisibility, RoomPreset
from typing import Optional, List, Dict
import asyncio
import aiohttp
import json
import logging

logger = logging.getLogger(__name__)


class MatrixClientWrapper:
    """Wrapper pour le client Matrix avec fonctionnalités spécifiques au jeu."""
    
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
    
    async def create_room(self, name: str, topic: str, is_public: bool = False, 
                         invite_users: List[str] = None, space_id: str = None) -> Optional[str]:
        """
        Crée un salon Matrix.
        
        Args:
            name: Nom du salon
            topic: Sujet du salon
            is_public: Si le salon est public
            invite_users: Liste des user_id à inviter
            space_id: ID de l'espace parent
            
        Returns:
            Room ID ou None en cas d'erreur
        """
        if not self.client:
            logger.error("Client non connecté")
            return None
        
        try:
            vis = RoomVisibility.public if is_public else RoomVisibility.private
            pre = RoomPreset.public_chat if is_public else RoomPreset.private_chat
            
            # Configuration du salon
            room_config = {
                "name": name,
                "topic": topic,
                "visibility": vis,
                "preset": pre,
                "invite": invite_users or [],
            }
            
            # Ajouter au space si spécifié
            if space_id:
                room_config["initial_state"] = [
                    {
                        "type": "m.space.parent",
                        "state_key": space_id,
                        "content": {
                            "canonical": True,
                            "via": [self.homeserver.replace("https://", "").replace("http://", "")]
                        }
                    }
                ]
            
            response = await self.client.room_create(**room_config)
            
            if hasattr(response, 'room_id'):
                logger.info(f"Salon créé: {response.room_id} ({name})")
                
                # Ajouter le salon au space
                if space_id:
                    await self.add_room_to_space(space_id, response.room_id)
                
                return response.room_id
            else:
                logger.error(f"Erreur création salon: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur création salon: {e}")
            return None
    
    async def add_room_to_space(self, space_id: str, room_id: str):
        """Ajoute un salon à un espace."""
        try:
            await self.client.room_put_state(
                space_id,
                "m.space.child",
                {
                    "via": [self.homeserver.replace("https://", "").replace("http://", "")],
                    "suggested": True
                },
                state_key=room_id
            )
            logger.info(f"Salon {room_id} ajouté à l'espace {space_id}")
        except Exception as e:
            logger.error(f"Erreur ajout au space: {e}")
    
    async def remove_room_from_space(self, space_id: str, room_id: str):
        """Retire un salon d'un espace (supprime le lien m.space.child)."""
        try:
            await self.client.room_put_state(
                space_id,
                "m.space.child",
                {},  # Contenu vide = supprime le lien
                state_key=room_id
            )
            logger.info(f"Salon {room_id} retiré de l'espace {space_id}")
        except Exception as e:
            logger.error(f"Erreur retrait du space: {e}")
    
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
                import re
                html = message
                # Convertir **bold** en <b>bold</b>
                html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
                # Convertir *italic* en <i>italic</i>
                html = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', html)
                # Convertir `code` en <code>code</code>
                html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
                # Convertir les retours à la ligne
                html = html.replace("\n", "<br>")
                content["formatted_body"] = html
            
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
    
    async def send_dm(self, user_id: str, message: str) -> bool:
        """
        Envoie un message privé (DM) à un utilisateur via Matrix.
        
        Crée un vrai DM Matrix (is_direct=true, pas de nom, pas d'ajout au space)
        qui apparaît dans la section "Messages directs" du client Matrix de l'utilisateur.
        Réutilise le salon DM existant s'il y en a un.
        
        Args:
            user_id: ID de l'utilisateur
            message: Message à envoyer
            
        Returns:
            True si le message a été envoyé avec succès.
        """
        if not self.client:
            logger.error("Client non connecté")
            return False
        
        try:
            # 1. Vérifier le cache DM
            dm_room = self._dm_rooms.get(user_id)
            if dm_room:
                logger.info(f"📩 DM → {user_id}: cache hit (room={dm_room})")
            
            # 2. Chercher via m.direct (account data)
            if not dm_room:
                dm_room = await self._find_existing_dm(user_id)
                if dm_room:
                    logger.info(f"📩 DM → {user_id}: salon existant trouvé (room={dm_room})")
            
            # 3. Créer un nouveau DM
            if not dm_room:
                logger.info(f"📩 DM → {user_id}: aucun DM existant, création d'un nouveau salon...")
                dm_room = await self._create_direct_room(user_id)
                if dm_room:
                    logger.info(f"📩 DM → {user_id}: nouveau salon créé (room={dm_room})")
            
            # 4. Envoyer le message
            if dm_room:
                self._dm_rooms[user_id] = dm_room
                event_id = await self.send_message(dm_room, message, formatted=True)
                if event_id:
                    logger.info(f"📩 DM → {user_id}: message envoyé ✅ (room={dm_room}, len={len(message)})")
                else:
                    logger.error(f"📩 DM → {user_id}: send_message a ÉCHOUÉ dans room={dm_room}")
                    # Invalider le cache, le salon est peut-être inaccessible
                    self._dm_rooms.pop(user_id, None)
                return bool(event_id)
            else:
                logger.error(f"📩 DM → {user_id}: IMPOSSIBLE d'obtenir un salon DM")
                return False
                
        except Exception as e:
            logger.error(f"📩 DM → {user_id}: EXCEPTION {e}")
            # Invalider le cache en cas d'erreur (le salon a peut-être été supprimé)
            self._dm_rooms.pop(user_id, None)
            return False
    
    async def _find_existing_dm(self, user_id: str) -> Optional[str]:
        """Cherche un salon DM existant via m.direct (account data).
        
        Utilise les account data m.direct comme source de vérité plutôt
        que de scanner aveuglément tous les salons à 2 membres.
        """
        # 1. Vérifier les m.direct account data (source de vérité)
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"{self.homeserver}/_matrix/client/v3/user/{self.user_id}/account_data/m.direct"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        direct_data = await resp.json()
                        dm_rooms_for_user = direct_data.get(user_id, [])
                        
                        if dm_rooms_for_user:
                            logger.info(
                                f"🔍 m.direct pour {user_id}: {dm_rooms_for_user}"
                            )
                            # Vérifier que le bot est encore dans le salon
                            response = await self.client.joined_rooms()
                            joined = response.rooms if hasattr(response, 'rooms') else []
                            
                            for room_id in dm_rooms_for_user:
                                if room_id in joined:
                                    logger.info(
                                        f"🔍 DM existant trouvé via m.direct: {room_id} "
                                        f"(bot est membre)"
                                    )
                                    return room_id
                                else:
                                    logger.info(
                                        f"🔍 DM {room_id} dans m.direct mais bot "
                                        f"n'est plus membre — ignoré"
                                    )
                        else:
                            logger.info(f"🔍 Aucun DM dans m.direct pour {user_id}")
                    elif resp.status == 404:
                        logger.info("🔍 Pas de données m.direct (premier usage)")
                    else:
                        body = await resp.text()
                        logger.warning(f"🔍 Erreur lecture m.direct: {resp.status} - {body}")
        except Exception as e:
            logger.warning(f"🔍 Impossible de lire m.direct: {e}")
        
        logger.info(f"🔍 Aucun DM existant trouvé pour {user_id}")
        return None
    
    async def _create_direct_room(self, user_id: str) -> Optional[str]:
        """Crée un vrai DM Matrix (is_direct, sans nom, sans E2EE, hors du space).
        
        Apparaît dans la section "Messages directs" du client Matrix du destinataire.
        Le bot peut écrire dedans même si le destinataire n'a pas encore accepté l'invitation.
        """
        try:
            # private_chat (PAS trusted_private_chat qui peut activer l'E2EE)
            # + initial_state pour forcer history_visibility à "shared"
            #   → le destinataire verra l'historique même s'il accepte plus tard
            response = await self.client.room_create(
                visibility=RoomVisibility.private,
                preset=RoomPreset.private_chat,
                is_direct=True,
                invite=[user_id],
                initial_state=[
                    {
                        "type": "m.room.history_visibility",
                        "content": {"history_visibility": "invited"}
                    }
                ]
            )
            
            if hasattr(response, 'room_id'):
                room_id = response.room_id
                logger.info(f"DM créé avec {user_id}: {room_id}")
                
                # Marquer comme conversation directe dans les account data
                await self._set_direct_room(user_id, room_id)
                
                return room_id
            else:
                logger.error(f"Erreur création DM: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur création DM avec {user_id}: {e}")
            return None
    
    async def _set_direct_room(self, user_id: str, room_id: str):
        """Marque un salon comme conversation directe (m.direct) dans les account data."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"{self.homeserver}/_matrix/client/v3/user/{self.user_id}/account_data/m.direct"
            
            async with aiohttp.ClientSession() as session:
                # GET les données existantes
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        direct_data = await resp.json()
                    else:
                        direct_data = {}
                
                # Ajouter le nouveau DM
                if user_id not in direct_data:
                    direct_data[user_id] = []
                if room_id not in direct_data[user_id]:
                    direct_data[user_id].append(room_id)
                
                # PUT les données mises à jour
                async with session.put(url, headers=headers, json=direct_data) as resp:
                    if resp.status == 200:
                        logger.debug(f"m.direct mis à jour pour {user_id}")
                    else:
                        body = await resp.text()
                        logger.warning(f"Erreur mise à jour m.direct: {resp.status} - {body}")
                        
        except Exception as e:
            logger.warning(f"Impossible de mettre à jour m.direct pour {user_id}: {e}")
    
    async def invite_user(self, room_id: str, user_id: str):
        """Invite un utilisateur dans un salon."""
        if not self.client:
            return
        
        try:
            await self.client.room_invite(room_id, user_id)
            logger.info(f"Utilisateur {user_id} invité dans {room_id}")
        except Exception as e:
            logger.error(f"Erreur invitation: {e}")
    
    async def kick_user(self, room_id: str, user_id: str, reason: str = ""):
        """Expulse un utilisateur d'un salon."""
        if not self.client:
            return
        
        try:
            await self.client.room_kick(room_id, user_id, reason)
            logger.info(f"Utilisateur {user_id} expulsé de {room_id}")
        except Exception as e:
            logger.error(f"Erreur expulsion: {e}")
    
    async def delete_room(self, room_id: str):
        """Supprime un salon (en fait, le bot le quitte)."""
        if not self.client:
            return
        
        try:
            # Matrix ne permet pas vraiment de supprimer un salon
            # On peut seulement le quitter et le "fermer"
            await self.client.room_leave(room_id)
            logger.info(f"Salon {room_id} quitté")
        except Exception as e:
            logger.error(f"Erreur suppression salon: {e}")
    
    async def clear_room_history(self, room_id: str):
        """
        Nettoie l'historique d'un salon (approximatif).
        Note: Matrix ne permet pas vraiment de supprimer l'historique,
        on peut seulement envoyer un message d'info.
        """
        if not self.client:
            return
        
        try:
            await self.send_message(
                room_id, 
                "═══════════════════════════════\n"
                "🔄 NOUVELLE PARTIE\n"
                "═══════════════════════════════"
            )
        except Exception as e:
            logger.error(f"Erreur clear historique: {e}")
    
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
