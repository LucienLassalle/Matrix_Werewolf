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
        
        # Cas spécial : Loup Bavard → afficher le mot imposé
        if role.name == "Loup Bavard" and hasattr(role, 'word_to_say') and role.word_to_say:
            message += f"\n🗣️ **Votre mot imposé pour demain : {role.word_to_say}**\n"
            message += "Vous DEVEZ prononcer ce mot dans le salon du village demain, sinon vous mourrez !\n"
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_death_notification(self, user_id: str, role: Role):
        """Notifie un joueur de sa mort."""
        message = "💀 **Vous êtes mort !**\n\n"
        message += f"Votre rôle était: **{role.name}**\n\n"
        
        # Message spécial pour le chasseur
        if role.name == "Chasseur":
            message += "🎯 En tant que Chasseur, vous pouvez encore éliminer quelqu'un !\n"
            message += "Utilisez `/tuer {pseudo}` pour tirer sur votre cible.\n\n"
        
        message += "Vous avez été ajouté au **Cimetière** où vous pouvez discuter avec les autres morts."
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_couple_notification(self, player1, player2):
        """Notifie les deux amoureux de leur couple avec l'identité de leur partenaire.
        
        Args:
            player1: Premier joueur du couple (objet Player).
            player2: Second joueur du couple (objet Player).
        """
        role1_name = player1.role.name if player1.role else "Inconnu"
        role2_name = player2.role.name if player2.role else "Inconnu"
        
        # Message pour player1
        msg1 = "💕 **Cupidon vous a choisi !**\n\n"
        msg1 += f"Vous êtes en couple avec **{player2.pseudo}** (_{role2_name}_).\n"
        msg1 += "Vous avez été ajouté à un salon privé pour communiquer.\n\n"
        msg1 += "⚠️ **Important:**\n"
        msg1 += "• Si votre partenaire meurt, vous mourez aussi\n"
        msg1 += "• Si vous êtes les 2 derniers survivants, vous gagnez ensemble\n"
        
        # Message pour player2
        msg2 = "💕 **Cupidon vous a choisi !**\n\n"
        msg2 += f"Vous êtes en couple avec **{player1.pseudo}** (_{role1_name}_).\n"
        msg2 += "Vous avez été ajouté à un salon privé pour communiquer.\n\n"
        msg2 += "⚠️ **Important:**\n"
        msg2 += "• Si votre partenaire meurt, vous mourez aussi\n"
        msg2 += "• Si vous êtes les 2 derniers survivants, vous gagnez ensemble\n"
        
        await self.room_manager.send_dm(player1.user_id, msg1)
        await self.room_manager.send_dm(player2.user_id, msg2)
    
    async def send_conversion_notification(self, user_id: str, new_role: Role):
        """Notifie un joueur de sa conversion (ex: Loup Blanc → Loup)."""
        message = "🔄 **Votre rôle a changé !**\n\n"
        message += f"Vous êtes maintenant: **{new_role.name}**\n\n"
        message += new_role.description + "\n\n"
        message += self._format_win_condition(new_role.team)
        
        await self.room_manager.send_dm(user_id, message)
    
    def _format_role_message(self, role: Role) -> str:
        """Formate le message d'annonce de rôle avec mini-tutoriel."""
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
        
        # Mini-tutoriel avec exemples concrets
        tutorial = self._get_role_tutorial(role)
        if tutorial:
            message += f"\n💡 **Comment jouer :**\n{tutorial}"
        
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
    
    def _get_role_tutorial(self, role: Role) -> str:
        """Retourne un mini-tutoriel avec exemples concrets pour chaque rôle."""
        tutorials = {
            "Loup-Garou": (
                "🐺 Chaque nuit, rendez-vous dans le **salon des loups** pour "
                "discuter avec la meute et choisir une victime.\n"
                "Exemple : `/vote Alice` dans le salon des loups.\n"
                "Le jour, restez discret dans le village et essayez de ne pas "
                "éveiller les soupçons !"
            ),
            "Loup Voyant": (
                "🔮 Vous pouvez espionner le rôle d'un joueur **avant** de voter "
                "avec la meute.\n"
                "Exemple : `/voyante Bob` (en DM) pour voir son rôle.\n"
                "Puis `/lg` (en DM) pour redevenir loup normal et voter.\n"
                "⚠️ Si vous votez avec la meute, vous perdez votre voyance cette nuit."
            ),
            "Loup Blanc": (
                "⚪ Vous jouez avec les loups MAIS votre objectif est d'être le "
                "**dernier survivant**.\n"
                "Une nuit sur deux, vous pouvez éliminer un joueur (même un loup) "
                "en secret.\n"
                "Exemple : `/tuer Charlie` (en DM, les nuits impaires).\n"
                "🎯 Stratégie : éliminez les loups quand il ne reste que peu de villageois."
            ),
            "Loup Noir": (
                "🖤 Vous pouvez convertir la cible des loups en loup-garou au lieu "
                "de la tuer (**une seule fois** dans la partie).\n"
                "Exemple : `/convertir` (en DM) après le vote des loups.\n"
                "💡 Gardez cette capacité pour un moment stratégique !"
            ),
            "Loup Bavard": (
                "🗣️ Chaque nuit, un **mot imposé** vous est attribué. Vous devez "
                "le prononcer dans le village pendant le jour, sinon vous mourez !\n"
                "💡 Intégrez le mot naturellement dans la conversation pour ne pas "
                "être repéré."
            ),
            "Voyante": (
                "👁️ Chaque nuit, vous pouvez espionner le rôle exact d'un joueur.\n"
                "Exemple : `/voyante Alice` (en DM au bot).\n"
                "💡 Le jour, partagez vos découvertes avec prudence — les loups "
                "vous cibleront si vous vous dévoilez trop vite !"
            ),
            "Voyante d'Aura": (
                "✨ Comme la Voyante, mais vous voyez l'**aura** (Gentil/Méchant) "
                "au lieu du rôle exact.\n"
                "Exemple : `/voyante Bob` (en DM au bot).\n"
                "💡 Utile pour détecter les loups sans connaître les rôles précis."
            ),
            "Sorcière": (
                "🧪 Vous avez **2 potions** (une seule utilisation chaque) :\n"
                "• **Vie** : sauver la victime des loups → `/sorciere-sauve Alice`\n"
                "• **Mort** : empoisonner quelqu'un → `/sorciere-tue Bob`\n"
                "Vous pouvez utiliser les deux la même nuit !\n"
                "💡 Le bot vous prévient qui les loups ont ciblé."
            ),
            "Cupidon": (
                "💘 La première nuit, vous mariez deux joueurs.\n"
                "Exemple : `/cupidon Alice Bob` (en DM).\n"
                "Les amoureux meurent ensemble. S'ils sont les derniers, "
                "ils gagnent (et vous aussi !).\n"
                "💡 Mariez un loup et un villageois pour créer un dilemme intéressant."
            ),
            "Chasseur": (
                "🔫 Quand vous mourez, vous emportez quelqu'un avec vous !\n"
                "Exemple : `/tuer Charlie` (en DM) après votre mort.\n"
                "⚠️ Vous avez peu de temps pour agir après votre mort."
            ),
            "Garde": (
                "🛡️ Chaque nuit, vous protégez un joueur contre les loups.\n"
                "Exemple : `/garde Alice` (en DM).\n"
                "⚠️ Vous ne pouvez pas protéger le même joueur deux nuits de suite.\n"
                "💡 Protégez les joueurs importants (Voyante, Sorcière si dévoilés)."
            ),
            "Petite Fille": (
                "👀 Vous espionnez les loups ! Chaque nuit, vous recevez "
                "automatiquement leurs messages (potentiellement brouillés).\n"
                "⚠️ Pas de commande à faire, c'est passif.\n"
                "💡 Attention à ne pas dévoiler cette info — les loups vous "
                "élimineront en priorité !"
            ),
            "Corbeau": (
                "🪶 Chaque nuit, vous maudissez un joueur : il reçoit **+2 votes** "
                "pour le prochain vote du village.\n"
                "Exemple : `/corbeau Alice` (en DM).\n"
                "💡 Ciblez les joueurs que vous soupçonnez d'être loups pour "
                "les faire éliminer plus facilement."
            ),
            "Dictateur": (
                "⚔️ Une fois dans la partie (de jour), vous pouvez éliminer un "
                "joueur sans vote.\n"
                "Exemple : `/dictateur Bob` (en DM).\n"
                "⚠️ Si la cible est un villageois, VOUS mourez aussi !\n"
                "💡 Soyez sûr de votre cible avant d'utiliser ce pouvoir."
            ),
            "Voleur": (
                "🎭 La première nuit, vous pouvez :\n"
                "• Tirer 2 cartes : `/voleur-tirer` (en DM)\n"
                "• Choisir une carte : `/voleur-choisir 1` ou `/voleur-choisir 2`\n"
                "• OU échanger avec un joueur : `/voleur-echange Alice`\n"
                "💡 Vous gardez le rôle choisi pour le reste de la partie."
            ),
            "Enfant Sauvage": (
                "🧒 La première nuit, choisissez un **mentor**.\n"
                "Exemple : `/enfant Alice` (en DM).\n"
                "Si votre mentor meurt, vous devenez **Loup-Garou** !\n"
                "💡 Choisissez quelqu'un qui a des chances de survivre longtemps."
            ),
            "Médium": (
                "🔮 Chaque nuit, vous pouvez communiquer avec un joueur mort.\n"
                "Exemple : `/medium Alice` (en DM).\n"
                "💡 Les morts connaissent les rôles de tous — ils peuvent "
                "vous donner des informations précieuses !"
            ),
            "Mercenaire": (
                "🎯 Une cible vous est assignée automatiquement au début de la partie.\n"
                "Si votre cible est éliminée par le vote du village dans les 2 "
                "premiers jours, vous gagnez une vie supplémentaire !\n"
                "💡 Orientez le vote vers votre cible sans paraître suspect."
            ),
            "Mentaliste": (
                "🧠 Quelques heures avant la fin du vote, vous recevez "
                "automatiquement une indication : le joueur le plus voté est-il "
                "**côté village** ou **côté loups** ?\n"
                "💡 Partagez cette info pour orienter le vote... ou gardez-la "
                "pour vous si vous pensez que les loups vous écoutent."
            ),
            "Montreur d'Ours": (
                "🐻 Chaque matin, si un **loup** est assis à côté de vous "
                "(joueurs adjacents dans la liste), l'ours grogne et le village "
                "est prévenu.\n"
                "⚠️ C'est automatique, pas de commande. Mais les loups sauront "
                "que vous êtes le Montreur d'Ours !"
            ),
            "Villageois": (
                "🏘️ Vous n'avez pas de pouvoir spécial, mais votre vote est crucial !\n"
                "Exemple : `/vote Alice` dans le salon du village pendant la phase de vote.\n"
                "💡 Observez les discussions, repérez les comportements suspects "
                "et votez pour éliminer les loups !"
            ),
            "Idiot": (
                "🤪 Si vous êtes éliminé par le vote du village, vous survivez ! "
                "Mais vous perdez votre droit de vote.\n"
                "💡 Vous pouvez continuer à participer aux discussions et "
                "influencer les autres joueurs."
            ),
        }
        return tutorials.get(role.name, "")
