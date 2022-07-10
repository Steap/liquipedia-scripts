#!/usr/bin/env python3
import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from enum import Enum
import importlib.resources as importlib_resources
import math
import os
import re
from string import Template
import sys

import mwclient
import requests


class RegionEnum(str, Enum):
    NA = 'AM'
    EU = 'EU'
    KR = 'KR'


@dataclass
class Player:
    esl_id: int
    esl_name: str


@dataclass
class Match:
    p1: Player
    p2: Player
    s1: int
    s2: int

    def is_forfeit(self) -> bool:
        return ((self.s1 == 1 and self.s2 == 0) or
                (self.s1 == 0 and self.s2 == 1))

    @property
    def winner(self) -> int:
        '''Return the id of the winning player, 0 if the match is not over'''
        if self.s1 == 2:
            return 1
        if self.s2 == 2:
            return 2
        if self.s1 == 1 and self.s2 == 0:
            return 1
        if self.s1 == 0 and self.s2 == 1:
            return 2
        return 0


class EPTCup:
    BASE_URL = 'https://api.eslgaming.com/play/v1/leagues'

    def __init__(self, region: RegionEnum, edition: int):
        self.league_id = self._get_league_id(region, edition)
        self._results = None
        self._participants = None

    def _get_league_id(self, region: RegionEnum, edition: int):
        # We need to get the "league id" from the tournament page (a URL like
        # https://play.eslgaming.com/starcraft/global/sc2/open/1on1-series-korea/cup-125/
        # Unfortunately, sending a GET request to that page triggers Cloudflare
        # and forces us to 1) wait while our browser is being checked 2) fill
        # in a captcha 3) get denied access.
        # Our solution is to get the league ids in advance and keep a list
        # here. We will need to keep it updated or find a better solution.
        return {
            'AM': {
                125: '237935',
                126: '238957',
                127: '238958',
                128: '238959',
                129: '238960',
                130: '240210',
                131: '240211',
                132: '240212',
                133: '240213',
                134: '240214',
            },
            'EU': {
                125: '237930',
                126: '238953',
                127: '238954',
                128: '238955',
                129: '238956',
                130: '240205',
                131: '240206',
                132: '240207',
                133: '240208',
                134: '240209',
            },
            'KR': {
                125: '237925',
                126: '238949',
                127: '238950',
                128: '238951',
                129: '238952',
                130: '240200',
                131: '240201',
                132: '240202',
                133: '240203',
                134: '240204',
            },
        }[region][edition]

    def _fetch_participants(self):
        self._participants = {}
        url = f'{self.BASE_URL}/{self.league_id}/contestants?states=checkedIn'
        r = requests.get(url)
        for pjson in r.json():
            self._participants[pjson['id']] = Player(pjson['id'],
                                                     pjson['name'])

    @property
    def participants(self):
        if self._participants is None:
            self._fetch_participants()
        return self._participants.values()

    @property
    def n_rounds(self) -> int:
        return int(math.ceil(math.log(len(self.participants), 2)))

    def _fetch_results(self):
        self._results = defaultdict(dict)
        url = f'{self.BASE_URL}/{self.league_id}/results'
        r = requests.get(url)
        for jresult in r.json():
            p1 = self._participants.get(jresult['participants'][0]['id'])
            p2 = self._participants.get(jresult['participants'][1]['id'])
            s1 = (jresult['participants'][0]['points'] or [0])[0]
            s2 = (jresult['participants'][1]['points'] or [0])[0]
            roundno = jresult['round']
            matchno = jresult['position']
            match_ = Match(p1, p2, s1, s2)
            self._results[roundno][matchno] = match_

    @property
    def results(self):
        '''Return results indexed by round number and match number

        Individual matches can be accessed by calling:

            results[<round number>][<match number>]
        '''
        if self._participants is None:
            self._fetch_participants()
        if self._results is None:
            self._fetch_results()
        return self._results


