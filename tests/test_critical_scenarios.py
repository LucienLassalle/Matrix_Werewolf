"""Tests critiques : scénarios de jeu qui peuvent casser la logique.

Vérifie les cas limites identifiés lors de l'audit :
1. Chasseur tue le dernier loup → victoire village
2. Couple meurt en cascade (nuit + jour)
3. Garde protège AVANT que le loup mange
4. Sorcière guérit APRÈS le vote des loups
5. Enfant Sauvage devient loup quand son mentor meurt
6. Dictateur tue un innocent → les deux meurent
"""

import pytest
from game.game_manager import GameManager
from game.action_manager import ActionManager
from models.enums import RoleType, GamePhase, Team, ActionType
from models.player import Player
from roles import RoleFactory


def setup_game(n_players=5, roles=None):
    """Crée une partie prête à jouer avec des rôles forcés.
    
    Les rôles obligatoires (SORCIERE, VOYANTE, CHASSEUR) sont 
    automatiquement ajoutés s'ils ne sont pas dans la config.
    Le nombre de joueurs est ajusté si nécessaire.
    """
    game = GameManager(db_path=":memory:")
    
    if roles:
        roles = dict(roles)  # Copier pour ne pas modifier l'original
        # Injecter les rôles obligatoires si manquants
        mandatory = {RoleType.SORCIERE: 1, RoleType.VOYANTE: 1, RoleType.CHASSEUR: 1}
        for rt, count in mandatory.items():
            if rt not in roles:
                roles[rt] = count
        # Ajuster le nombre de joueurs si nécessaire
        total_roles = sum(roles.values())
        n_players = max(n_players, total_roles)
    
    for i in range(n_players):
        game.add_player(f"P{i}", f"@p{i}:test")
    
    if roles:
        game.set_roles(roles)
    
    result = game.start_game()
    assert result["success"], f"Impossible de démarrer : {result.get('message')}"
    return game


def force_roles(game, role_map: dict):
    """Force les rôles après start_game.
    
    role_map: {user_id: RoleType}
    """
    for uid, rt in role_map.items():
        player = game.get_player(uid)
        assert player, f"Joueur {uid} introuvable"
        role = RoleFactory.create_role(rt)
        role.assign_to_player(player)
        game.vote_manager.register_player(player)


# ============================================================
# 1. CHASSEUR TUE LE DERNIER LOUP → VICTOIRE VILLAGE
# ============================================================

