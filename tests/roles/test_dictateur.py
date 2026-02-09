"""Tests complets du rôle Dictateur.

Couvre :
- Coup d'état réussi (cible loup → devient maire)
- Coup d'état raté (cible innocente → mort du Dictateur)
- Auto-ciblage interdit
- Un seul maire après coup d'état (destitution de l'ancien maire)
- Coup d'état pendant la phase VOTE → annulation du vote
- Poids de vote ×2 uniquement pour le nouveau maire
"""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def make_game(*specs) -> GameManager:
    """Crée une partie avec les joueurs/rôles donnés."""
    game = GameManager()
    for pseudo, uid, rt in specs:
        game.add_player(pseudo, uid)
        role = RoleFactory.create_role(rt)
        role.assign_to_player(game.players[uid])
    game.phase = GamePhase.NIGHT
    return game


# ═══════════════════════════════════════════════════════════
#  Coup d'état — résultat selon la cible
# ═══════════════════════════════════════════════════════════

class TestDictateurCoupDetat:
    """Le Dictateur tue une cible de jour : loup → il devient maire, sinon il meurt."""

    def test_kill_wolf_becomes_mayor(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        result = game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        assert result["success"]
        assert result["became_mayor"]
        assert game.players["d1"].is_mayor
        assert not game.players["w1"].is_alive

    def test_kill_innocent_both_die(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        result = game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["a1"]
        )
        assert result["success"]
        assert not result["became_mayor"]
        assert not game.players["a1"].is_alive
        assert not game.players["d1"].is_alive
        assert game.players["d1"].is_mayor is False

    def test_cannot_act_at_night(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        # Phase par défaut = NIGHT
        result = game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        assert not result["success"]

    def test_power_single_use(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup1", "w1", RoleType.LOUP_GAROU),
            ("Loup2", "w2", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        result = game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w2"]
        )
        assert not result["success"]


# ═══════════════════════════════════════════════════════════
#  Auto-ciblage interdit
# ═══════════════════════════════════════════════════════════

class TestDictateurSelfTarget:
    """Le Dictateur ne peut pas se cibler lui-même."""

    def test_self_target_rejected(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        result = game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["d1"]
        )
        assert not result["success"]
        assert game.players["d1"].is_alive
        assert not game.players["d1"].role.has_used_power


# ═══════════════════════════════════════════════════════════
#  Maire unique — pas de doublon
# ═══════════════════════════════════════════════════════════

class TestDictateurMayor:
    """Vérifie qu'il n'y a jamais deux maires après un coup d'état."""

    def test_old_mayor_destituted(self):
        """L'ancien maire perd son titre quand le Dictateur prend le pouvoir."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["m1"].is_mayor = True

        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )

        assert game.players["d1"].is_mayor is True
        assert game.players["m1"].is_mayor is False
        assert game._pending_mayor_succession is None

    def test_wolf_mayor_killed_no_succession(self):
        """Si la cible loup était aussi maire, pas de succession parasite."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("LoupMaire", "wm1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["wm1"].is_mayor = True

        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["wm1"]
        )

        assert game.players["d1"].is_mayor is True
        assert game.players["wm1"].is_mayor is False
        assert game._pending_mayor_succession is None

    def test_no_existing_mayor(self):
        """Sans maire existant, le Dictateur devient le seul maire."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        mayors = [p for p in game.players.values() if p.is_mayor]
        assert len(mayors) == 1
        assert mayors[0].user_id == "d1"

    def test_exactly_one_mayor_invariant(self):
        """Invariant : exactement un maire vivant après le coup d'état."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["m1"].is_mayor = True
        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        living_mayors = [p for p in game.get_living_players() if p.is_mayor]
        assert len(living_mayors) == 1
        assert living_mayors[0].user_id == "d1"


# ═══════════════════════════════════════════════════════════
#  Vote — poids ×2 uniquement pour le nouveau maire
# ═══════════════════════════════════════════════════════════

class TestDictateurVoteWeight:
    """Après le coup d'état, seul le Dictateur-maire a le poids ×2."""

    def test_vote_weight_single_mayor(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["m1"].is_mayor = True
        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )

        game.phase = GamePhase.VOTE
        game.vote_manager.clear_votes()
        game.vote_manager.cast_vote(game.players["m1"], game.players["a1"])
        game.vote_manager.cast_vote(game.players["d1"], game.players["b1"])

        counts = game.vote_manager.count_votes()
        assert counts.get("a1", 0) == 1   # Ancien maire → poids 1
        assert counts.get("b1", 0) == 2   # Nouveau maire → poids 2


# ═══════════════════════════════════════════════════════════
#  Coup d'état pendant phase VOTE → annulation du vote
# ═══════════════════════════════════════════════════════════

class TestDictateurDuringVotePhase:
    """Le coup d'état pendant le VOTE doit annuler le vote en cours."""

    def test_cancels_vote_phase(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.VOTE
        game.vote_manager.cast_vote(game.players["a1"], game.players["e1"])
        game.vote_manager.cast_vote(game.players["b1"], game.players["e1"])

        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )

        assert game.phase == GamePhase.DAY
        assert game.vote_manager.votes == {}

    def test_no_double_kill(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.VOTE
        game.vote_manager.cast_vote(game.players["b1"], game.players["a1"])
        game.vote_manager.cast_vote(game.players["e1"], game.players["a1"])

        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        assert not game.players["w1"].is_alive

        result = game.end_vote_phase()
        assert not result["success"]
        assert game.players["a1"].is_alive

    def test_during_day_does_not_clear_votes(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["w1"]
        )
        assert game.phase == GamePhase.DAY

    def test_innocent_during_vote_also_cancels(self):
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.VOTE
        game.vote_manager.cast_vote(game.players["w1"], game.players["b1"])

        game.players["d1"].role.perform_action(
            game, ActionType.DICTATOR_KILL, game.players["a1"]
        )

        assert not game.players["a1"].is_alive
        assert not game.players["d1"].is_alive
        assert game.phase == GamePhase.DAY
        assert game.vote_manager.votes == {}
        assert game.players["b1"].is_alive


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