class LiquipediaPage:
    PARTICIPANTS_SECTION = 3
    RESULTS_SECTION = 4

    def __init__(self, region: RegionEnum, edition: int, dry_run: bool,
                 page_template: str):
        self.site = mwclient.Site('liquipedia.net/starcraft2', path='/')
        self._authenticate()
        self.ept_cup = EPTCup(region, edition)
        page_link = Template(page_template).substitute(region=region.value,
                                                       edition=edition)
        self.page = self.site.pages[page_link]
        self.dry_run = dry_run
        self.known_players = self._fetch_known_players()

    @staticmethod
    def _get_known_players_file():
        # NOTE: If we face packaging issues on Windows and are unable to import
        # this file, we could try to fetch it from other locations, such as the
        # current directory.
        pkg = importlib_resources.files("liquipedia_scripts")
        return pkg / 'data/ept-cups-known-players.csv'

    def _fetch_known_players(self):
        players = {}
        with open(self._get_known_players_file()) as f:
            reader = csv.DictReader(f)
            for row in reader:
                esl_id = int(row.pop('ESL id'))
                players[esl_id] = row
        return players

    def _authenticate(self):
        # NOTE: We should probably use token authentication here.
        # NOTE: The credentials should be in
        # $XDG_CONFIG_HOME/liquipedia_scripts/lp.config but it's hard to know
        # how that would work on Windows, and whether users are used to writing
        # config files.
        try:
            username = os.environ['LIQUIPEDIA_USERNAME']
            password = os.environ['LIQUIPEDIA_PASSWORD']
        except KeyError:
            sys.exit('Please set the following environment variables:\n'
                     '    LIQUIPEDIA_USERNAME\n'
                     '    LIQUIPEDIA_PASSWORD')
        self.site.login(username, password)

    def update_notable_participants(self):
        current_text = self.page.text(section=self.PARTICIPANTS_SECTION)
        notable_players = []
        i = 1
        for esl_player in self.ept_cup.participants:
            try:
                player = self.known_players[esl_player.esl_id]
                if int(player['notable']):
                    lpname = player['LP name']
                    link = player['LP link']
                    if link:
                        entry = f'|p{i}={lpname}|p{i}link={link}'
                    else:
                        entry = f'|p{i}={lpname}'
                    notable_players.append(entry)
                    i += 1
            except KeyError:
                # We do not know this player, so we just assume that they are
                # not a notable one.
                continue
        notable_players = '\n'.join(notable_players)
        new_text = re.sub(r'{{ParticipantTable.*}}',
                          f'{{{{ParticipantTable\n{notable_players}\n}}}}',
                          current_text, flags=re.DOTALL)
        if current_text != new_text:
            if self.dry_run:
                print('New participants section:')
                print(new_text)
            else:
                self.page.edit(new_text,
                               summary="Updating participant list",
                               section=self.PARTICIPANTS_SECTION)

    @staticmethod
    def _lp_round_to_esl_round(lp_round_no: int,
                               n_esl_rounds: int,
                               n_lp_rounds: int) -> int:
        # ESL rounds start at 0.
        # LP rounds start at 1, and not all rounds are shown on LP.
        # Here is an example with 128 players in a tournament, with Liquipedia
        # only logging matches starting from the Ro32:
        #
        # RoX              | 128 | 64 | 32 | 16 | 8 | 4 | 2
        # ESL round number |  0  |  1 |  2 |  3 | 4 | 5 | 6
        # LP  round number | N/A | N/A|  1 |  2 | 3 | 4 | 5
        #
        # The ESL knows about 7 rounds, and LP about 5 rounds. So, round 3 for
        # ESL is round (3 - (7 - 5 - 1)) = 2 for LP.
        if lp_round_no <= 0:
            raise ValueError('The Liquipedia round number must be at least 1')
        return lp_round_no + (n_esl_rounds - n_lp_rounds - 1)

    def _format_match_result(self, match_: Match, current_info: dict) -> str:
        '''Format a match result for Liquipedia.

        The player names, races, country flags and scores already displayed on
        Liquipedia for this match are held in current_info (keys: p1, p2, r1,
        r2, f1, f2, s1, s2).

        The values already available on Liquipedia are not overwritten.
        '''
        def _format_player_score(match_: Match, current_info: dict,
                                 player_index: int) -> str:
            score = current_info['s%d' % player_index]
            if not score:
                if match_.is_forfeit():
                    score = 'W' if match_.winner == player_index else 'FF'
                elif match_.winner:
                    score = str(getattr(match_, 's%d' % player_index))
                else:
                    score = ''
            return score

        def _format_player_name(match_: Match, current_info: dict,
                                player_index: int) -> str:
            player_name = current_info['p%d' % player_index]
            if not player_name:
                try:
                    esl_player = getattr(match_, 'p%d' % player_index)
                    if esl_player is None:
                        player_name = ''
                    else:
                        player = self.known_players[esl_player.esl_id]
                        player_name = player['LP name']
                except KeyError:
                    player_name = esl_player.esl_name
            return player_name

        def _format_player_race(match_: Match, current_info: dict,
                                player_index: int) -> str:
            race = current_info['r%d' % player_index]
            if not race:
                try:
                    esl_player = getattr(match_, 'p%d' % player_index)
                    if esl_player is None:
                        race = ''
                    else:
                        r = self.known_players[esl_player.esl_id]['race']
                        race = f'|race={r}' if r else ''
                except KeyError:
                    race = ''
            return race

        def _format_player_flag(match_: Match, current_info: dict,
                                player_index: int) -> str:
            flag = current_info['f%d' % player_index]
            if not flag:
                try:
                    esl_player = getattr(match_, 'p%d' % player_index)
                    if esl_player is None:
                        flag = ''
                    else:
                        f = self.known_players[esl_player.esl_id]['flag']
                        flag = f'|flag={f}' if f else ''
                except KeyError:
                    flag = ''
            return flag

        values = {
            'roundno': current_info['roundno'],
            'matchno': current_info['matchno'],
            'bestof': current_info['bestof'],
            'name1': _format_player_name(match_, current_info, 1),
            'name2': _format_player_name(match_, current_info, 2),
            'race1': _format_player_race(match_, current_info, 1),
            'race2': _format_player_race(match_, current_info, 2),
            'flag1': _format_player_flag(match_, current_info, 1),
            'flag2': _format_player_flag(match_, current_info, 2),
            'score1': _format_player_score(match_, current_info, 1),
            'score2': _format_player_score(match_, current_info, 2),
        }
        return '''|R%(roundno)sM%(matchno)s=%(bestof)s
    |opponent1={{1v1Opponent|1=%(name1)s%(flag1)s%(race1)s|score=%(score1)s}}
    |opponent2={{1v1Opponent|1=%(name2)s%(flag2)s%(race2)s|score=%(score2)s}}
}}''' % values

    def update_results(self):
        current_text = self.page.text(section=self.RESULTS_SECTION)
        m = re.search(r'\|Bracket/(\d+)\|', current_text)
        if m is None:
            raise ValueError('Cannot figure out what kind of bracket this is')
        n_lp_rounds = int(math.ceil(math.log(int(m.groups()[0]), 2)))

        pattern = r'''\|R(?P<roundno>[1-%d])M(?P<matchno>\d+)=(?P<bestof>{{Match(\|bestof=\d)?)
    \|opponent1={{1v1Opponent\|1=(?P<p1>[a-zA-Z0-9_]*)(?P<f1>(\|flag=[a-z]+)?)(?P<r1>(\|race=[tzp])?)\|score=(?P<s1>[0-2]*)}}
    \|opponent2={{1v1Opponent\|1=(?P<p2>[a-zA-Z0-9_]*)(?P<f2>(\|flag=[a-z]+)?)(?P<r2>(\|race=[tzp])?)\|score=(?P<s2>[0-2]*)}}
}}''' % (n_lp_rounds - 2)

        new_text = current_text
        for match_ in re.finditer(pattern, current_text, re.DOTALL):
            d = match_.groupdict()
            esl_roundno = self._lp_round_to_esl_round(int(d['roundno']),
                                                      self.ept_cup.n_rounds,
                                                      n_lp_rounds)
            match_result = self.ept_cup.results[esl_roundno][int(d['matchno'])]
            formatted_result = self._format_match_result(match_result, d)
            new_text = new_text.replace(match_.group(0), formatted_result)

        if current_text != new_text:
            if self.dry_run:
                print('New results section:')
                print(new_text)
            else:
                self.page.edit(new_text,
                               summary="Updating results",
                               section=self.RESULTS_SECTION)


def create_parser():
    parser = argparse.ArgumentParser(prog='lp-ept-cups')
    subparsers = parser.add_subparsers(title='Commands', dest='cmd',
                                       required=True)
    participants_parser = subparsers.add_parser('participants')
    results_parser = subparsers.add_parser('results')

    parser.add_argument('-n', '--dry-run',
                        action='store_true',
                        help='Do not write anything; print on stdout instead')
    default_page = 'ESL_Open_Cup_${region}/${edition}'
    parser.add_argument('-p', '--page-template',
                        default=default_page,
                        help='Liquipedia page to edit. '
                             f'Defaults to "{default_page}"')
    for subparser in (participants_parser, results_parser):
        subparser.add_argument('region',
                               choices=[region.value for region in RegionEnum],
                               help='Region we are interested in')
        subparser.add_argument('edition',
                               type=int,
                               help='Edition we are interested in')

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    lp = LiquipediaPage(RegionEnum(args.region),
                        args.edition,
                        dry_run=args.dry_run,
                        page_template=args.page_template)
    if args.cmd == 'participants':
        lp.update_notable_participants()
    elif args.cmd == 'results':
        lp.update_results()
    else:
        raise ValueError(args.cmd)


if __name__ == '__main__':
    main()