class TestChasseurKillsLastWolf:
    """Le Chasseur tire et tue le dernier loup → le village gagne."""
    
    def test_chasseur_kills_last_wolf_triggers_victory(self):
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 3})
        
        # Identifier les rôles
        chasseur = wolf = None
        for p in game.players.values():
            if p.role.role_type == RoleType.CHASSEUR:
                chasseur = p
            elif p.role.role_type == RoleType.LOUP_GAROU:
                wolf = p
        
        assert chasseur and wolf
        
        # Tuer le chasseur (le loup le mange)
        chasseur.kill()
        chasseur.role.killed_during_day = False
        chasseur.role.can_shoot_now = True
        
        # Le chasseur tire sur le dernier loup
        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)
        assert result["success"], f"Chasseur n'a pas pu tirer : {result.get('message')}"
        
        # Le loup est mort
        assert not wolf.is_alive
        
        # Vérifier la victoire du village
        winner = game.check_win_condition()
        assert winner == Team.GENTIL, f"Le village devrait gagner, mais winner={winner}"
    
    def test_chasseur_kills_wolf_lover_cascade(self):
        """Le Chasseur tue un loup en couple → l'amoureux meurt aussi."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 3})
        
        chasseur = wolf = villager = None
        for p in game.players.values():
            if p.role.role_type == RoleType.CHASSEUR:
                chasseur = p
            elif p.role.role_type == RoleType.LOUP_GAROU:
                wolf = p
            elif villager is None:
                villager = p
        
        # Mettre le loup en couple avec un villageois
        wolf.lover = villager
        villager.lover = wolf
        
        # Tuer le chasseur et le faire tirer
        chasseur.kill()
        chasseur.role.can_shoot_now = True
        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)
        assert result["success"]
        
        # Le loup ET son amoureux sont morts
        assert not wolf.is_alive
        assert not villager.is_alive
        
        # La liste des morts inclut les deux
        deaths = result.get("deaths", [])
        dead_ids = {d.user_id for d in deaths}
        assert wolf.user_id in dead_ids
        assert villager.user_id in dead_ids


# ============================================================
# 2. COUPLE : MORT EN CASCADE (NUIT ET JOUR)
# ============================================================

class TestCoupleDeathCascade:
    """Si un amoureux meurt, l'autre meurt aussi — toujours."""
    
    def test_wolf_kills_lover_both_die_at_night(self):
        """Les loups tuent un amoureux → les deux meurent la nuit."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1, v2 = [p for p in players if p.role.role_type == RoleType.VILLAGEOIS][:2]
        
        # Marier v1 et v2
        v1.lover = v2
        v2.lover = v1
        
        # Les loups votent pour v1
        game.vote_manager.cast_vote(wolf, v1, is_wolf_vote=True)
        
        # Résoudre la nuit
        results = game.action_manager.execute_night_actions(game)
        
        # Les deux amoureux sont dans les morts
        dead_ids = {d.user_id for d in results["deaths"]}
        assert v1.user_id in dead_ids, "v1 devrait être mort (tué par les loups)"
        assert v2.user_id in dead_ids, "v2 devrait être mort (cascade amoureux)"
    
    def test_vote_kills_lover_both_die_at_day(self):
        """Le village élimine un amoureux → les deux meurent le jour."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1, v2 = [p for p in players if p.role.role_type == RoleType.VILLAGEOIS][:2]
        
        # Marier v1 et v2
        v1.lover = v2
        v2.lover = v1
        
        # Passer au vote
        game.phase = GamePhase.VOTE
        game.vote_manager.reset_votes()
        
        # Tout le monde vote v1
        for p in players:
            if p.is_alive and p != v1:
                game.vote_manager.cast_vote(p, v1)
        
        result = game.end_vote_phase()
        
        assert result.get("eliminated") == v1
        assert not v1.is_alive
        assert not v2.is_alive
        
        # all_deaths doit contenir les deux
        all_deaths = result.get("all_deaths", [])
        dead_ids = {d.user_id for d in all_deaths}
        assert v1.user_id in dead_ids
        assert v2.user_id in dead_ids
    
    def test_couple_wolf_village_win_together(self):
        """Un couple loup+villageois → seule façon de gagner = être les 2 derniers."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1 = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Marier le loup et un villageois
        wolf.lover = v1
        v1.lover = wolf
        
        # Tuer tous les autres
        for p in players:
            if p != wolf and p != v1:
                p.kill()
        
        # Il reste le couple → victoire COUPLE
        winner = game.check_win_condition()
        assert winner == Team.COUPLE, f"Le couple devrait gagner, mais winner={winner}"


# ============================================================
# 3. GARDE PROTÈGE → LOUP NE MANGE PAS
# ============================================================

class TestGardeProtection:
    """La protection du Garde empêche le meurtre des loups."""
    
    def test_garde_saves_wolf_target(self):
        """Le Garde protège la cible des loups → personne ne meurt."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        target = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Le Garde protège la cible
        result = garde.role.perform_action(game, ActionType.PROTECT, target)
        assert result["success"]
        game.action_manager.register_action(garde, ActionType.PROTECT, target)
        
        # Les loups votent pour la même cible
        game.vote_manager.cast_vote(wolf, target, is_wolf_vote=True)
        
        # Résoudre la nuit
        results = game.action_manager.execute_night_actions(game)
        
        # Personne ne meurt
        assert len(results["deaths"]) == 0, "Personne ne devrait mourir (protégé par le Garde)"
        assert target.is_alive
    
    def test_garde_does_not_block_sorciere_poison(self):
        """Le Garde ne protège PAS contre le poison de la Sorcière."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1, 
            RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 2
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Le Garde protège la victime
        garde.role.perform_action(game, ActionType.PROTECT, victim)
        game.action_manager.register_action(garde, ActionType.PROTECT, victim)
        
        # La Sorcière empoisonne la victime
        sorciere.role.perform_action(game, ActionType.POISON, victim)
        game.action_manager.register_action(sorciere, ActionType.POISON, victim)
        
        # Les loups votent pour quelqu'un d'autre
        other = next(p for p in players if p != victim and p.role.role_type == RoleType.VILLAGEOIS)
        game.vote_manager.cast_vote(wolf, other, is_wolf_vote=True)
        
        results = game.action_manager.execute_night_actions(game)
        
        # La victime est morte (poison ignore la protection)
        assert not victim.is_alive, "La victime devrait mourir (poison ignore la protection du Garde)"


# ============================================================
# 4. SORCIÈRE : HEAL ANNULE LE MEURTRE DU LOUP
# ============================================================

class TestSorciereHeal:
    """La Sorcière peut sauver la cible des loups."""
    
    def test_sorciere_heals_wolf_target(self):
        """La Sorcière utilise la potion de vie → la victime survit."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Les loups votent
        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)
        
        # La Sorcière sauve
        sorciere.role.perform_action(game, ActionType.HEAL, victim)
        game.action_manager.register_action(sorciere, ActionType.HEAL, victim)
        
        results = game.action_manager.execute_night_actions(game)
        
        assert victim.is_alive, "La victime devrait survivre (sauvée par la Sorcière)"
        assert len(results["deaths"]) == 0
        assert victim in [p for p in results.get("saved", [])]
    
    def test_sorciere_heal_and_poison_same_night(self):
        """La Sorcière peut utiliser les deux potions la même nuit."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        villagers = [p for p in players if p.role.role_type == RoleType.VILLAGEOIS]
        v1, v2 = villagers[0], villagers[1]
        
        # Les loups votent pour v1
        game.vote_manager.cast_vote(wolf, v1, is_wolf_vote=True)
        
        # La Sorcière sauve v1 et empoisonne v2
        sorciere.role.perform_action(game, ActionType.HEAL, v1)
        game.action_manager.register_action(sorciere, ActionType.HEAL, v1)
        sorciere.role.perform_action(game, ActionType.POISON, v2)
        game.action_manager.register_action(sorciere, ActionType.POISON, v2)
        
        results = game.action_manager.execute_night_actions(game)
        
        assert v1.is_alive, "v1 devrait survivre (sauvée)"
        assert not v2.is_alive, "v2 devrait mourir (empoisonnée)"


# ============================================================
# 5. ENFANT SAUVAGE : MENTOR MEURT → DEVIENT LOUP
# ============================================================

class TestEnfantSauvageConversion:
    """L'Enfant Sauvage devient loup quand son mentor meurt."""
    
    def test_mentor_killed_by_wolves_enfant_becomes_wolf(self):
        """Le mentor est tué par les loups → l'Enfant Sauvage devient loup."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.ENFANT_SAUVAGE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        enfant = next(p for p in players if p.role.role_type == RoleType.ENFANT_SAUVAGE)
        mentor = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # L'enfant choisit un mentor
        enfant.role.perform_action(game, ActionType.CHOOSE_MENTOR, mentor)
        assert enfant.mentor == mentor
        
        # Avant la mort du mentor : Enfant est gentil
        assert enfant.get_team() == Team.GENTIL
        
        # Les loups tuent le mentor
        game.vote_manager.cast_vote(wolf, mentor, is_wolf_vote=True)
        
        # Résoudre via end_night (qui appelle on_player_death)
        result = game.end_night()
        
        # L'enfant est maintenant un loup !
        assert enfant.role.role_type == RoleType.LOUP_GAROU, \
            f"L'enfant devrait être loup, mais est {enfant.role.role_type}"
        assert enfant.get_team() == Team.MECHANT
        assert enfant.is_alive
    
    def test_mentor_killed_by_vote_enfant_becomes_wolf(self):
        """Le mentor est éliminé par vote → l'Enfant Sauvage devient loup."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.ENFANT_SAUVAGE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        enfant = next(p for p in players if p.role.role_type == RoleType.ENFANT_SAUVAGE)
        mentor = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # L'enfant choisit un mentor
        enfant.role.perform_action(game, ActionType.CHOOSE_MENTOR, mentor)
        
        # Résoudre la nuit (personne ne meurt, on passe au jour)
        game.end_night()
        
        # Passer au vote
        game.start_vote_phase()
        
        # Tout le monde vote pour le mentor
        for p in game.get_living_players():
            if p != mentor:
                game.vote_manager.cast_vote(p, mentor)
        
        result = game.end_vote_phase()
        
        assert not mentor.is_alive, "Le mentor devrait être mort"
        assert enfant.role.role_type == RoleType.LOUP_GAROU, \
            "L'enfant devrait être devenu loup après la mort du mentor"
        assert enfant.get_team() == Team.MECHANT


