"""Tests pour les nouvelles mécaniques : Sorcière (deux potions/nuit),
Loup Noir (conversion), Dictateur (jour), action_manager (conversion),
command_handler (/convertir, /dictateur), resolve_night (wolf_target, converted)."""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager
from game.action_manager import ActionManager
from game.vote_manager import VoteManager
from commands.command_handler import CommandHandler


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés.
    
    specs: tuples (pseudo, user_id, RoleType)
    Retourne le GameManager en phase NIGHT.
    """
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


# ═══════════════════════════════════════════════════════════
#  Sorcière : deux potions la même nuit
# ═══════════════════════════════════════════════════════════

class TestSorciereBothPotions:
    """Vérifie que la Sorcière peut utiliser heal ET poison la même nuit."""

    def test_both_potions_same_night(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Victime", "v1", RoleType.VILLAGEOIS),
            ("Cible", "c1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        victime = game.players["v1"]
        cible = game.players["c1"]

        # Heal d'abord
        r1 = sorc.role.perform_action(game, ActionType.HEAL, victime)
        assert r1["success"]
        assert sorc.role.has_healed_tonight
        assert not sorc.role.has_life_potion

        # Poison ensuite (même nuit)
        r2 = sorc.role.perform_action(game, ActionType.POISON, cible)
        assert r2["success"]
        assert sorc.role.has_poisoned_tonight
        assert not sorc.role.has_death_potion

    def test_cannot_heal_twice_same_night(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        v1 = game.players["v1"]

        sorc.role.perform_action(game, ActionType.HEAL, v1)
        # Deuxième heal impossible (has_healed_tonight)
        r = sorc.role.perform_action(game, ActionType.HEAL, v1)
        assert not r["success"]

    def test_cannot_poison_twice_same_night(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        v1 = game.players["v1"]

        sorc.role.perform_action(game, ActionType.POISON, v1)
        r = sorc.role.perform_action(game, ActionType.POISON, v1)
        assert not r["success"]

    def test_flags_reset_on_night_start(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        # Simuler une nuit où elle a guéri
        sorc.role.has_healed_tonight = True
        sorc.role.has_poisoned_tonight = True

        sorc.role.on_night_start(game)
        assert not sorc.role.has_healed_tonight
        assert not sorc.role.has_poisoned_tonight

    def test_no_life_potion_left(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.has_life_potion = False

        r = sorc.role.perform_action(game, ActionType.HEAL, game.players["v1"])
        assert not r["success"]

    def test_no_death_potion_left(self):
        game = make_game(
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        sorc.role.has_death_potion = False

        r = sorc.role.perform_action(game, ActionType.POISON, game.players["v1"])
        assert not r["success"]


# ═══════════════════════════════════════════════════════════
#  Loup Noir : mécanisme de conversion
# ═══════════════════════════════════════════════════════════

class TestLoupNoir:
    """Vérifie le toggle wants_to_convert et la conversion dans l'action_manager."""

    def test_convert_toggle(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]

        assert not ln.role.wants_to_convert
        r = ln.role.perform_action(game, ActionType.CONVERT)
        assert r["success"]
        assert ln.role.wants_to_convert

    def test_cannot_convert_twice_same_night(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
        )
        ln = game.players["ln1"]

        ln.role.perform_action(game, ActionType.CONVERT)
        r = ln.role.perform_action(game, ActionType.CONVERT)
        assert not r["success"]

    def test_reset_on_night_start(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
        )
        ln = game.players["ln1"]
        ln.role.wants_to_convert = True

        ln.role.on_night_start(game)
        assert not ln.role.wants_to_convert

    def test_can_vote_with_wolves(self):
        role = RoleFactory.create_role(RoleType.LOUP_NOIR)
        assert role.can_vote_with_wolves()

    def test_conversion_in_action_manager(self):
        """La cible des loups est convertie au lieu d'être tuée."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]
        target = game.players["v1"]

        # Loup Noir active la conversion
        ln.role.perform_action(game, ActionType.CONVERT)

        # Loups votent pour la cible
        game.vote_manager.register_player(ln)
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(ln, target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] == target
        assert target.is_alive  # Pas mort
        assert target.role.role_type == RoleType.LOUP_GAROU
        assert len(results["deaths"]) == 0

    def test_garde_blocks_conversion(self):
        """Le Garde bloque aussi la conversion."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Garde", "g1", RoleType.GARDE),
        )
        ln = game.players["ln1"]
        garde = game.players["g1"]
        target = game.players["v1"]

        # Loup Noir active la conversion
        ln.role.perform_action(game, ActionType.CONVERT)

        # Garde protège la cible
        garde.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        # Loups votent
        game.vote_manager.register_player(ln)
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(ln, target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert target.is_alive
        assert target.role.role_type == RoleType.VILLAGEOIS  # Pas converti
        assert len(results["deaths"]) == 0

    def test_conversion_target_already_mechant(self):
        """Tenter de convertir un joueur déjà MECHANT n'a aucun effet, pas de meurtre."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup2", "w2", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),  # Gentil, pour remplir
        )
        ln = game.players["ln1"]
        w2 = game.players["w2"]  # Déjà méchant

        ln.role.perform_action(game, ActionType.CONVERT)

        game.vote_manager.register_player(ln)
        game.vote_manager.register_player(w2)
        # Voter pour un loup (cas anormal mais possible)
        # On va plutôt voter pour la sorcière mais changer son équipe manuellement
        # Actually: w2 est already MECHANT, testons en votant pour sorcière
        # No — let's vote for something that is actually MECHANT
        # Simplest: just set up votes for w2 who is already MECHANT
        
        # Actually in a real game, wolves wouldn't vote for another wolf,
        # but the mechanic still needs to be tested
        game.vote_manager.register_player(game.players["s1"])
        
        # Make sorciere MECHANT temporarily for the test
        game.players["s1"].role = RoleFactory.create_role(RoleType.LOUP_GAROU)
        game.players["s1"].role.assign_to_player(game.players["s1"])
        
        game.vote_manager.add_wolf_vote(ln, game.players["s1"])

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert game.players["s1"].is_alive  # Pas mort non plus
        assert len(results["deaths"]) == 0

    def test_no_conversion_normal_kill(self):
        """Sans conversion active, le meurtre classique a lieu."""
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        # Pas de /convertir → meurtre classique
        game.vote_manager.register_player(game.players["ln1"])
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["ln1"], target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["converted"] is None
        assert not target.is_alive
        assert target in results["deaths"]


# ═══════════════════════════════════════════════════════════
#  Action Manager : résolution complète
# ═══════════════════════════════════════════════════════════

class TestActionManagerResolution:
    """Vérifie l'ordre de résolution du nuit."""

    def test_garde_protects_wolf_target(self):
        """Le Garde empêche la mort par les loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Garde", "g1", RoleType.GARDE),
        )
        target = game.players["v1"]
        garde = game.players["g1"]

        # Garde protège
        garde.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        # Loup vote
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert len(results["deaths"]) == 0

    def test_sorciere_heal_saves_wolf_target(self):
        """La Sorcière peut sauver la cible des loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]
        sorc = game.players["s1"]

        # Loup vote
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        # Sorcière sauve
        sorc.role.perform_action(game, ActionType.HEAL, target)
        game.action_manager.register_action(sorc, ActionType.HEAL, target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert target in results["saved"]

    def test_sorciere_heal_wasted_if_garde_protects(self):
        """Si le Garde protège et que la Sorcière sauve aussi, la potion est quand même consommée."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Garde", "g1", RoleType.GARDE),
        )
        target = game.players["v1"]
        sorc = game.players["s1"]
        garde = game.players["g1"]

        # Garde protège
        garde.role.perform_action(game, ActionType.PROTECT, target)
        game.action_manager.register_action(garde, ActionType.PROTECT, target)

        # Loup vote
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        # Sorcière sauve quand même (elle ne sait pas que le Garde protège)
        sorc.role.perform_action(game, ActionType.HEAL, target)
        game.action_manager.register_action(sorc, ActionType.HEAL, target)

        results = game.action_manager.execute_night_actions(game)

        assert target.is_alive
        assert not sorc.role.has_life_potion  # Potion consommée quand même

    def test_sorciere_poison_kills(self):
        """La potion de mort de la Sorcière tue la cible."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
        )
        sorc = game.players["s1"]
        cible_poison = game.players["v2"]

        # Sorcière empoisonne
        sorc.role.perform_action(game, ActionType.POISON, cible_poison)
        game.action_manager.register_action(sorc, ActionType.POISON, cible_poison)

        results = game.action_manager.execute_night_actions(game)

        assert not cible_poison.is_alive
        assert cible_poison in results["deaths"]

    def test_sorciere_heal_and_poison_same_night(self):
        """La Sorcière peut sauver ET empoisonner la même nuit."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Sorciere", "s1", RoleType.SORCIERE),
            ("Victime", "v1", RoleType.VILLAGEOIS),
            ("CiblePoison", "v2", RoleType.VILLAGEOIS),
        )
        target_wolf = game.players["v1"]
        target_poison = game.players["v2"]
        sorc = game.players["s1"]

        # Loup vote pour v1
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target_wolf)
        game.vote_manager.add_wolf_vote(game.players["w1"], target_wolf)

        # Sorcière sauve v1 ET empoisonne v2
        sorc.role.perform_action(game, ActionType.HEAL, target_wolf)
        game.action_manager.register_action(sorc, ActionType.HEAL, target_wolf)

        sorc.role.perform_action(game, ActionType.POISON, target_poison)
        game.action_manager.register_action(sorc, ActionType.POISON, target_poison)

        results = game.action_manager.execute_night_actions(game)

        assert target_wolf.is_alive  # Sauvé
        assert not target_poison.is_alive  # Empoisonné
        assert target_wolf in results["saved"]
        assert target_poison in results["deaths"]

    def test_loup_blanc_kill(self):
        """Le Loup Blanc tue un loup-garou (nuit paire)."""
        game = make_game(
            ("LoupBlanc", "lb1", RoleType.LOUP_BLANC),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        lb = game.players["lb1"]
        target = game.players["w1"]

        # Activer le kill du Loup Blanc
        lb.role.on_night_start(game)  # Nuit 1 : non
        lb.role.on_night_start(game)  # Nuit 2 : oui
        lb.role.perform_action(game, ActionType.KILL, target)
        game.action_manager.register_action(lb, ActionType.KILL, target)

        results = game.action_manager.execute_night_actions(game)

        assert not target.is_alive
        assert target in results["deaths"]

    def test_wolf_target_in_results(self):
        """Le résultat contient la cible des loups."""
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.action_manager.execute_night_actions(game)

        assert results["wolf_target"] == target


# ═══════════════════════════════════════════════════════════
#  Command Handler : /convertir et /dictateur
# ═══════════════════════════════════════════════════════════

class TestCommandHandlerNewCommands:
    """Vérifie les nouvelles commandes."""

    def test_convertir_command(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("V1", "v1", RoleType.VILLAGEOIS),
        )
        handler = CommandHandler(game)

        result = handler.execute_command("ln1", "convertir", [])
        assert result["success"]
        assert game.players["ln1"].role.wants_to_convert

    def test_convertir_wrong_role(self):
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        handler = CommandHandler(game)

        result = handler.execute_command("v1", "convertir", [])
        assert not result["success"]

    def test_dictateur_command(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", ["Loup"])
        assert result["success"]
        assert not game.players["w1"].is_alive
        assert game.players["d1"].is_mayor  # Tué un loup → maire

    def test_dictateur_kills_innocent_dies_too(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", ["Villageois"])
        assert result["success"]
        assert not game.players["v1"].is_alive
        assert not game.players["d1"].is_alive  # Dictateur meurt aussi

    def test_dictateur_wrong_role(self):
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Target", "t1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("v1", "dictateur", ["Target"])
        assert not result["success"]

    def test_dictateur_no_target(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
        )
        game.phase = GamePhase.DAY
        handler = CommandHandler(game)

        result = handler.execute_command("d1", "dictateur", [])
        assert not result["success"]


# ═══════════════════════════════════════════════════════════
#  resolve_night : données wolf_target et converted
# ═══════════════════════════════════════════════════════════

class TestResolveNight:
    """Vérifie que resolve_night() retourne les bonnes données."""

    def test_resolve_night_includes_wolf_target(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["wolf_target"] == "v1"
        assert "v1" in results["deaths"]

    def test_resolve_night_includes_converted(self):
        game = make_game(
            ("LoupNoir", "ln1", RoleType.LOUP_NOIR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        ln = game.players["ln1"]
        target = game.players["v1"]

        ln.role.perform_action(game, ActionType.CONVERT)

        game.vote_manager.register_player(ln)
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(ln, target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["converted"] == "v1"
        assert "v1" not in results["deaths"]  # Converti, pas mort

    def test_resolve_night_no_conversion(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("V2", "v2", RoleType.VILLAGEOIS),
        )
        target = game.players["v1"]

        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(target)
        game.vote_manager.add_wolf_vote(game.players["w1"], target)

        results = game.resolve_night()

        assert results["converted"] is None
        assert "v1" in results["deaths"]

    def test_resolve_night_wrong_phase(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY

        results = game.resolve_night()
        assert results["deaths"] == []
        assert results["wolf_target"] is None
        assert results["converted"] is None


# ═══════════════════════════════════════════════════════════
#  get_player_by_pseudo : recherche étendue
# ═══════════════════════════════════════════════════════════

class TestGetPlayerByPseudo:
    """Vérifie la recherche étendue de joueurs."""

    def test_by_pseudo(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("Alice") is not None

    def test_by_pseudo_case_insensitive(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("alice") is not None

    def test_by_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("@alice:matrix.org")
        assert p is not None
        assert p.user_id == "@alice:matrix.org"

    def test_by_partial_matrix_id(self):
        game = GameManager()
        game.add_player("Alice", "@alice:matrix.org")
        p = game.get_player_by_pseudo("alice:matrix.org")
        assert p is not None

    def test_by_display_name(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        game.players["user_1"].display_name = "Alice Wonderland"
        p = game.get_player_by_pseudo("Alice Wonderland")
        assert p is not None

    def test_not_found(self):
        game = GameManager()
        game.add_player("Alice", "user_1")
        assert game.get_player_by_pseudo("NotExist") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
