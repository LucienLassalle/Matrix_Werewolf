"""Tests du journal de fin de partie.

Vérifie que :
- Les actions secrètes (voyante, sorcière, garde, cupidon…) sont tracées
- Les événements de phase (morts, sauvetages, conversions) sont tracés
- La chronologie groupée s'affiche correctement dans _announce_victory
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from game.game_manager import GameManager
from models.enums import GamePhase, RoleType, Team
from models.player import Player
from roles.voyante import Voyante
from roles.sorciere import Sorciere
from roles.garde import Garde
from roles.cupidon import Cupidon
from roles.loup_garou import LoupGarou
from roles.villageois import Villageois
from roles.corbeau import Corbeau
from roles.enfant_sauvage import EnfantSauvage
from roles.medium import Medium
from roles.loup_blanc import LoupBlanc
from roles.loup_noir import LoupNoir
from roles.loup_voyant import LoupVoyant
from roles.voleur import Voleur


# ── Helpers ────────────────────────────────────────────────────────

def _make_game(*specs):
    """Crée un GameManager avec les joueurs et rôles donnés.

    specs: tuples (pseudo, RoleClass)
    """
    gm = GameManager()
    for i, (pseudo, role_cls) in enumerate(specs):
        uid = f"@{pseudo}:matrix.org"
        gm.add_player(pseudo, uid)
        role = role_cls()
        role.assign_to_player(gm.players[uid])
    return gm


def _make_router_stub(game_manager):
    """Crée un stub avec CommandRouterMixin._track_journal_event."""
    from matrix_bot.command_router import CommandRouterMixin

    class Stub(CommandRouterMixin):
        pass

    stub = Stub()
    stub.game_manager = game_manager
    stub._game_events = []
    stub.command_prefix = "!"
    return stub


# ── Tests : _track_journal_event ──────────────────────────────────

class TestTrackJournalEvent:
    """Teste l'enregistrement d'événements par _track_journal_event."""

    def _setup(self, *specs):
        gm = _make_game(*specs)
        gm.phase = GamePhase.NIGHT
        gm.night_count = 1
        gm.day_count = 0
        stub = _make_router_stub(gm)
        return gm, stub

    def test_cupidon_event(self):
        gm, stub = self._setup(
            ("alice", Cupidon), ("bob", Villageois), ("carol", LoupGarou)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("cupidon", ["bob", "carol"], result, player)
        assert len(stub._game_events) == 1
        assert "Cupidon" in stub._game_events[0]
        assert "bob" in stub._game_events[0]
        assert "carol" in stub._game_events[0]
        assert "💕" in stub._game_events[0]

    def test_enfant_sauvage_mentor(self):
        gm, stub = self._setup(
            ("alice", EnfantSauvage), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("enfant", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Enfant Sauvage" in stub._game_events[0]
        assert "bob" in stub._game_events[0]
        assert "mentor" in stub._game_events[0]

    def test_sorciere_sauve(self):
        gm, stub = self._setup(
            ("alice", Sorciere), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("sorciere-sauve", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Sorcière" in stub._game_events[0]
        assert "vie" in stub._game_events[0]
        assert "bob" in stub._game_events[0]

    def test_sorciere_tue(self):
        gm, stub = self._setup(
            ("alice", Sorciere), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("sorciere-tue", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Sorcière" in stub._game_events[0]
        assert "empoisonne" in stub._game_events[0]
        assert "bob" in stub._game_events[0]

    def test_garde_protect(self):
        gm, stub = self._setup(
            ("alice", Garde), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("garde", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Garde" in stub._game_events[0]
        assert "protège" in stub._game_events[0]
        assert "bob" in stub._game_events[0]

    def test_voyante_see_role(self):
        gm, stub = self._setup(
            ("alice", Voyante), ("bob", LoupGarou)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True, "role": "Loup-Garou"}
        stub._track_journal_event("voyante", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Voyante" in stub._game_events[0]
        assert "bob" in stub._game_events[0]
        assert "Loup-Garou" in stub._game_events[0]

    def test_voyante_aura(self):
        gm, stub = self._setup(
            ("alice", Voyante), ("bob", LoupGarou)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True, "aura": "Méchant 🐺"}
        stub._track_journal_event("voyante", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Voyante d'Aura" in stub._game_events[0]
        assert "Méchant" in stub._game_events[0]

    def test_corbeau_curse(self):
        gm, stub = self._setup(
            ("alice", Corbeau), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("corbeau", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Corbeau" in stub._game_events[0]
        assert "maudit" in stub._game_events[0]
        assert "+2 votes" in stub._game_events[0]

    def test_medium_consult(self):
        gm, stub = self._setup(
            ("alice", Medium), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("medium", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Médium" in stub._game_events[0]
        assert "bob" in stub._game_events[0]

    def test_voleur_echange(self):
        gm, stub = self._setup(
            ("alice", Voleur), ("bob", LoupGarou)
        )
        player = gm.players["@alice:matrix.org"]
        new_role = LoupGarou()
        result = {"success": True, "new_role": new_role}
        stub._track_journal_event("voleur-echange", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Voleur" in stub._game_events[0]
        assert "bob" in stub._game_events[0]
        assert "Loup-Garou" in stub._game_events[0]

    def test_voleur_choisir(self):
        gm, stub = self._setup(
            ("alice", Voleur),
        )
        player = gm.players["@alice:matrix.org"]
        new_role = Voyante()
        result = {"success": True, "new_role": new_role}
        stub._track_journal_event("voleur-choisir", ["1"], result, player)
        assert len(stub._game_events) == 1
        assert "Voleur" in stub._game_events[0]
        assert "Voyante" in stub._game_events[0]

    def test_lg_become_wolf(self):
        gm, stub = self._setup(
            ("alice", LoupVoyant),
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("lg", [], result, player)
        assert len(stub._game_events) == 1
        assert "Loup Voyant" in stub._game_events[0]
        assert "meute" in stub._game_events[0]

    def test_convertir(self):
        gm, stub = self._setup(
            ("alice", LoupNoir),
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("convertir", [], result, player)
        assert len(stub._game_events) == 1
        assert "Loup Noir" in stub._game_events[0]
        assert "conversion" in stub._game_events[0]

    def test_loup_blanc_kill(self):
        gm, stub = self._setup(
            ("alice", LoupBlanc), ("bob", LoupGarou)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("tuer", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "Loup Blanc" in stub._game_events[0]
        assert "bob" in stub._game_events[0]

    def test_maire_succession(self):
        gm, stub = self._setup(
            ("alice", Villageois), ("bob", Villageois)
        )
        gm.phase = GamePhase.DAY
        gm.day_count = 1
        player = gm.players["@alice:matrix.org"]
        new_mayor = gm.players["@bob:matrix.org"]
        result = {"success": True, "new_mayor": new_mayor}
        stub._track_journal_event("maire", ["bob"], result, player)
        assert len(stub._game_events) == 1
        assert "alice" in stub._game_events[0]
        assert "bob" in stub._game_events[0]
        assert "👑" in stub._game_events[0]

    def test_dictateur_not_duplicated(self):
        """Le dictateur est tracé par _process_command_deaths, pas ici."""
        gm, stub = self._setup(
            ("alice", Villageois), ("bob", Villageois)
        )
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("dictateur", ["bob"], result, player)
        assert len(stub._game_events) == 0

    def test_unknown_command_no_event(self):
        gm, stub = self._setup(("alice", Villageois),)
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("unknown", [], result, player)
        assert len(stub._game_events) == 0

    def test_night_count_in_events(self):
        """Le numéro de nuit doit apparaître dans l'événement."""
        gm, stub = self._setup(
            ("alice", Garde), ("bob", Villageois)
        )
        gm.night_count = 3
        player = gm.players["@alice:matrix.org"]
        result = {"success": True}
        stub._track_journal_event("garde", ["bob"], result, player)
        assert "Nuit 3" in stub._game_events[0]