# ============================================================
# 6. DICTATEUR : TUE INNOCENT → LES DEUX MEURENT
# ============================================================

class TestDictateur:
    """Le Dictateur tue : si c'est un loup il devient maire, sinon il meurt."""
    
    def test_dictateur_kills_wolf_becomes_mayor(self):
        """Le Dictateur tue un loup → il devient maire."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.DICTATEUR: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        dictateur = next(p for p in players if p.role.role_type == RoleType.DICTATEUR)
        
        # Le dictateur frappe pendant le jour
        game.phase = GamePhase.DAY
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, wolf)
        
        assert result["success"]
        assert not wolf.is_alive
        assert dictateur.is_alive
        assert dictateur.is_mayor
    
    def test_dictateur_kills_innocent_both_die(self):
        """Le Dictateur tue un villageois → les deux meurent."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.DICTATEUR: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        dictateur = next(p for p in players if p.role.role_type == RoleType.DICTATEUR)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        game.phase = GamePhase.DAY
        result = dictateur.role.perform_action(game, ActionType.DICTATOR_KILL, victim)
        
        assert result["success"]
        assert not victim.is_alive
        assert not dictateur.is_alive
        
        # La liste des morts doit contenir les deux
        deaths = result.get("deaths", [])
        dead_ids = {d.user_id for d in deaths}
        assert victim.user_id in dead_ids
        assert dictateur.user_id in dead_ids


