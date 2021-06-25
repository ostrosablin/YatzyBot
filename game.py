#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# YatzyBot - A Telegram bot for playing Yatzy/Yahtzee
# Copyright (C) 2019  Vitaly Ostrosablin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import UserString, defaultdict
from time import time
from random import shuffle
from functools import wraps

from const import START, ERROR, STOP, ROLL
from dice import Dice
from error import PlayerError
from scoreboard import Scoreboard


def is_usable(func):
    """Decorator to check command for basic validity"""
    @wraps(func)
    def wrapper(self, player, *args, **kwargs):
        self.chk_command_usable(player)
        return func(self, player, *args, **kwargs)
    return wrapper


def is_usable_any_turn(func):
    """Decorator to check command for basic validity"""
    @wraps(func)
    def wrapper(self, player, *args, **kwargs):
        self.chk_command_usable_any_turn(player)
        return func(self, player, *args, **kwargs)
    return wrapper


def is_reroll_sane(func):
    """Decorator to check reroll correctness"""
    @wraps(func)
    def wrapper(self, player, dice):
        self.reroll_precheck(player, dice)
        return func(self, player, dice)
    return wrapper


class Game(object):
    """This class represents a Yatzy/Yahtzee game"""

    def __init__(self, chat, owner, yahtzee=False, forced=False, maxi=False):
        if (maxi or forced) and yahtzee:
            raise ValueError(
                "Error, Maxi and Forced mode is valid only for Yatzy game!"
            )
        self.chat = chat
        self.owner = owner
        self.players = [owner]
        self.current = 0
        self.scoreboard = None
        self.started = False
        self.finished = False
        self.yahtzee = yahtzee
        self.forced = forced
        self.maxi = maxi
        self.hand = None
        self.saved_rerolls = defaultdict(int)
        self.reroll = 0
        self.reroll_pool = []
        self.last_op = time()

    def add_player(self, player):
        """Add a new player"""
        if self.started:
            raise PlayerError(
                f"{ERROR} Cannot add a player into started game."
            )
        if player in self.players:
            raise PlayerError(f"{ERROR} You've already joined.")
        player.activate(self)
        self.players.append(player)

    def del_player(self, player):
        """Remove a player"""
        if self.started:
            self.leave_started(player)
            return
        if player not in self.players:
            raise PlayerError(f"{ERROR} You're not in game.")
        if player == self.owner:
            self.stop_game(player)
            raise PlayerError(
                f"{STOP} Owner has left the game, game is aborted."
            )
        self.players.remove(player)

    def leave_started(self, player):
        """Leave a started game"""
        if self.started:
            if player.is_active(self):
                self.scoreboard.zero_scoreboard(player)
                player.deactivate(self)
                if not self.has_active_players():
                    self.stop_game(player, True)
                    return
                if player == self.get_current_player():
                    self.rotate_turn()
                return
            else:
                raise PlayerError(f"{ERROR} You have already left the game.")
        else:
            raise PlayerError(f"{ERROR} Cannot leave: no game in progress.")

    def has_active_players(self):
        """Check if active players remain in the game"""
        for player in self.players:
            if player.is_active(self):
                return True
        return False

    def is_current_turn(self, player):
        """Check, whether it's a turn of this player"""
        if self.players[self.current] == player:
            return True
        return False

    def get_current_player(self):
        """Get a player, whose turn it's now"""
        if not self.started:
            return None
        return self.players[self.current]

    def rotate_turn(self):
        """Switch to next player"""
        self.last_op = time()
        self.current += 1
        if self.current == len(self.players):
            self.current = 0
        self.hand = None
        self.reroll_pool = []
        self.reroll = 0
        if not self.get_current_player().is_active(self):
            self.rotate_turn()

    def chk_command_usable_any_turn(self, player):
        """Check if command can be used on any turn"""
        if not self.started:
            raise PlayerError(
                f"{ERROR} This game is not started (try {START} /start)."
            )
        if self.finished:
            raise PlayerError(
                f"{ERROR} This game is already finished, create a new game "
                f"(try {START} /start)."
            )
        if player not in self.players:
            raise PlayerError(f"{ERROR} You're not in game.")

    def chk_command_usable(self, player):
        """Check command can be used on player's turn"""
        self.chk_command_usable_any_turn(player)
        if not self.is_current_turn(player):
            raise PlayerError(f"{ERROR} It's not your turn.")

    @is_usable
    def roll(self, _):
        """Roll a dice (initial)"""
        if self.hand:
            raise PlayerError(f"{ERROR} You've already rolled a hand.")
        self.hand = sorted(Dice.roll(5 if not self.maxi else 6))
        self.last_op = time()
        return self.hand

    @is_usable
    def get_hand_score_options(self, player):
        """
        Get a list of possible ways to score your hand
        (in descending score order)
        """
        if not self.hand:
            raise PlayerError(
                f"{ERROR} Cannot get move list - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
        return self.scoreboard.get_score_options(player, self.hand)

    @is_usable
    def commit_turn(self, player, move):
        """Commit a move and record it in scoreboard"""
        if not self.hand:
            raise PlayerError(
                f"{ERROR} Cannot move - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
        score = self.scoreboard.commit_dice_combination(
            player, self.hand, move)
        # In Maxi Yatzy - we keep saved rerolls
        if self.maxi:
            self.saved_rerolls[player] += (2 - self.reroll)
        self.rotate_turn()
        if self.scoreboard.is_finished():
            self.stop_game(player, True)
        return score

    def is_completed(self):
        """Check if game is completed gracefully"""
        if self.finished and self.scoreboard.is_finished():
            return True
        return False

    def is_game_not_started(self):
        """Check if game is to be started"""
        if not self.started and not self.finished:
            return True
        return False

    def is_game_in_progress(self):
        """Check if game is running"""
        if self.started and not self.finished:
            return True
        return False

    def scores_player(self, player):
        """Get player scores"""
        return self.scoreboard.print_player_scores(player)

    def scores_all(self, _):
        """Get full scoreboard - unused due to formatting issues"""
        return self.scoreboard.print_scores()

    def scores_final(self, _):
        """Get final scores"""
        return self.scoreboard.print_final_scores()

    @is_usable
    def reroll_precheck(self, _, query):
        """Reroll pre-checks"""
        dice_count = 5 if not self.maxi else 6
        if not self.hand:
            raise PlayerError(
                f"{ERROR} Cannot reroll - you didn't roll a hand yet "
                f"(try {ROLL} /roll).")
        if len(query) > dice_count or len(query) < 1:
            raise PlayerError(
                f"{ERROR} You should select from 1 to "
                f"{dice_count} dice to reroll.")

    def dice_validate(self, dice):
        """Check dice for validity"""
        for die in dice:
            if die not in f'12345{"6" if self.maxi else ""}':
                dicecount = 5 if not self.maxi else 6
                raise PlayerError(
                    f"{ERROR} You should specify numbers in "
                    f"range 1-{dicecount} to reroll."
                )

    def reroll_increment(self, player):
        """Increase number of rerolls (and check if we can reroll)"""
        if self.reroll >= 2:
            if self.maxi:
                if self.saved_rerolls[player]:
                    self.saved_rerolls[player] -= 1
                else:
                    raise PlayerError(
                        f"{ERROR} You cannot reroll more than twice "
                        f"(no saved rerolls)!"
                    )
            else:
                raise PlayerError(
                    f"{ERROR} You cannot reroll more than twice!"
                )
        else:
            self.reroll += 1

    @is_reroll_sane
    def reroll_dice(self, player, dice):
        """Reroll dice by positions"""
        self.dice_validate(dice)
        dicemap = map(int, dice)
        self.reroll_increment(player)
        for d in dicemap:
            self.hand[d - 1] = Dice.roll_single()
        self.hand = sorted(self.hand)
        self.last_op = time()
        return self.hand

    def reroll_pooled(self, player):
        """Reroll pooled dice"""
        self.reroll_dice(player, "".join(self.reroll_pool))
        self.reroll_pool = []
        return self.hand

    @is_usable
    def reroll_pool_clear(self, _):
        """Clear pooled dice"""
        self.reroll_pool = []

    @is_usable
    def reroll_pool_select_all(self, _):
        """Clear pooled dice"""
        self.reroll_pool = ['1', '2', '3', '4', '5']
        if self.maxi:
            self.reroll_pool.append('6')

    @is_reroll_sane
    def reroll_pool_toggle(self, _, dice):
        """Toggle dice in reroll pool"""
        if len(dice) != 1:
            raise PlayerError(
                f"{ERROR} You should specify a single dice to reroll."
            )
        if dice in self.reroll_pool:
            self.reroll_pool.remove(dice)
        else:
            self.reroll_pool.append(dice)

    @is_reroll_sane
    def reroll_pool_add(self, _, dice):
        """Add dice to reroll pool"""
        if len(dice) != 1:
            raise PlayerError(
                f"{ERROR} You should specify a single dice to reroll."
            )
        if dice in self.reroll_pool:
            raise PlayerError(
                f"{ERROR} This dice is already queued for reroll."
            )
        self.reroll_pool.append(dice)

    @is_reroll_sane
    def reroll_pool_del(self, _, dice):
        """Remove dice from reroll pool"""
        if len(dice) != 1:
            raise PlayerError(
                f"{ERROR} You should specify a single dice to reroll."
            )
        if dice not in self.reroll_pool:
            raise PlayerError(f"{ERROR} This dice is not queued for reroll.")
        self.reroll_pool.remove(dice)

    def start_game(self, player):
        """Begin game"""
        if self.finished:
            raise PlayerError(
                f"{ERROR} This game is already finished (try {START} /start)."
            )
        if len(self.players) < 1:
            raise PlayerError(
                f"{ERROR} At least one person should join a game to start."
            )
        if player != self.owner:
            raise PlayerError(f"{ERROR} Only owner can do this!")
        shuffle(self.players)
        self.scoreboard = Scoreboard(
            self.players, self.yahtzee, self.forced, self.maxi)
        self.started = True
        self.last_op = time()

    @is_usable_any_turn
    def stop_game(self, player, completed=False):
        """Stop game"""
        if not completed and player != self.owner:
            raise PlayerError(f"{ERROR} Only owner can do this!")
        self.started = False
        self.finished = True
        self.last_op = 0
        self.players = []


class Player(UserString):
    """Class for representing a player"""

    def __init__(self, user):
        self.user = user
        name = [user.first_name]
        if user.last_name:
            name.append(user.last_name)
        if user.username:
            name.append(f"({user.username})")
        self.active = {}
        UserString.__init__(self, " ".join(name))

    def deactivate(self, game):
        self.active[game] = False

    def activate(self, game):
        self.active[game] = True

    def is_active(self, game):
        return self.active.get(game, True)
