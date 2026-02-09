"""Gestionnaire de notifications pour les joueurs."""

import logging
from typing import Optional

from matrix_bot.room_manager import RoomManager
from models.role import Role
from models.enums import Team

logger = logging.getLogger(__name__)


class NotificationManager:
    """Gère l'envoi de notifications aux joueurs."""
    
    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager
    
    async def send_role_assignment(self, user_id: str, role: Role):
        """Envoie les informations de rôle à un joueur."""
        message = self._format_role_message(role)
        await self.room_manager.send_dm(user_id, message)
        logger.info(f"Rôle envoyé à {user_id}: {role.name}")
    
    async def send_night_reminder(self, user_id: str, role: Role):
        """Rappelle les actions nocturnes possibles."""
        if not role.can_act_at_night():
            return
        
        message = "🌙 **Rappel de nuit**\n\n"
        message += f"En tant que **{role.name}**, vous pouvez:\n\n"
        
        # Actions spécifiques selon le rôle
        actions = self._get_role_night_actions(role)
        if actions:
            for action in actions:
                message += f"• {action}\n"
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_death_notification(self, user_id: str, role: Role):
        """Notifie un joueur de sa mort."""
        message = "💀 **Vous êtes mort !**\n\n"
        message += f"Votre rôle était: **{role.name}**\n\n"
        
        # Message spécial pour le chasseur
        if role.name == "Chasseur":
            message += "🎯 En tant que Chasseur, vous pouvez encore éliminer quelqu'un !\n"
            message += "Utilisez `/shoot {pseudo}` pour tirer sur votre cible.\n\n"
        
        message += "Vous avez été ajouté au **Cimetière** où vous pouvez discuter avec les autres morts."
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_couple_notification(self, user_id_1: str, user_id_2: str):
        """Notifie les deux amoureux de leur couple."""
        message = "💕 **Cupidon vous a choisi !**\n\n"
        message += "Vous êtes maintenant en couple avec un autre joueur.\n"
        message += "Vous avez été ajouté à un salon privé pour communiquer.\n\n"
        message += "⚠️ **Important:**\n"
        message += "• Si votre partenaire meurt, vous mourez aussi\n"
        message += "• Si vous êtes les 2 derniers survivants, vous gagnez ensemble\n"
        
        await self.room_manager.send_dm(user_id_1, message)
        await self.room_manager.send_dm(user_id_2, message)
    
    async def send_conversion_notification(self, user_id: str, new_role: Role):
        """Notifie un joueur de sa conversion (ex: Loup Blanc → Loup)."""
        message = "🔄 **Votre rôle a changé !**\n\n"
        message += f"Vous êtes maintenant: **{new_role.name}**\n\n"
        message += new_role.description + "\n\n"
        message += self._format_win_condition(new_role.team)
        
        await self.room_manager.send_dm(user_id, message)
    
    def _format_role_message(self, role: Role) -> str:
        """Formate le message d'annonce de rôle."""
        # Emoji selon l'équipe
        emoji = {
            Team.GENTIL: "🏘️",
            Team.MECHANT: "🐺",
            Team.COUPLE: "💕"
        }.get(role.team, "❓")
        
        message = f"{emoji} **Votre rôle: {role.name}**\n\n"
        message += f"📖 **Description:**\n{role.description}\n\n"
        
        # Équipe et condition de victoire
        message += self._format_win_condition(role.team) + "\n\n"
        
        # Pouvoirs
        if role.can_act_at_night():
            message += "🌙 **Pouvoirs nocturnes:**\n"
            actions = self._get_role_night_actions(role)
            for action in actions:
                message += f"• {action}\n"
            message += "\n"
        
        # Commandes disponibles
        message += "⌨️ **Commandes disponibles:**\n"
        commands = self._get_role_commands(role)
        for cmd in commands:
            message += f"• {cmd}\n"
        
        return message
    
    def _format_win_condition(self, team: Team) -> str:
        """Formate la condition de victoire."""
        conditions = {
            Team.GENTIL: "🎯 **Victoire:** Éliminer tous les loups-garous",
            Team.MECHANT: "🎯 **Victoire:** Éliminer tous les villageois",
            Team.COUPLE: "🎯 **Victoire:** Être les 2 derniers survivants"
        }
        return conditions.get(team, "")
    
    def _get_role_night_actions(self, role: Role) -> list:
        """Retourne la liste des actions nocturnes d'un rôle."""
        actions_map = {
            "Loup-Garou": ["Voter avec la meute pour tuer un villageois (`/vote {pseudo}`)"],
            "Loup Voyant": [
                "Espionner le rôle d'un joueur (`/voyante {pseudo}`)",
                "Abandonner la voyance pour voter avec la meute (`/lg`)"
            ],
            "Loup Blanc": [
                "Voter avec la meute (`/vote {pseudo}`)",
                "Tuer un joueur seul, une nuit sur deux (`/tuer {pseudo}`)"
            ],
            "Loup Noir": [
                "Voter avec la meute (`/vote {pseudo}`)",
                "Convertir la cible des loups en loup (`/convertir`)"
            ],
            "Loup Bavard": [
                "Voter avec la meute (`/vote {pseudo}`)",
                "⚠️ Vous devez utiliser le mot imposé dans vos messages du jour !"
            ],
            "Voyante": ["Voir le rôle d'un joueur (`/voyante {pseudo}`)"],
            "Voyante d'Aura": ["Voir l'aura (Gentil/Méchant/Neutre) d'un joueur (`/voyante {pseudo}`)"],
            "Sorcière": [
                "Sauver la victime des loups (`/sorciere-sauve {pseudo}`)",
                "Empoisonner un joueur (`/sorciere-tue {pseudo}`)",
                "💡 Vous pouvez utiliser les deux potions la même nuit"
            ],
            "Cupidon": ["Marier deux joueurs la première nuit (`/cupidon {pseudo1} {pseudo2}`)"],
            "Garde": ["Protéger un joueur des loups (`/garde {pseudo}`)"],
            "Petite Fille": ["Espionner les loups (passif — vous recevez leurs messages en DM)"],
            "Montreur d'Ours": ["L'ours grogne automatiquement au réveil si un loup est voisin"],
            "Corbeau": ["Ajouter 2 votes contre quelqu'un pour le vote du lendemain (`/corbeau {pseudo}`)"],
            "Médium": ["Communiquer avec un joueur mort (`/medium {pseudo}`)"],
            "Enfant Sauvage": ["Choisir un mentor la première nuit (`/enfant {pseudo}`)"],
            "Voleur": [
                "Tirer 2 cartes (`/voleur-tirer`)",
                "Choisir une carte tirée (`/voleur-choisir 1` ou `/voleur-choisir 2`)",
                "Échanger avec un joueur (`/voleur-echange {pseudo}`)"
            ]
        }
        
        return actions_map.get(role.name, [])
    
    def _get_role_commands(self, role: Role) -> list:
        """Retourne la liste des commandes disponibles pour un rôle."""
        commands = []
        
        # Commandes communes
        commands.append("`/vote {pseudo}` — Voter pendant la phase de vote du village")
        
        # Commandes spécifiques
        role_commands = {
            "Loup-Garou": ["`/vote {pseudo}` — Voter la nuit avec la meute (dans le salon loups)"],
            "Loup Voyant": [
                "`/voyante {pseudo}` — Espionner le rôle d'un joueur",
                "`/lg` — Abandonner la voyance et voter avec la meute"
            ],
            "Loup Blanc": [
                "`/vote {pseudo}` — Voter avec la meute",
                "`/tuer {pseudo}` — Tuer un joueur seul (1 nuit / 2)"
            ],
            "Loup Noir": [
                "`/vote {pseudo}` — Voter avec la meute",
                "`/convertir` — Convertir la cible des loups en loup"
            ],
            "Loup Bavard": ["`/vote {pseudo}` — Voter avec la meute"],
            "Voyante": ["`/voyante {pseudo}` — Voir le rôle d'un joueur"],
            "Voyante d'Aura": ["`/voyante {pseudo}` — Voir l'aura d'un joueur"],
            "Sorcière": [
                "`/sorciere-sauve {pseudo}` — Sauver un joueur (1 seule fois dans la partie)",
                "`/sorciere-tue {pseudo}` — Empoisonner un joueur (1 seule fois dans la partie)"
            ],
            "Cupidon": ["`/cupidon {pseudo1} {pseudo2}` — Marier deux joueurs (nuit 1)"],
            "Chasseur": ["`/tuer {pseudo}` — Tirer sur un joueur après votre mort"],
            "Garde": ["`/garde {pseudo}` — Protéger un joueur (pas le même 2 nuits de suite)"],
            "Corbeau": ["`/corbeau {pseudo}` — Ajouter 2 votes contre quelqu'un"],
            "Dictateur": ["`/dictateur {pseudo}` — Éliminer quelqu'un sans vote (1 fois, de jour)"],
            "Voleur": [
                "`/voleur-tirer` — Tirer 2 cartes supplémentaires",
                "`/voleur-choisir {1|2}` — Choisir une carte tirée",
                "`/voleur-echange {pseudo}` — Échanger son rôle avec un joueur"
            ],
            "Enfant Sauvage": ["`/enfant {pseudo}` — Choisir un mentor (nuit 1)"],
            "Mercenaire": ["Pas de commande — votre cible vous est assignée automatiquement"],
            "Mentaliste": ["Pas de commande — le résultat du vote vous est communiqué automatiquement"],
            "Médium": ["`/medium {pseudo}` — Communiquer avec un mort (la nuit)"]
        }
        
        if role.name in role_commands:
            commands.extend(role_commands[role.name])
        
        return commands
