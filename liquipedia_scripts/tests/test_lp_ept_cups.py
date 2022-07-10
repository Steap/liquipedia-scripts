import pytest
import mwclient
import liquipedia_scripts
from liquipedia_scripts.lp_ept_cups import EPTCup
from liquipedia_scripts.lp_ept_cups import LiquipediaPage
from liquipedia_scripts.lp_ept_cups import Match
from liquipedia_scripts.lp_ept_cups import Player
from liquipedia_scripts.lp_ept_cups import RegionEnum


class FakePlayer:
    herO = Player(7831103, 'her0')
    PhleBuster = Player(16597540, 'PhleBuster')
    Reynor = Player(5701196, 'Reynor')
    Serral = Player(6467940, 'Serral')
    Syrril = Player(16616688, 'Syrril')


class TestMatch:
    def test_match(self):
        match_ = Match('Serral', 'Reynor', 0, 0)
        assert match_.winner == 0
        assert not match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 1, 0)
        assert match_.winner == 1
        assert match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 0, 1)
        assert match_.winner == 2
        assert match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 2, 0)
        assert match_.winner == 1
        assert not match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 2, 1)
        assert match_.winner == 1
        assert not match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 0, 2)
        assert match_.winner == 2
        assert not match_.is_forfeit()

        match_ = Match('Serral', 'Reynor', 1, 2)
        assert match_.winner == 2
        assert not match_.is_forfeit()


@pytest.fixture
def eptcup(monkeypatch):
    monkeypatch.setattr(EPTCup, '_get_league_id', lambda *args: 123)
    return EPTCup('EU', 123)


class TestEPTCup:
    def test_participants(self, requests_mock, eptcup):
        url = 'https://api.eslgaming.com/play/v1/leagues'
        url += '/123/contestants?states=checkedIn'
        fake_answer = [{
            "id": 16616688,
            "name": "Syrril",
        }]
        requests_mock.get(url, json=fake_answer)
        assert list(eptcup.participants) == [FakePlayer.Syrril]

    def test_n_rounds(self, eptcup, monkeypatch):
        eptcup._participants = {player_id: 'name' for player_id in range(1)}
        assert eptcup.n_rounds == 0
        eptcup._participants = {player_id: 'name' for player_id in range(2)}
        assert eptcup.n_rounds == 1
        eptcup._participants = {player_id: 'name' for player_id in range(4)}
        assert eptcup.n_rounds == 2
        eptcup._participants = {player_id: 'name' for player_id in range(8)}
        assert eptcup.n_rounds == 3
        eptcup._participants = {player_id: 'name' for player_id in range(9)}
        assert eptcup.n_rounds == 4

    def test_result(self, requests_mock, eptcup):
        players_url = 'https://api.eslgaming.com/play/v1/leagues'
        players_url += '/123/contestants?states=checkedIn'
        fake_players = [{
            "id": 16616688,
            "name": "Syrril",
        }]
        requests_mock.get(players_url, json=fake_players)

        results_url = 'https://api.eslgaming.com/play/v1/leagues/123/results'
        fake_results = [{
            "round": 0,
            "position": 14,
            "participants": [{
                "id": 0,
                "points": [
                  0
                ]
            }, {
                "id": 16616688,
                "points": [
                  1
                ]
            }],
        }]
        requests_mock.get(results_url, json=fake_results)

        assert eptcup.results[0][14] == Match(None, FakePlayer.Syrril, 0, 1)

    def test_result_null_points(self, requests_mock, eptcup):
        # When a match has not yet been played, the ESL API returns the score
        # as being "null to null". In our wrapper class, we use "0 to 0"
        # instead.
        players_url = 'https://api.eslgaming.com/play/v1/leagues'
        players_url += '/123/contestants?states=checkedIn'
        fake_players = [{
            "id": 16616688,
            "name": "Syrril",
        }]
        requests_mock.get(players_url, json=fake_players)

        results_url = 'https://api.eslgaming.com/play/v1/leagues/123/results'
        fake_results = [{
            "round": 0,
            "position": 14,
            "participants": [{
                "id": 0,
                "points": None,
            }, {
                "id": 16616688,
                "points": None,
            }],
        }]
        requests_mock.get(results_url, json=fake_results)

        assert eptcup.results[0][14] == Match(None, FakePlayer.Syrril, 0, 0)