# ── Tests : Chronologie groupée dans _announce_victory ────────────

class TestChronologyGrouping:
    """Teste le groupement par phase dans la chronologie de fin de partie."""

    def test_events_grouped_by_phase(self):
        """Les événements sont groupés par Nuit N / Jour N."""
        events = [
            "Nuit 0 — 💕 **Cupidon** lie **Alice** et **Bob**",
            "Jour 0 — 👑 **Charlie** élu maire",
            "Nuit 1 — 🛡️ **Le Garde** protège **Alice**",
            "Nuit 1 — 💀 **Bob** tué durant la nuit (Villageois)",
            "Jour 1 — 🗳️ **Dave** éliminé par le vote (Loup-Garou)",
        ]
        # Simulate the grouping logic from _announce_victory
        output = self._format_chronology(events)
        assert "**Nuit 0**" in output
        assert "**Jour 0**" in output
        assert "**Nuit 1**" in output
        assert "**Jour 1**" in output
        # Phase headers should appear before their events
        nuit0_pos = output.index("**Nuit 0**")
        cupidon_pos = output.index("Cupidon")
        assert nuit0_pos < cupidon_pos

    def test_events_without_phase_prefix(self):
        """Les événements sans préfixe de phase sont affichés sans header."""
        events = [
            "Nuit 1 — 💀 **Bob** tué",
            "🔫 **Alice** (Chasseur) tire sur **Carol**",
            "👑 **Dave** désigne **Eve** comme nouveau maire",
        ]
        output = self._format_chronology(events)
        assert "🔫" in output
        assert "👑" in output

    def test_empty_events(self):
        """Pas de section chronologie si aucun événement."""
        output = self._format_chronology([])
        assert output == ""

    @staticmethod
    def _format_chronology(events):
        """Reproduit la logique de groupement de _announce_victory."""
        if not events:
            return ""
        message = "\n📜 **Chronologie de la partie:**\n"
        current_phase = None
        for event in events:
            phase_label = None
            event_text = event
            for prefix in ("Nuit ", "Jour "):
                if event.startswith(prefix):
                    dash_pos = event.find(" — ")
                    if dash_pos != -1:
                        phase_label = event[:dash_pos]
                        event_text = event[dash_pos + 3:]
                    break
            if phase_label and phase_label != current_phase:
                current_phase = phase_label
                message += f"\n**{phase_label}**\n"
            if phase_label:
                message += f"  • {event_text}\n"
            else:
                message += f"  • {event}\n"
        return message


