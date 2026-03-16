"""Gestionnaire de notifications pour les joueurs."""

import logging
from typing import Optional

from matrix_bot.room_manager import RoomManager
from models.role import Role
from models.enums import Team

logger = logging.getLogger(__name__)


class NotificationManager:
    """Gère l'envoi de notifications aux joueurs."""
    
    def __init__(self, room_manager: RoomManager, command_prefix: str = "!"):
        self.room_manager = room_manager
        self.prefix = command_prefix
    
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
        
        # Cas spécial : Garde → rappeler qui a été protégé la nuit précédente
        if role.name == "Garde" and hasattr(role, 'last_protected') and role.last_protected:
            message += f"\n⚠️ Vous avez protégé **{role.last_protected.pseudo}** la nuit dernière — vous ne pouvez pas le/la protéger à nouveau cette nuit.\n"
        
        # Cas spécial : Sorcière → indiquer les potions restantes
        if role.name == "Sorcière":
            potions = []
            if hasattr(role, 'has_life_potion') and role.has_life_potion:
                potions.append("🧪 Potion de vie : **disponible**")
            elif hasattr(role, 'has_life_potion'):
                potions.append("🧪 Potion de vie : **utilisée**")
            if hasattr(role, 'has_death_potion') and role.has_death_potion:
                potions.append("☠️ Potion de mort : **disponible**")
            elif hasattr(role, 'has_death_potion'):
                potions.append("☠️ Potion de mort : **utilisée**")
            if potions:
                message += "\n" + "\n".join(potions) + "\n"
            message += "\n💡 Le bot vous informera de la cible des loups quand ils auront voté (au plus tard à la deadline des loups).\n"
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_death_notification(self, user_id: str, role: Role):
        """Notifie un joueur de sa mort et de son passage en mode spectateur."""
        message = "💀 **Vous êtes mort.e !**\n\n"
        
        # Message spécial pour le chasseur
        if role.name == "Chasseur":
            message += "🎯 En tant que Chasseur, vous pouvez encore éliminer quelqu'un !\n"
            message += f"Utilisez `{self.prefix}tuer {{pseudo}}` pour tirer sur votre cible.\n\n"
        
        # Mode spectateur
        message += "👻 **Mode spectateur activé**\n"
        message += "Vous pouvez toujours **lire** les messages du village"
        if role.can_vote_with_wolves():
            message += " et du salon des loups"
        message += ", mais vous ne pouvez plus écrire.\n\n"
        message += "Vous avez été ajouté au **Cimetière** où vous pouvez discuter avec les autres morts."
        
        await self.room_manager.send_dm(user_id, message)
    
    async def send_couple_notification(self, lovers: list):
        """Notifie les amoureux de leur couple avec l'identité des partenaires."""
        if not lovers:
            return

        for player in lovers:
            partners = [p for p in lovers if p != player]
            partners_text = ", ".join(
                f"**{p.pseudo}** ({p.role.name if p.role else 'Inconnu'})"
                for p in partners
            )

            msg = "💕 **Cupidon vous a choisi !**\n\n"
            msg += f"Vous êtes en couple avec {partners_text}.\n"
            msg += "Vous avez été ajouté à un salon privé pour communiquer.\n\n"
            msg += "⚠️ **Important:**\n"
            msg += "• Si un membre du couple meurt, vous mourez aussi\n"
            msg += "• Si vous êtes les derniers survivants, vous gagnez ensemble\n"

            await self.room_manager.send_dm(player.user_id, msg)
    
    async def send_mercenaire_target(self, user_id: str, target_pseudo: str):
        """Envoie la cible assignée au Mercenaire en DM."""
        message = "🎯 **Mission reçue !**\n\n"
        message += f"Votre cible est : **{target_pseudo}**\n\n"
        message += ("Vous avez **2 jours** pour faire éliminer cette personne "
                    "par le vote du village.\n")
        message += "Si vous réussissez, vous rejoignez le camp du village.\n"
        message += "Si vous échouez, vous mourrez.\n\n"
        message += "💡 Orientez le vote vers votre cible sans paraître suspect !"
        await self.room_manager.send_dm(user_id, message)
        logger.info(f"Cible du Mercenaire envoyée à {user_id}: {target_pseudo}")

    async def send_chasseur_de_tetes_target(self, user_id: str, target_pseudo: str):
        """Envoie la cible assignée au Chasseur de Têtes en DM."""
        message = "🎯 **Cible désignée !**\n\n"
        message += f"Votre cible est : **{target_pseudo}**\n\n"
        message += "Vous gagnez **seul** si le village élimine votre cible au vote "
        message += "(et que vous êtes toujours en vie).\n\n"
        message += "⚠️ Si votre cible meurt d'une autre façon (loups, sorcière, "
        message += "chasseur…), vous rejoignez **l'alliance du mal** : vous gagnez "
        message += "si les loups-garous remportent la partie.\n\n"
        message += "💡 Orientez subtilement le vote vers votre cible !"
        await self.room_manager.send_dm(user_id, message)
        logger.info(f"Cible du Chasseur de Têtes envoyée à {user_id}: {target_pseudo}")

    async def send_conversion_notification(self, user_id: str, new_role: Role):
        """Notifie un joueur de sa conversion (ex: Loup Blanc → Loup)."""
        message = "🔄 **Votre rôle a changé !**\n\n"
        message += f"Vous êtes maintenant: **{new_role.name}**\n\n"
        message += new_role.description + "\n\n"
        message += self._format_win_condition(new_role.team)
        
        await self.room_manager.send_dm(user_id, message)
    
    def _format_role_message(self, role: Role) -> str:
        """Formate le message d'annonce de rôle avec mini-tutoriel."""
        emoji = getattr(role, 'emoji', "❓")
        
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
            Team.COUPLE: "🎯 **Victoire:** Être les 2 derniers survivants",
            Team.NEUTRE: "🎯 **Victoire:** Condition spéciale (voir description)"
        }
        return conditions.get(team, "")
    
    def _get_role_night_actions(self, role: Role) -> list:
        """Retourne la liste des actions nocturnes d'un rôle."""
        p = self.prefix
        actions_map = {
            "Loup-Garou": [f"Voter avec la meute pour tuer un villageois (`{p}vote {{pseudo}}`)"],
            "Loup Voyant": [
                f"Espionner le rôle d'un joueur (`{p}voyante {{pseudo}}`)",
                f"Abandonner la voyance pour voter avec la meute (`{p}lg`)"
            ],
            "Loup Blanc": [
                f"Voter avec la meute (`{p}vote {{pseudo}}`)",
                f"Tuer un joueur seul, une nuit sur deux (`{p}tuer {{pseudo}}`)"
            ],
            "Loup Noir": [
                f"Voter avec la meute (`{p}vote {{pseudo}}`)",
                f"Convertir la cible des loups en loup (`{p}convertir`)"
            ],
            "Loup Bavard": [
                f"Voter avec la meute (`{p}vote {{pseudo}}`)",
                "⚠️ Vous devez utiliser le mot imposé dans vos messages du jour !"
            ],
            "Voyante": [f"Voir le rôle d'un joueur (`{p}voyante {{pseudo}}`)"],
            "Voyante d'Aura": [f"Voir l'aura (Gentil/Méchant/Neutre) d'un joueur (`{p}voyante {{pseudo}}`)"],
            "Sorcière": [
                f"Sauver la victime des loups (`{p}sorciere-sauve {{pseudo}}`)",
                f"Empoisonner un joueur (`{p}sorciere-tue {{pseudo}}`)",
                "💡 Vous pouvez utiliser les deux potions la même nuit"
            ],
            "Cupidon": [f"Marier deux joueurs la première nuit (`{p}cupidon {{pseudo1}} {{pseudo2}}`)"],
            "Garde": [f"Protéger un joueur des loups (`{p}garde {{pseudo}}`)"],
            "Petite Fille": ["Espionner les loups (passif — vous recevez leurs messages en DM)"],
            "Montreur d'Ours": ["L'ours grogne automatiquement au réveil si un loup est voisin"],
            "Corbeau": [f"Ajouter 2 votes contre quelqu'un pour le vote du lendemain (`{p}corbeau {{pseudo}}`)"],
            "Médium": [f"Communiquer avec un.e joueur.se mort.e (`{p}medium {{pseudo}}`)"],
            "Enfant Sauvage": [f"Choisir un mentor la première nuit (`{p}enfant {{pseudo}}`)"],
            "Voleur": [
                f"Tirer 2 cartes (`{p}voleur-tirer`)",
                f"Choisir une carte tirée (`{p}voleur-choisir 1` ou `{p}voleur-choisir 2`)",
                f"Échanger avec un joueur (`{p}voleur-echange {{pseudo}}`)"
            ],
            "Assassin": [f"Éliminer une cible (`{p}assassin {{pseudo}}`)"],
            "Pyromane": [
                f"Asperger jusqu'a deux cibles (`{p}pyromane {{pseudo}}`)",
                f"Embraser les cibles aspergees (`{p}pyromane-brule`)",
            ],
            "Détective": [f"Comparer deux joueurs (`{p}detective {{pseudo1}} {{pseudo2}}`)"],
            "Geôlier": [
                f"Interroger votre prisonnier (`{p}msg {{message}}`)",
                f"Exécuter le prisonnier (`{p}geolier-tuer`)",
            ]
        }
        
        return actions_map.get(role.name, [])
    
    def _get_role_commands(self, role: Role) -> list:
        """Retourne la liste des commandes disponibles pour un rôle."""
        p = self.prefix
        commands = []
        
        # Commandes communes
        commands.append(f"`{p}vote {{pseudo}}` — Voter pendant la phase de vote du village")
        
        # Commandes spécifiques
        role_commands = {
            "Loup-Garou": [f"`{p}vote {{pseudo}}` — Voter la nuit avec la meute (dans le salon loups)"],
            "Loup Voyant": [
                f"`{p}voyante {{pseudo}}` — Espionner le rôle d'un joueur",
                f"`{p}lg` — Abandonner la voyance et voter avec la meute"
            ],
            "Loup Blanc": [
                f"`{p}vote {{pseudo}}` — Voter avec la meute",
                f"`{p}tuer {{pseudo}}` — Tuer un joueur seul (1 nuit / 2)"
            ],
            "Loup Noir": [
                f"`{p}vote {{pseudo}}` — Voter avec la meute",
                f"`{p}convertir` — Convertir la cible des loups en loup"
            ],
            "Loup Bavard": [f"`{p}vote {{pseudo}}` — Voter avec la meute"],
            "Voyante": [f"`{p}voyante {{pseudo}}` — Voir le rôle d'un joueur"],
            "Voyante d'Aura": [f"`{p}voyante {{pseudo}}` — Voir l'aura d'un joueur"],
            "Sorcière": [
                f"`{p}sorciere-sauve {{pseudo}}` — Sauver un joueur (1 seule fois dans la partie)",
                f"`{p}sorciere-tue {{pseudo}}` — Empoisonner un joueur (1 seule fois dans la partie)"
            ],
            "Cupidon": [f"`{p}cupidon {{pseudo1}} {{pseudo2}}` — Marier deux joueurs (nuit 1)"],
            "Chasseur": [f"`{p}tuer {{pseudo}}` — Tirer sur un joueur après votre mort"],
            "Garde": [f"`{p}garde {{pseudo}}` — Protéger un joueur (pas le même 2 nuits de suite)"],
            "Corbeau": [f"`{p}corbeau {{pseudo}}` — Ajouter 2 votes contre quelqu'un"],
            "Dictateur": [f"`{p}dictateur {{pseudo}}` — Éliminer quelqu'un sans vote (1 fois, de jour)"],
            "Voleur": [
                f"`{p}voleur-tirer` — Tirer 2 cartes supplémentaires",
                f"`{p}voleur-choisir {{1|2}}` — Choisir une carte tirée",
                f"`{p}voleur-echange {{pseudo}}` — Échanger son rôle avec un joueur"
            ],
            "Enfant Sauvage": [f"`{p}enfant {{pseudo}}` — Choisir un mentor (nuit 1)"],
            "Mercenaire": ["Pas de commande — votre cible vous est assignée automatiquement"],
            "Chasseur de Têtes": ["Pas de commande — votre cible vous est désignée automatiquement"],
            "Mentaliste": ["Pas de commande — le résultat du vote vous est communiqué automatiquement"],
            "Médium": [f"`{p}medium {{pseudo}}` — Communiquer avec un.e joueur.se mort.e (la nuit)"],
            "Assassin": [f"`{p}assassin {{pseudo}}` — Éliminer une cible (la nuit)"],
            "Pyromane": [
                f"`{p}pyromane {{pseudo}}` — Asperger une cible (jusqu'a 2 par nuit)",
                f"`{p}pyromane-brule` — Embraser les cibles aspergees (1 fois)"
            ],
            "Détective": [f"`{p}detective {{pseudo1}} {{pseudo2}}` — Comparer deux joueurs (la nuit)"],
            "Geôlier": [
                f"`{p}geolier {{pseudo}}` — Choisir un prisonnier (de jour)",
                f"`{p}geolier-tuer` — Exécuter le prisonnier (1 fois, la nuit)",
                f"`{p}msg {{message}}` — Parler au prisonnier (DM)"
            ]
        }
        
        if role.name in role_commands:
            commands.extend(role_commands[role.name])
        
        return commands
    
    def _get_role_tutorial(self, role: Role) -> str:
        """Retourne un mini-tutoriel avec exemples concrets pour chaque rôle."""
        p = self.prefix
        tutorials = {
            "Loup-Garou": (
                "🐺 Chaque nuit, rendez-vous dans le **salon des loups** pour "
                "discuter avec la meute et choisir une victime.\n"
                f"Exemple : `{p}vote Alice` dans le salon des loups.\n"
                "Le jour, restez discret dans le village et essayez de ne pas "
                "éveiller les soupçons !"
            ),
            "Loup Voyant": (
                "🔮 Vous pouvez espionner le rôle d'un joueur **avant** de voter "
                "avec la meute.\n"
                f"Exemple : `{p}voyante Bob` (en DM) pour voir son rôle.\n"
                f"Puis `{p}lg` (en DM) pour redevenir loup normal et voter.\n"
                "⚠️ Si vous votez avec la meute, vous perdez votre voyance cette nuit."
            ),
            "Loup Blanc": (
                "⚪ Vous jouez avec les loups MAIS votre objectif est d'être le "
                "**dernier survivant**.\n"
                "Une nuit sur deux, vous pouvez éliminer un joueur (même un loup) "
                "en secret.\n"
                f"Exemple : `{p}tuer Charlie` (en DM, les nuits impaires).\n"
                "🎯 Stratégie : éliminez les loups quand il ne reste que peu de villageois."
            ),
            "Loup Noir": (
                "🖤 Vous pouvez convertir la cible des loups en loup-garou au lieu "
                "de la tuer (**une seule fois** dans la partie).\n"
                f"Exemple : `{p}convertir` (en DM) après le vote des loups.\n"
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
                f"Exemple : `{p}voyante Alice` (en DM au bot).\n"
                "💡 Le jour, partagez vos découvertes avec prudence — les loups "
                "vous cibleront si vous vous dévoilez trop vite !"
            ),
            "Voyante d'Aura": (
                "✨ Comme la Voyante, mais vous voyez l'**aura** (Gentil/Méchant) "
                "au lieu du rôle exact.\n"
                f"Exemple : `{p}voyante Bob` (en DM au bot).\n"
                "💡 Utile pour détecter les loups sans connaître les rôles précis."
            ),
            "Sorcière": (
                "🧪 Vous avez **2 potions** (une seule utilisation chaque) :\n"
                f"• **Vie** : sauver la victime des loups → `{p}sorciere-sauve Alice`\n"
                f"• **Mort** : empoisonner quelqu'un → `{p}sorciere-tue Bob`\n"
                "Vous pouvez utiliser les deux la même nuit !\n"
                "💡 Le bot vous prévient qui les loups ont ciblé."
            ),
            "Cupidon": (
                "💘 La première nuit, vous mariez deux joueurs.\n"
                f"Exemple : `{p}cupidon Alice Bob` (en DM).\n"
                "Les amoureux meurent ensemble. S'ils sont les derniers, "
                "ils gagnent (et vous aussi !).\n"
                "💡 Mariez un loup et un villageois pour créer un dilemme intéressant."
            ),
            "Chasseur": (
                "🔫 Quand vous mourez, vous emportez quelqu'un avec vous !\n"
                f"Exemple : `{p}tuer Charlie` (en DM) après votre mort.\n"
                "⚠️ Vous avez peu de temps pour agir après votre mort."
            ),
            "Garde": (
                "🛡️ Chaque nuit, vous protégez un joueur contre les loups.\n"
                f"Exemple : `{p}garde Alice` (en DM).\n"
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
                f"Exemple : `{p}corbeau Alice` (en DM).\n"
                "💡 Ciblez les joueurs que vous soupçonnez d'être loups pour "
                "les faire éliminer plus facilement."
            ),
            "Dictateur": (
                "⚔️ Une fois dans la partie (de jour), vous pouvez éliminer un "
                "joueur sans vote.\n"
                f"Exemple : `{p}dictateur Bob` (en DM).\n"
                "⚠️ Si la cible est un villageois, VOUS mourez aussi !\n"
                "💡 Soyez sûr de votre cible avant d'utiliser ce pouvoir."
            ),
            "Voleur": (
                "🎭 La première nuit, vous pouvez :\n"
                f"• Tirer 2 cartes : `{p}voleur-tirer` (en DM)\n"
                f"• Choisir une carte : `{p}voleur-choisir 1` ou `{p}voleur-choisir 2`\n"
                f"• OU échanger avec un joueur : `{p}voleur-echange Alice`\n"
                "💡 Vous gardez le rôle choisi pour le reste de la partie."
            ),
            "Enfant Sauvage": (
                "🧒 La première nuit, choisissez un **mentor**.\n"
                f"Exemple : `{p}enfant Alice` (en DM).\n"
                "Si votre mentor meurt, vous devenez **Loup-Garou** !\n"
                "💡 Choisissez quelqu'un qui a des chances de survivre longtemps."
            ),
            "Médium": (
                "🔮 Chaque nuit, vous pouvez communiquer avec un.e joueur.se mort.e.\n"
                f"Exemple : `{p}medium Alice` (en DM).\n"
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
                f"Exemple : `{p}vote Alice` dans le salon du village pendant la phase de vote.\n"
                "💡 Observez les discussions, repérez les comportements suspects "
                "et votez pour éliminer les loups !"
            ),
            "Idiot": (
                "🤪 Si vous êtes éliminé par le vote du village, vous survivez ! "
                "Mais vous perdez votre droit de vote.\n"
                "💡 Vous pouvez continuer à participer aux discussions et "
                "influencer les autres joueurs."
            ),
            "Chasseur de Têtes": (
                "🎯 Une cible vous est désignée automatiquement au début de la partie.\n"
                "Si votre cible est éliminée par le **vote du village**, vous gagnez **seul** !\n"
                "⚠️ Si votre cible meurt d'une autre façon (loups, sorcière…), "
                "vous rejoignez l'**alliance du mal** et gagnez avec les loups.\n"
                "💡 Orientez subtilement le vote vers votre cible sans paraître suspect."
            ),
            "Assassin": (
                "🗡️ Chaque nuit, vous pouvez éliminer une cible en secret.\n"
                f"Exemple : `{p}assassin Alice` (en DM).\n"
                "🎯 Vous gagnez si vous êtes le dernier survivant.\n"
                "💡 Évitez d'attirer l'attention pendant la journée."
            ),
            "Pyromane": (
                "🔥 Chaque nuit, vous pouvez asperger jusqu'a deux personnes.\n"
                f"Exemple : `{p}pyromane Bob` (en DM).\n"
                "Ou vous pouvez embraser toutes vos cibles (1 fois).\n"
                f"Exemple : `{p}pyromane-brule` (en DM).\n"
                "🎯 Vous gagnez si vous êtes le dernier survivant."
            ),
            "Détective": (
                "🕵️ Chaque nuit, comparez deux joueurs pour savoir s'ils sont dans la même équipe.\n"
                f"Exemple : `{p}detective Alice Bob` (en DM).\n"
                "💡 Utilisez ces informations pour aider le village."
            ),
            "Geôlier": (
                "🔒 Le jour, choisissez un prisonnier pour la nuit.\n"
                f"Exemple : `{p}geolier Alice` (en DM).\n"
                "Le prisonnier est isolé et ne peut pas agir.\n"
                f"Pour lui parler : `{p}msg Bonjour`.\n"
                f"Vous pouvez exécuter une fois : `{p}geolier-tuer` (nuit)."
            ),
        }
        return tutorials.get(role.name, "")