class MockPage:
    def __init__(self, *args, **kwargs):
        self._texts = {
            LiquipediaPage.PARTICIPANTS_SECTION: '''{{ParticipantTable
|p1=someplayer
}}'''
        }

    def text(self, section):
        try:
            return self._texts[section]
        except KeyError:
            raise ValueError(section)

    def edit(self, text, section, *args, **kwargs):
        try:
            self._texts[section] = text
        except KeyError:
            raise ValueError(section)


class MockSite:
    def __init__(self, *args, **kwargs):
        self.pages = {
            'EU/123': MockPage(),
        }


class MockEPTCup:
    def __init__(self, *args, **kwargs):
        self.participants = [
            FakePlayer.herO,
            FakePlayer.Serral,
            FakePlayer.PhleBuster,
            FakePlayer.Syrril
        ]


@pytest.fixture
def liquipedia_page(monkeypatch, tmp_path):
    def mock_site(*args, **kwargs):
        return MockSite()

    @staticmethod
    def fake_get_known_players_file():
        csv_file = tmp_path / 'players.csv'
        csv_file.write_text('''ESL id,LP name,LP link,race,flag,notable
7831103,herO,herO(jOin),,,1
6467940,Serral,,,,1
16616688,Syrril,,z,fr,0
16597540,PhleBuster,,z,fi,0
''')
        return csv_file

    monkeypatch.setattr(liquipedia_scripts.lp_ept_cups, 'EPTCup', MockEPTCup)
    monkeypatch.setattr(LiquipediaPage, '_authenticate', lambda *args: None)
    monkeypatch.setattr(LiquipediaPage, '_get_known_players_file',
                        fake_get_known_players_file)
    monkeypatch.setattr(mwclient, 'Site', mock_site)
    return LiquipediaPage(RegionEnum('EU'), 123, False, '${region}/${edition}')