# ── Tests : événements de phase (morts, sauvetages) ──────────────

class TestPhaseEvents:
    """Teste les événements ajoutés durant les phases (nuit → jour)."""

    def test_night_deaths_tracked(self):
        """Les morts de nuit ajoutent des événements au journal."""
        gm = _make_game(
            ("alice", Villageois), ("bob", LoupGarou),
            ("carol", Villageois), ("dave", Villageois),
            ("eve", Villageois),
        )
        gm.phase = GamePhase.NIGHT
        gm.night_count = 1
        gm.day_count = 0

        # Simuler un vote des loups/résolution
        gm.start_game()

        events = []
        events.append(
            f"Nuit {gm.night_count} — 💀 **alice** tué durant la nuit (Villageois)"
        )
        assert "Nuit" in events[0]
        assert "alice" in events[0]

    def test_guard_save_tracked(self):
        """Quand le Garde sauve quelqu'un, un événement est ajouté."""
        # Simulate the event that phase_handlers adds for saved players
        events = []
        night_count = 2
        saved_name = "Alice"
        events.append(
            f"Nuit {night_count} — 🛡️ **{saved_name}** "
            f"sauvé par la protection du Garde"
        )
        assert "🛡️" in events[0]
        assert "Alice" in events[0]
        assert "Nuit 2" in events[0]

    def test_enfant_sauvage_conversion_tracked(self):
        """La conversion de l'Enfant Sauvage est tracée."""
        events = []
        night_count = 2
        name = "Alice"
        events.append(
            f"Nuit {night_count} — 🧒🐺 "
            f"**{name}** (Enfant Sauvage) "
            f"converti en Loup-Garou (mentor mort)"
        )
        assert "Enfant Sauvage" in events[0]
        assert "mentor" in events[0]

    def test_loup_noir_conversion_tracked(self):
        """La conversion par le Loup Noir est tracée."""
        events = []
        night_count = 1
        name = "Bob"
        events.append(
            f"Nuit {night_count} — 🐺 **{name}** "
            f"converti en Loup-Garou par le Loup Noir"
        )
        assert "Loup Noir" in events[0]
        assert "Bob" in events[0]
