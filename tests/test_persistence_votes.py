"""Tests de persistance des votes."""

import os
import tempfile

from models.enums import RoleType, Team
from tests.persistence_helpers import make_game, load_into_new_gm


class TestVotePersistence:
    """Verifie la restauration des votes."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_village_votes_restored(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())
        voter = gm.players[uids[0]]
        target = gm.players[uids[1]]
        gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert uids[0] in gm2.vote_manager.votes
        assert gm2.vote_manager.votes[uids[0]] == uids[1]
        gm2.db.close()
        gm.db.close()

    def test_wolf_votes_restored(self):
        gm = make_game(self.tmp.name)
        wolves = [p for p in gm.players.values() if p.get_team() == Team.MECHANT]
        villagers = [p for p in gm.players.values() if p.get_team() == Team.GENTIL]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)
            gm.save_state()

            gm2 = load_into_new_gm(self.tmp.name)
            assert wolves[0].user_id in gm2.vote_manager.wolf_votes
            assert gm2.vote_manager.wolf_votes[wolves[0].user_id] == villagers[0].user_id
            gm2.db.close()

        gm.db.close()

    def test_mayor_votes_restored(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())
        voter = gm.players[uids[0]]
        candidate = gm.players[uids[1]]
        gm.vote_manager.cast_mayor_vote_for(voter, candidate)
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert uids[0] in gm2.vote_manager.mayor_votes_for
        assert gm2.vote_manager.mayor_votes_for[uids[0]] == uids[1]
        gm2.db.close()
        gm.db.close()

    def test_multiple_votes_restored(self):
        gm = make_game(self.tmp.name, 8, role_config={
            RoleType.LOUP_GAROU: 2,
            RoleType.SORCIERE: 1,
            RoleType.VOYANTE: 1,
            RoleType.CHASSEUR: 1,
            RoleType.VILLAGEOIS: 3,
        })
        uids = list(gm.players.keys())

        for i in range(4):
            voter = gm.players[uids[i]]
            target = gm.players[uids[(i + 1) % len(uids)]]
            gm.vote_manager.cast_vote(voter, target, is_wolf_vote=False)
        gm.save_state()

        gm2 = load_into_new_gm(self.tmp.name)
        assert len(gm2.vote_manager.votes) == 4
        gm2.db.close()
        gm.db.close()


class TestVoteManagerAfterRestore:
    """Verifie que le VoteManager fonctionne normalement apres restauration."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_can_add_votes_after_restore(self):
        gm = make_game(self.tmp.name)
        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        uids = list(gm2.players.keys())
        voter = gm2.players[uids[0]]
        target = gm2.players[uids[1]]
        result = gm2.vote_manager.cast_vote(voter, target)
        assert result["success"]
        gm2.db.close()

    def test_get_most_voted_after_restore(self):
        gm = make_game(self.tmp.name)
        uids = list(gm.players.keys())

        for i in range(3):
            gm.vote_manager.cast_vote(gm.players[uids[i]], gm.players[uids[3]])

        gm.save_state()
        gm.db.close()

        gm2 = load_into_new_gm(self.tmp.name)
        most_voted = gm2.vote_manager.get_most_voted()
        assert most_voted is not None
        assert most_voted.user_id == uids[3]
        gm2.db.close()

    def test_wolf_vote_resolution_after_restore(self):
        gm = make_game(self.tmp.name)
        wolves = [p for p in gm.players.values() if p.get_team() == Team.MECHANT]
        villagers = [p for p in gm.players.values() if p.get_team() == Team.GENTIL]

        if wolves and villagers:
            gm.vote_manager.cast_vote(wolves[0], villagers[0], is_wolf_vote=True)
            gm.save_state()
            gm.db.close()

            gm2 = load_into_new_gm(self.tmp.name)
            wolf_target = gm2.vote_manager.get_most_voted(is_wolf_vote=True)
            assert wolf_target is not None
            assert wolf_target.user_id == villagers[0].user_id
            gm2.db.close()
        else:
            gm.db.close()
