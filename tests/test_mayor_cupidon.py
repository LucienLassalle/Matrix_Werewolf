"""Tests pour la succession du maire et la règle CUPIDON_WINS_WITH_COUPLE."""

import pytest
from models.player import Player
from models.enums import RoleType, ActionType, Team, GamePhase
from roles import RoleFactory
from game.game_manager import GameManager
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
#  Succession du Maire
# ═══════════════════════════════════════════════════════════

class TestMayorSuccession:
    """Tests de la succession du maire quand il meurt."""

    def test_mayor_death_triggers_succession(self):
        """Quand le maire meurt, _pending_mayor_succession est set."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=False)
        
        assert not mayor.is_alive
        assert not mayor.is_mayor  # is_mayor reset to False
        assert game._pending_mayor_succession == mayor
    
    def test_non_mayor_death_no_succession(self):
        """Quand un non-maire meurt, pas de succession."""
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        villager = game.players["v1"]
        
        game.kill_player(villager, killed_during_day=False)
        
        assert game._pending_mayor_succession is None
    
    def test_designate_mayor_success(self):
        """Le maire mort peut désigner un successeur vivant."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        successor = game.players["s1"]
        
        game.kill_player(mayor, killed_during_day=True)
        assert game._pending_mayor_succession == mayor
        
        result = game.designate_mayor(successor)
        
        assert result["success"]
        assert successor.is_mayor
        assert game._pending_mayor_succession is None
        assert result["new_mayor"] == successor
    
    def test_designate_dead_player_fails(self):
        """On ne peut pas désigner un joueur mort comme successeur."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        dead_target = game.players["d1"]
        dead_target.is_alive = False
        
        game.kill_player(mayor, killed_during_day=True)
        result = game.designate_mayor(dead_target)
        
        assert not result["success"]
        assert "vivant" in result["message"]
    
    def test_designate_without_pending_fails(self):
        """designate_mayor échoue s'il n'y a pas de succession en cours."""
        game = make_game(
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        target = game.players["v1"]
        
        result = game.designate_mayor(target)
        
        assert not result["success"]
        assert "Aucune succession" in result["message"]
    
    def test_auto_designate_mayor(self):
        """Le maire est auto-désigné aléatoirement si timeout."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Vivant1", "v1", RoleType.VILLAGEOIS),
            ("Vivant2", "v2", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        assert game._pending_mayor_succession is not None
        
        new_mayor = game.auto_designate_mayor()
        
        assert new_mayor is not None
        assert new_mayor.is_alive
        assert new_mayor.is_mayor
        assert game._pending_mayor_succession is None
    
    def test_auto_designate_no_living_players(self):
        """auto_designate_mayor avec aucun vivant retourne None."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        wolf = game.players["w1"]
        wolf.is_alive = False
        
        game.kill_player(mayor, killed_during_day=True)
        new_mayor = game.auto_designate_mayor()
        
        assert new_mayor is None
    
    def test_mayor_lover_cascade(self):
        """Quand le maire meurt via cascade amoureux, la succession se déclenche."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Amoureux", "a1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        amoureux = game.players["a1"]
        
        # Marier le maire avec l'amoureux
        mayor.lover = amoureux
        amoureux.lover = mayor
        
        # Tuer l'amoureux → le maire meurt aussi
        game.kill_player(amoureux, killed_during_day=False)
        
        assert not mayor.is_alive
        assert not amoureux.is_alive
        # Le maire est détecté comme mort → succession
        assert game._pending_mayor_succession == mayor
    
    def test_lover_is_mayor_dies_by_cascade(self):
        """Quand l'amoureux qui est maire meurt, la succession se déclenche."""
        game = make_game(
            ("Joueur", "j1", RoleType.VILLAGEOIS),
            ("MaireAmoureux", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        joueur = game.players["j1"]
        maire_amoureux = game.players["m1"]
        maire_amoureux.is_mayor = True
        
        joueur.lover = maire_amoureux
        maire_amoureux.lover = joueur
        
        # Tuer le joueur → le maire-amoureux meurt aussi
        game.kill_player(joueur, killed_during_day=True)
        
        assert not joueur.is_alive
        assert not maire_amoureux.is_alive
        assert game._pending_mayor_succession == maire_amoureux
    
    def test_get_mayor(self):
        """get_mayor retourne le maire vivant."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        assert game.get_mayor() == mayor
        
        mayor.is_alive = False
        assert game.get_mayor() is None


# ═══════════════════════════════════════════════════════════
#  Commande /maire via CommandHandler
# ═══════════════════════════════════════════════════════════

class TestMaireCommand:
    """Tests de la commande /maire pour la succession."""

    def test_maire_command_success(self):
        """Le maire mort peut utiliser /maire pour désigner un successeur."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        
        result = handler.execute_command("m1", "maire", ["Successeur"])
        
        assert result["success"]
        assert game.players["s1"].is_mayor
        assert game._pending_mayor_succession is None
    
    def test_maire_command_dead_non_mayor_fails(self):
        """Un joueur mort non-maire ne peut pas utiliser /maire."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        dead = game.players["d1"]
        dead.is_alive = False
        
        # d1 est mort mais pas le maire → la commande est bloquée par "Vous êtes mort"
        result = handler.execute_command("d1", "maire", ["Maire"])
        
        assert not result["success"]
        assert "mort" in result["message"].lower()
    
    def test_maire_command_alive_player_fails(self):
        """Un joueur vivant ne peut pas utiliser /maire (pas de succession en cours pour lui)."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        
        # v1 est vivant mais ce n'est pas lui le maire mort
        result = handler.execute_command("v1", "maire", ["Loup"])
        
        assert not result["success"]
    
    def test_maire_command_no_args(self):
        """La commande /maire sans argument échoue."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        
        result = handler.execute_command("m1", "maire", [])
        
        assert not result["success"]
        assert "Usage" in result["message"]
    
    def test_maire_command_invalid_target(self):
        """La commande /maire avec un pseudo inexistant échoue."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        
        result = handler.execute_command("m1", "maire", ["Inexistant"])
        
        assert not result["success"]
        assert "non trouvé" in result["message"]
    
    def test_maire_via_handle_command(self):
        """Le handle_command (cible résolue) fonctionne aussi."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Successeur", "s1", RoleType.VILLAGEOIS),
            ("Loup", "w1", RoleType.LOUP_GAROU),
        )
        handler = CommandHandler(game)
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        game.kill_player(mayor, killed_during_day=True)
        
        result = handler.handle_command("m1", "maire", "Successeur")
        
        assert result["success"]
        assert game.players["s1"].is_mayor


# ═══════════════════════════════════════════════════════════
#  CUPIDON_WINS_WITH_COUPLE
# ═══════════════════════════════════════════════════════════

class TestCupidonWinsWithCouple:
    """Tests de la condition de victoire Couple + Cupidon."""

    def test_couple_wins_2_alive_standard(self):
        """Victoire classique du couple : 2 derniers vivants amoureux."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False
        
        assert game.check_win_condition() == Team.COUPLE
    
    def test_couple_cupidon_wins_3_alive_enabled(self):
        """Avec option activée, Couple + Cupidon gagnent à 3 vivants."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True
        
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False
        
        assert game.check_win_condition() == Team.COUPLE
    
    def test_couple_cupidon_no_win_3_alive_disabled(self):
        """Avec option désactivée, Couple + Cupidon ne gagnent PAS à 3 vivants."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = False
        
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False
        
        # 3 vivants, option False → pas de victoire
        assert game.check_win_condition() is None
    
    def test_cupidon_in_couple_always_wins(self):
        """Si Cupidon est un des amoureux, il gagne avec le couple (indép. du flag)."""
        game = make_game(
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Amoureux", "a1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.LOUP_GAROU),
        )
        game.cupidon_wins_with_couple = False
        
        cupidon = game.players["c1"]
        amoureux = game.players["a1"]
        cupidon.lover = amoureux
        amoureux.lover = cupidon
        game.players["d1"].is_alive = False
        
        # 2 derniers vivants sont amoureux → couple gagne (Cupidon est dedans)
        assert game.check_win_condition() == Team.COUPLE
    
    def test_3_alive_not_cupidon_no_win(self):
        """3 vivants = 2 amoureux + 1 non-Cupidon → pas de victoire couple."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Villageois", "v1", RoleType.VILLAGEOIS),
            ("Mort", "d1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True
        
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["d1"].is_alive = False
        
        # 3 vivants mais le 3e n'est pas Cupidon → pas de victoire couple
        assert game.check_win_condition() is None
    
    def test_cupidon_dead_couple_wins_alone(self):
        """Si Cupidon est mort, le couple gagne seul (2 derniers vivants)."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
        )
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        game.players["c1"].is_alive = False
        
        assert game.check_win_condition() == Team.COUPLE
    
    def test_4_alive_no_couple_win(self):
        """Avec 4 vivants (2 amoureux + Cupidon + 1), pas de victoire couple."""
        game = make_game(
            ("Amoureux1", "a1", RoleType.VILLAGEOIS),
            ("Amoureux2", "a2", RoleType.LOUP_GAROU),
            ("Cupidon", "c1", RoleType.CUPIDON),
            ("Vivant", "v1", RoleType.VILLAGEOIS),
        )
        game.cupidon_wins_with_couple = True
        
        a1 = game.players["a1"]
        a2 = game.players["a2"]
        a1.lover = a2
        a2.lover = a1
        
        # 4 vivants → trop de monde, pas de victoire couple
        assert game.check_win_condition() is None


# ═══════════════════════════════════════════════════════════
#  Dictateur + Succession Maire
# ═══════════════════════════════════════════════════════════

class TestDictateurMayorSuccession:
    """Tests de la succession quand le Dictateur (devenu maire) meurt."""

    def test_dictateur_becomes_mayor_then_dies(self):
        """Le Dictateur devient maire, puis meurt → succession se déclenche."""
        game = make_game(
            ("Dictateur", "d1", RoleType.DICTATEUR),
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Villageois1", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
            ("Villageois3", "v3", RoleType.VILLAGEOIS),
        )
        game.phase = GamePhase.DAY
        
        dictateur = game.players["d1"]
        loup = game.players["w1"]
        
        # Le Dictateur tue un loup → devient maire
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, loup)
        assert result["success"]
        assert dictateur.is_mayor
        
        # Plus tard, le Dictateur meurt
        game.kill_player(dictateur, killed_during_day=True)
        
        assert not dictateur.is_alive
        assert game._pending_mayor_succession == dictateur
    
    def test_mayor_succession_after_vote_death(self):
        """Le maire meurt par vote du village → succession."""
        game = make_game(
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Villageois1", "v1", RoleType.VILLAGEOIS),
            ("Villageois2", "v2", RoleType.VILLAGEOIS),
            ("Loup1", "w1", RoleType.LOUP_GAROU),
            ("Loup2", "w2", RoleType.LOUP_GAROU),
        )
        game.phase = GamePhase.VOTE
        mayor = game.players["m1"]
        mayor.is_mayor = True
        
        # Simuler le vote
        game.vote_manager.register_player(game.players["v1"])
        game.vote_manager.register_player(game.players["v2"])
        game.vote_manager.register_player(game.players["w1"])
        game.vote_manager.register_player(game.players["w2"])
        game.vote_manager.register_player(mayor)
        
        game.vote_manager.cast_vote(game.players["v1"], mayor)
        game.vote_manager.cast_vote(game.players["w1"], mayor)
        game.vote_manager.cast_vote(game.players["w2"], mayor)
        
        result = game.end_vote_phase()
        
        assert result.get("eliminated") == mayor
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor


