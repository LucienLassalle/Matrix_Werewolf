"""Mixin pour la construction des messages UI du bot.

Contient les méthodes de mise en forme : annonces de rôles,
ordre d'assise, statut de la partie, liste des joueurs.
"""

import logging
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

from models.enums import GamePhase, Team
from matrix_bot.scheduler import day_name_fr

if TYPE_CHECKING:
    from matrix_bot.bot_controller import WerewolfBot

logger = logging.getLogger(__name__)


class UIBuildersMixin:
    """Mixin fournissant les méthodes de construction de messages."""

    def _build_roles_announcement(self: 'WerewolfBot') -> str:
        """Construit l'annonce des rôles en jeu au début de la partie."""
        summary = self.game_manager.get_roles_summary()
        nb_players = len(self.game_manager.players)

        message = "🎮 **La partie commence !**\n\n"
        message += f"👥 **{nb_players} joueurs** participent.\n\n"
        message += "📋 **Rôles en jeu :**\n\n"

        for rt, info in sorted(summary.items(), key=lambda x: x[0].value):
            emoji = info.get('emoji', "❓")
            message += f"{emoji} **{info['name']}** ×{info['count']}\n"
            message += f"   {info['description']}\n\n"

        message += f"🌙 La première nuit commence à **{self._night_hour}h00**.\n"
        message += "Consultez vos **messages privés** (DM du bot) pour découvrir votre rôle.\n\n"
        message += (
            f"👑 **Élection du maire** — Après la première nuit, votez avec "
            f"`{self.command_prefix}vote-maire {{pseudo}}` dans le salon du village "
            f"pour élire un maire !"
        )

        return message

    def _build_seating_message(self: 'WerewolfBot') -> str:
        """Construit le message d'ordre d'assise (cercle) des joueurs.

        Les joueurs sont assis en cercle : le premier et le dernier sont
        voisins.  Cette disposition est utilisée par le Montreur d'Ours
        pour déterminer les voisins.
        """
        order = self.game_manager._player_order
        if not order:
            return ""

        names = []
        for uid in order:
            player = self.game_manager.players.get(uid)
            if not player:
                continue
            display = player.display_name
            if player.is_alive:
                names.append(f"**{display}**")
            else:
                names.append(f"~~**{display}**~~")

        if not names:
            return ""

        chain = " ↔ ".join(names)

        return (
            "🪑 **Ordre d'assise (cercle) :**\n\n"
            f"{chain}\n\n"
            f"↩️ {names[-1]} et {names[0]} sont côte à côte (le cercle est fermé)."
        )

    def _build_statut_message(self: 'WerewolfBot') -> str:
        """Construit le message de statut de la partie en cours."""
        if self.game_manager.phase == GamePhase.SETUP:
            # Rafraîchir depuis la BDD (inclut les ajouts via admin_cli)
            db_regs = self.game_manager.db.load_registrations()
            if db_regs:
                self.registered_players = dict(db_regs)
            nb = len(self.registered_players)
            return (
                "📋 **Statut de la partie**\n\n"
                f"⏳ En attente de joueurs — **{nb}** inscrit{'s' if nb > 1 else ''}\n"
                f"La partie démarrera **{day_name_fr(self._game_start_day)} à {self._game_start_hour}h**."
            )

        if self.game_manager.phase == GamePhase.ENDED:
            return "📋 **Statut :** Aucune partie en cours."

        living = self.game_manager.get_living_players()
        dead_count = len(self.game_manager.players) - len(living)

        # Phase actuelle
        phase_names = {
            GamePhase.NIGHT: "🌙 Nuit",
            GamePhase.DAY: "☀️ Jour",
            GamePhase.VOTE: "🗳️ Vote",
        }
        phase_str = phase_names.get(self.game_manager.phase, str(self.game_manager.phase))

        # Temps restant avant la prochaine phase
        now = datetime.now()
        if self.game_manager.phase == GamePhase.NIGHT:
            next_phase_time = datetime.combine(now.date(), self.scheduler.day_start)
            if next_phase_time < now:
                next_phase_time += timedelta(days=1)
            next_phase_name = "☀️ Jour"
        elif self.game_manager.phase == GamePhase.DAY:
            if self.game_manager.night_count < 1:
                # Jour 0 : en attente de la première nuit
                next_phase_time = datetime.combine(now.date(), self.scheduler.night_start)
                if next_phase_time < now:
                    next_phase_time += timedelta(days=1)
                next_phase_name = "🌙 Première nuit"
            else:
                next_phase_time = datetime.combine(now.date(), self.scheduler.vote_start)
                if next_phase_time < now:
                    next_phase_time += timedelta(days=1)
                next_phase_name = "🗳️ Vote"
        elif self.game_manager.phase == GamePhase.VOTE:
            next_phase_time = datetime.combine(now.date(), self.scheduler.night_start)
            if next_phase_time < now:
                next_phase_time += timedelta(days=1)
            next_phase_name = "🌙 Nuit"
        else:
            next_phase_time = None
            next_phase_name = ""

        remaining_str = ""
        if next_phase_time:
            remaining = next_phase_time - now
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes = remainder // 60
            if hours > 0:
                remaining_str = f"{hours}h{minutes:02d}"
            else:
                remaining_str = f"{minutes} min"

        # Maire
        mayor = self.game_manager.get_mayor()
        mayor_str = f"👑 Maire : **{mayor.display_name}**" if mayor else "👑 Maire : aucun"

        message = "📋 **Statut de la partie**\n\n"
        message += f"**Phase :** {phase_str}\n"
        message += f"**Jour :** {self.game_manager.day_count}\n"
        message += f"**Vivants :** {len(living)} / {len(self.game_manager.players)}\n"
        message += f"**Morts :** {dead_count}\n"
        message += f"{mayor_str}\n"
        if remaining_str:
            message += f"\n⏰ Prochaine phase ({next_phase_name}) dans **{remaining_str}**"

        return message

    def _build_joueurs_message(self: 'WerewolfBot') -> str:
        """Construit la liste des joueurs (vivants/morts, sans révéler les rôles)."""
        if not self.game_manager.players:
            # En phase SETUP, rafraîchir depuis la BDD pour inclure les ajouts
            # faits via admin_cli.py qui n'ont pas encore été synchronisés.
            db_regs = self.game_manager.db.load_registrations()
            if db_regs:
                self.registered_players = dict(db_regs)
            if self.registered_players:
                nb = len(self.registered_players)
                names = ", ".join(self.registered_players.values())
                return f"👥 **Joueurs inscrits ({nb}):**\n{names}"
            return "👥 Aucun joueur dans la partie."

        living = self.game_manager.get_living_players()
        dead = [p for p in self.game_manager.players.values() if not p.is_alive]
        mayor = self.game_manager.get_mayor()

        message = f"👥 **Joueurs ({len(self.game_manager.players)})**\n\n"

        # Vivants
        message += f"**✅ Vivants ({len(living)}):**\n"
        for p in living:
            crown = " 👑" if p == mayor else ""
            message += f"• {p.display_name}{crown}\n"

        # Morts
        if dead:
            message += f"\n**💀 Morts ({len(dead)}):**\n"
            for p in dead:
                message += f"• ~~{p.display_name}~~ — **{p.role.name}**\n"

        return message

    def _build_roles_list_message(self: 'WerewolfBot') -> str:
        """Construit la liste de tous les rôles disponibles dans le bot.

        Les rôles désactivés sont exclus de la liste.
        """
        from roles import RoleFactory
        from models.role import ROLE_DISPLAY_NAMES

        available = RoleFactory.get_available_roles()
        # Exclure les rôles désactivés
        available = [rt for rt in available if rt not in self.disabled_roles]

        if not available:
            return "🎭 Aucun rôle disponible."

        message = "🎭 **Rôles disponibles :**\n\n"
        for rt in available:
            role = RoleFactory.create_role(rt)
            emoji = getattr(role, 'emoji', "❓")
            message += f"{emoji} **{role.name}**\n"
            message += f"   {role.description}\n\n"

        if self.disabled_roles:
            disabled_names = ', '.join(
                ROLE_DISPLAY_NAMES.get(rt, rt.value)
                for rt in sorted(self.disabled_roles, key=lambda r: r.value)
            )
            message += f"🚫 **Rôles désactivés :** {disabled_names}\n"

        return message

    def _build_help_message(self: 'WerewolfBot') -> str:
        """Construit le message d'aide avec toutes les commandes disponibles."""
        p = self.command_prefix

        message = "📖 **Aide — Commandes du Loup-Garou**\n\n"

        # Commandes générales
        message += "🔹 **Commandes générales** (utilisables partout) :\n"
        message += f"• `{p}inscription` — S'inscrire à la prochaine partie\n"
        message += f"• `{p}help` / `{p}aide` — Afficher cette aide\n"
        message += f"• `{p}statut` — Voir l'état actuel de la partie\n"
        message += f"• `{p}joueurs` — Voir la liste des joueurs (vivants/morts)\n"
        message += f"• `{p}leaderboard` / `{p}top` — Voir le classement\n"
        message += f"• `{p}stats` — Voir ses propres statistiques\n"
        message += f"• `{p}roles` — Voir tous les rôles disponibles (lobby / MP)\n"
        message += "\n"

        # Commandes de vote (village)
        message += "🗳️ **Commandes de vote** (salon du village) :\n"
        message += f"• `{p}vote {{pseudo}}` — Voter pour éliminer quelqu'un (phase de vote)\n"
        message += f"• `{p}votes` — Voir les votes en cours (phase de vote)\n"
        message += f"• `{p}vote-maire {{pseudo}}` — Voter pour un candidat maire (après la 1ère nuit)\n"
        message += f"• `{p}votes-maire` — Voir les votes du maire (après la 1ère nuit)\n"
        message += "\n"

        # Commandes des loups (salon des loups)
        message += "🐺 **Commandes des loups** (salon des loups, la nuit) :\n"
        message += f"• `{p}vote {{pseudo}}` — Voter avec la meute pour dévorer quelqu'un\n"
        message += "\n"

        # Commandes nocturnes (DM)
        message += "🌙 **Commandes nocturnes** (en message privé au bot) :\n"
        message += f"• `{p}voyante {{pseudo}}` — Voir le rôle/aura d'un joueur (Voyante / Voyante d'Aura / Loup Voyant)\n"
        message += f"• `{p}sorciere-sauve {{pseudo}}` — Sauver la victime des loups (Sorcière, 1 seule fois)\n"
        message += f"• `{p}sorciere-tue {{pseudo}}` — Empoisonner un joueur (Sorcière, 1 seule fois)\n"
        message += f"• `{p}garde {{pseudo}}` — Protéger un joueur cette nuit (Garde)\n"
        message += f"• `{p}cupidon {{pseudo1}} {{pseudo2}}` — Marier deux joueurs (Cupidon, nuit 1)\n"
        message += f"• `{p}enfant {{pseudo}}` — Choisir un mentor (Enfant Sauvage, nuit 1)\n"
        message += f"• `{p}medium {{pseudo}}` — Communiquer avec un.e joueur.se mort.e (Médium)\n"
        message += f"• `{p}corbeau` / `{p}curse` `{{pseudo}}` — Maudire un joueur (+2 votes, Corbeau)\n"
        message += f"• `{p}lg` — Abandonner la voyance et rejoindre la meute (Loup Voyant)\n"
        message += f"• `{p}convertir` — Convertir la cible des loups en loup (Loup Noir, 1 fois)\n"
        message += f"• `{p}tuer {{pseudo}}` — Tuer un joueur (Loup Blanc 1 nuit/2, Chasseur après mort)\n"
        message += f"• `{p}assassin {{pseudo}}` — Éliminer une cible (Assassin)\n"
        message += f"• `{p}pyromane {{pseudo}}` — Asperger une cible (Pyromane)\n"
        message += f"• `{p}pyromane-brule` — Embraser les cibles aspergées (Pyromane, 1 fois)\n"
        message += f"• `{p}detective {{pseudo1}} {{pseudo2}}` — Comparer deux joueurs (Détective)\n"
        message += f"• `{p}geolier-tuer` — Exécuter le prisonnier (Geôlier, 1 fois)\n"
        message += f"• `{p}msg {{message}}` — Parler au prisonnier (Geôlier)\n"

        message += "\n🔒 **Commandes privées de jour** (en message privé au bot) :\n"
        message += f"• `{p}dictateur {{pseudo}}` — Éliminer quelqu'un sans vote (Dictateur)\n"
        message += f"• `{p}geolier {{pseudo}}` — Choisir un prisonnier pour la nuit (Geôlier)\n"
        message += f"• `{p}voleur-tirer` — Tirer 2 cartes (Voleur, nuit 1)\n"
        message += f"• `{p}voleur-choisir {{1|2}}` — Choisir une carte tirée (Voleur)\n"
        message += f"• `{p}voleur-echange {{pseudo}}` — Échanger son rôle (Voleur, nuit 1)\n"
        message += "\n"

        # Commandes spéciales
        message += "⚡ **Commandes spéciales** (en message privé au bot) :\n"
        message += f"• `{p}dictateur {{pseudo}}` — Éliminer sans vote, de jour (Dictateur, 1 fois)\n"
        message += f"• `{p}maire {{pseudo}}` — Désigner un successeur (Maire mourant)\n"

        # Rôles désactivés
        if self.disabled_roles:
            from models.role import ROLE_DISPLAY_NAMES
            names = ', '.join(
                ROLE_DISPLAY_NAMES.get(rt, rt.value)
                for rt in sorted(self.disabled_roles, key=lambda r: r.value)
            )
            message += f"\n🚫 **Rôles désactivés :** {names}\n"

        return message