class TestLiquipediaPage:
    def test__fetch_known_players(self, liquipedia_page):
        known_players = {
            FakePlayer.herO.esl_id: {
                'LP link': 'herO(jOin)',
                'LP name': 'herO',
                'flag': '',
                'notable': '1',
                'race': ''
            },
            FakePlayer.Serral.esl_id: {
                'LP link': '',
                'LP name': 'Serral',
                'flag': '',
                'notable': '1',
                'race': ''
            },
            FakePlayer.PhleBuster.esl_id: {
                'LP link': '',
                'LP name': 'PhleBuster',
                'flag': 'fi',
                'notable': '0',
                'race': 'z'
            },
            FakePlayer.Syrril.esl_id: {
                'LP link': '',
                'LP name': 'Syrril',
                'flag': 'fr',
                'notable': '0',
                'race': 'z'
            },
        }

        assert liquipedia_page.known_players == known_players

    def test_update_notable_participants(self, liquipedia_page):
        expected = '''{{ParticipantTable
|p1=herO|p1link=herO(jOin)
|p2=Serral
}}'''
        liquipedia_page.update_notable_participants()
        text = liquipedia_page.page.text(LiquipediaPage.PARTICIPANTS_SECTION)
        assert expected == text

    def test__lp_round_to_esl_round(self, liquipedia_page):
        with pytest.raises(ValueError):
            liquipedia_page._lp_round_to_esl_round(-1, 7, 5)
        with pytest.raises(ValueError):
            liquipedia_page._lp_round_to_esl_round(0, 7, 5)
        assert liquipedia_page._lp_round_to_esl_round(1, 7, 5) == 2
        assert liquipedia_page._lp_round_to_esl_round(2, 7, 5) == 3
        assert liquipedia_page._lp_round_to_esl_round(3, 7, 5) == 4
        assert liquipedia_page._lp_round_to_esl_round(4, 7, 5) == 5
        assert liquipedia_page._lp_round_to_esl_round(5, 7, 5) == 6

    def test__format_match_result(self, liquipedia_page):
        current_info = {
            'roundno': '1',
            'matchno': '1',
            'bestof': '',
            'p1': 'Serral',
            'p2': 'Reynor',
            'r1': '',
            'r2': '',
            'f1': '',
            'f2': '',
            's1': '',
            's2': '',
        }
        match_ = Match(FakePlayer.Serral, FakePlayer.Reynor, 2, 1)
        expected = self.format_result('Serral', 'Reynor', s1='2', s2='1')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

        match_ = Match(FakePlayer.Serral, FakePlayer.Reynor, 0, 2)
        expected = self.format_result('Serral', 'Reynor', s1='0', s2='2')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

    def test__format_match_result_forfeit(self, liquipedia_page):
        # The ESL returns forfeits as 1-0 wins, but they should be marked
        # "W vs FF" on Liquipedia.
        current_info = {
            'roundno': '1',
            'matchno': '1',
            'bestof': '',
            'p1': 'Serral',
            'p2': 'Reynor',
            'r1': '',
            'r2': '',
            'f1': '',
            'f2': '',
            's1': '',
            's2': '',
        }
        match_ = Match(FakePlayer.Serral, FakePlayer.Reynor, 1, 0)
        expected = self.format_result('Serral', 'Reynor', s1='W', s2='FF')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

        match_ = Match(FakePlayer.Serral, FakePlayer.Reynor, 0, 1)
        expected = self.format_result('Serral', 'Reynor', s1='FF', s2='W')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

    def test__format_match_result_non_notable_players(self, liquipedia_page):
        # In this scenario:
        # - Syrril is offracing as T and recently became German. A human wrote
        #   it all down in the results
        # - A human wrote down the name of PhleBuster, without adding info
        #   about their race/nationality.
        #
        # The script should update PhleBuster's race and flag, but should not
        # overwrite Syrril's race and flag, trusting humans instead.
        current_info = {
            'roundno': '1',
            'matchno': '1',
            'bestof': '',
            'p1': 'Syrril',
            'p2': 'PhleBuster',
            'r1': '|race=t',
            'r2': '',
            'f1': '|flag=de',
            'f2': '',
            's1': '',
            's2': '',
        }
        match_ = Match(FakePlayer.Syrril, FakePlayer.PhleBuster, 0, 0)
        expected = self.format_result('Syrril', 'PhleBuster',
                                      r1='|race=t', f1='|flag=de',
                                      r2='|race=z', f2='|flag=fi')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

    def test__format_match_result_scores(self, liquipedia_page):
        # In this scenario, a human entered the result of the match on
        # Liquipedia before it was available on the ESL website (they probably
        # were watching the stream and were really quick!). The ESL website
        # therefore returns that the match is not over (0-0), and our script
        # should not overwrite the values entered by its human friend.
        current_info = {
            'roundno': '1',
            'matchno': '1',
            'bestof': '',
            'p1': 'Serral',
            'p2': 'Reynor',
            'r1': '',
            'r2': '',
            'f1': '',
            'f2': '',
            's1': '2',
            's2': '0',
        }
        match_ = Match(FakePlayer.Serral, FakePlayer.Reynor, 0, 0)
        expected = self.format_result('Serral', 'Reynor', s1='2', s2='0')
        result = liquipedia_page._format_match_result(match_, current_info)
        assert expected == result

    @staticmethod
    def format_result(p1, p2, roundno='1', matchno='1',
                      bestof='', r1='', r2='', f1='', f2='', s1='', s2=''):
        values = {
            'roundno': roundno,
            'matchno': matchno,
            'bestof': bestof,
            'name1': p1,
            'name2': p2,
            'race1': r1,
            'race2': r2,
            'flag1': f1,
            'flag2': f2,
            'score1': s1,
            'score2': s2,
        }
        return '''|R%(roundno)sM%(matchno)s=%(bestof)s
    |opponent1={{1v1Opponent|1=%(name1)s%(flag1)s%(race1)s|score=%(score1)s}}
    |opponent2={{1v1Opponent|1=%(name2)s%(flag2)s%(race2)s|score=%(score2)s}}
}}''' % values