# ═══════════════════════════════════════════════════════════
#  Succession du Maire de nuit (audit)
# ═══════════════════════════════════════════════════════════

class TestNightMayorSuccession:
    """Le maire tué pendant la nuit doit déclencher _pending_mayor_succession."""

    def test_wolf_kills_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], mayor)
        result = game.end_night()
        assert result["success"]
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor
        assert mayor.is_mayor is False

    def test_sorciere_poison_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Sorc", "s1", RoleType.SORCIERE),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        sorc = game.players["s1"]
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        sorc.role.perform_action(game, ActionType.POISON, mayor)
        game.action_manager.register_action(sorc, ActionType.POISON, mayor)
        result = game.end_night()
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor

    def test_loup_blanc_kills_mayor_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("LBlanc", "wb1", RoleType.LOUP_BLANC),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        loup_blanc = game.players["wb1"]
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        game.vote_manager.add_wolf_vote(loup_blanc, game.players["a1"])
        loup_blanc.role.night_count = 1
        loup_blanc.role.on_night_start(game)
        r = loup_blanc.role.perform_action(game, ActionType.KILL, mayor)
        assert r["success"]
        game.action_manager.register_action(loup_blanc, ActionType.KILL, mayor)
        result = game.end_night()
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor

    def test_no_succession_if_mayor_survives(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["a1"])
        result = game.end_night()
        assert game.players["m1"].is_alive
        assert game._pending_mayor_succession is None

    def test_mayor_lover_cascade_triggers_succession(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Lover", "l1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
        )
        mayor = game.players["m1"]
        mayor.is_mayor = True
        lover = game.players["l1"]
        mayor.lover = lover
        lover.lover = mayor
        game.vote_manager.add_wolf_vote(game.players["w1"], lover)
        result = game.end_night()
        assert not lover.is_alive
        assert not mayor.is_alive
        assert game._pending_mayor_succession == mayor


class TestEndNightMayorIntegration:
    """resolve_night() détecte correctement la mort du maire."""

    def test_resolve_night_mayor_killed_by_wolves(self):
        game = make_game(
            ("Loup", "w1", RoleType.LOUP_GAROU),
            ("Maire", "m1", RoleType.VILLAGEOIS),
            ("Alice", "a1", RoleType.VILLAGEOIS),
            ("Bob", "b1", RoleType.VILLAGEOIS),
            ("Eve", "e1", RoleType.VILLAGEOIS),
        )
        game.players["m1"].is_mayor = True
        game.vote_manager.add_wolf_vote(game.players["w1"], game.players["m1"])
        result = game.resolve_night()
        assert "m1" in result["deaths"]
        assert game._pending_mayor_succession is not None
        assert game.players["m1"].is_mayor is False