# ============================================================
# 7. ORDRE DE RÉSOLUTION : GARDE → LOUPS → SORCIÈRE → LOUP BLANC
# ============================================================

class TestNightResolutionOrder:
    """L'ordre de résolution de la nuit est correct."""
    
    def test_garde_before_wolves(self):
        """Le Garde agit AVANT les loups dans la résolution."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.GARDE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        garde = next(p for p in players if p.role.role_type == RoleType.GARDE)
        target = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Garde protège ET loups votent pour la même cible
        game.action_manager.register_action(garde, ActionType.PROTECT, target)
        target.is_protected = True
        game.vote_manager.cast_vote(wolf, target, is_wolf_vote=True)
        
        results = game.action_manager.execute_night_actions(game)
        
        assert target.is_alive
        assert len(results["deaths"]) == 0
    
    def test_sorciere_after_wolves(self):
        """La Sorcière peut sauver car elle agit APRÈS le vote des loups."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 3
        })
        
        players = list(game.players.values())
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)
        
        sorciere.role.perform_action(game, ActionType.HEAL, victim)
        game.action_manager.register_action(sorciere, ActionType.HEAL, victim)
        
        results = game.action_manager.execute_night_actions(game)
        
        # La Sorcière agit après → peut sauver
        assert victim.is_alive
    
    def test_loup_blanc_after_sorciere(self):
        """Le Loup Blanc agit APRÈS la Sorcière (la Sorcière ne peut pas le sauver)."""
        game = setup_game(5, {
            RoleType.LOUP_GAROU: 1, RoleType.LOUP_BLANC: 1, 
            RoleType.SORCIERE: 1, RoleType.VILLAGEOIS: 2
        })
        
        players = list(game.players.values())
        lb = next(p for p in players if p.role.role_type == RoleType.LOUP_BLANC)
        sorciere = next(p for p in players if p.role.role_type == RoleType.SORCIERE)
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        victim = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Le Loup Blanc tue un autre loup (la nuit paire)
        lb.role.can_kill_tonight = True
        lb.role.perform_action(game, ActionType.KILL, wolf)
        game.action_manager.register_action(lb, ActionType.KILL, wolf)
        
        # Les loups votent pour un villageois
        game.vote_manager.cast_vote(lb, victim, is_wolf_vote=True)
        game.vote_manager.cast_vote(wolf, victim, is_wolf_vote=True)
        
        results = game.action_manager.execute_night_actions(game)
        
        # Les deux sont morts (le loup normal par le Loup Blanc, le villageois par les loups)
        dead_ids = {d.user_id for d in results["deaths"]}
        assert wolf.user_id in dead_ids
        assert victim.user_id in dead_ids


# ============================================================
# 8. CONDITIONS DE VICTOIRE EDGE CASES
# ============================================================

class TestVictoryConditions:
    """Tests des conditions de victoire dans les cas limites."""
    
    def test_all_wolves_dead_village_wins(self):
        """Plus aucun loup vivant → le village gagne."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        wolf = next(p for p in game.players.values() if p.role.role_type == RoleType.LOUP_GAROU)
        wolf.kill()
        
        assert game.check_win_condition() == Team.GENTIL
    
    def test_only_wolves_alive_wolves_win(self):
        """Il ne reste que des loups → les loups gagnent."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 2, RoleType.VILLAGEOIS: 3})
        
        for p in game.players.values():
            if p.get_team() == Team.GENTIL:
                p.kill()
        
        assert game.check_win_condition() == Team.MECHANT
    
    def test_loup_blanc_solo_neutral_win(self):
        """Le Loup Blanc est le seul survivant → victoire neutre."""
        game = setup_game(5, {RoleType.LOUP_BLANC: 1, RoleType.VILLAGEOIS: 4})
        
        lb = next(p for p in game.players.values() if p.role.role_type == RoleType.LOUP_BLANC)
        for p in game.players.values():
            if p != lb:
                p.is_alive = False
        
        assert game.check_win_condition() == Team.NEUTRE
    
    def test_couple_last_two_alive_couple_wins(self):
        """Les 2 derniers vivants sont amoureux (équipes différentes) → le couple gagne."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        players = list(game.players.values())
        # Forcer un couple loup + villageois (équipes mixtes → COUPLE)
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        villager = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        wolf.lover = villager
        villager.lover = wolf
        
        for p in players:
            if p not in (wolf, villager):
                p.is_alive = False
        
        assert game.check_win_condition() == Team.COUPLE
    
    def test_couple_same_team_wins_as_team(self):
        """Les 2 derniers vivants sont amoureux de la même équipe → l'équipe gagne (pas COUPLE)."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        players = list(game.players.values())
        villagers = [p for p in players if p.role.role_type == RoleType.VILLAGEOIS]
        p1, p2 = villagers[0], villagers[1]
        p1.lover = p2
        p2.lover = p1
        
        for p in players:
            if p not in (p1, p2):
                p.is_alive = False
        
        assert game.check_win_condition() == Team.GENTIL
    
    def test_everyone_dead_neutral(self):
        """Tout le monde est mort → neutre."""
        game = setup_game(5, {RoleType.LOUP_GAROU: 1, RoleType.VILLAGEOIS: 4})
        
        for p in game.players.values():
            p.is_alive = False
        
        assert game.check_win_condition() == Team.NEUTRE
    
    def test_chasseur_kills_last_wolf_with_lover(self):
        """Chasseur tue le dernier loup qui est en couple → l'amoureux meurt aussi → village gagne."""
        game = setup_game(6, {
            RoleType.LOUP_GAROU: 1, RoleType.CHASSEUR: 1, RoleType.VILLAGEOIS: 4
        })
        
        players = list(game.players.values())
        chasseur = next(p for p in players if p.role.role_type == RoleType.CHASSEUR)
        wolf = next(p for p in players if p.role.role_type == RoleType.LOUP_GAROU)
        v1 = next(p for p in players if p.role.role_type == RoleType.VILLAGEOIS)
        
        # Couple : loup + villageois
        wolf.lover = v1
        v1.lover = wolf
        
        # Le chasseur meurt, puis tire
        chasseur.kill()
        chasseur.role.can_shoot_now = True
        result = chasseur.role.perform_action(game, ActionType.KILL, wolf)
        
        assert not wolf.is_alive
        assert not v1.is_alive  # Cascade amoureux
        
        # Le village gagne (plus de loups)
        assert game.check_win_condition() == Team.GENTIL
