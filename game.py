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

from collections import UserString
from time import time

from dice import Dice
from error import PlayerError
from scoreboard import Scoreboard


class Game(object):
    """This class represents a Yatzy/Yahtzee game"""

    def __init__(self, chat, owner, yahtzee=False):
        self.chat = chat
        self.owner = owner
        self.players = [owner]
        self.current = 0
        self.scoreboard = None
        self.started = False
        self.finished = False
        self.yahtzee = yahtzee
        self.hand = None
        self.reroll = 0
        self.reroll_pool = []
        self.last_op = time()

    def add_player(self, player):
        """Add a new player"""
        if self.started:
            raise PlayerError("Cannot add a player into started game")
        if player in self.players:
            raise PlayerError("You've already joined")
        self.players.append(player)

    def del_player(self, player):
        """Remove a player"""
        if self.started:
            raise PlayerError("Cannot remove a player from started game")
        if player not in self.players:
            raise PlayerError("You're not in game")
        if player == self.owner:
            self.stop_game(player)
            raise PlayerError("Owner has left the game, game is aborted")
        self.players.remove(player)

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

    def chk_command_usable(self, player):
        """Check if command can be used"""
        if not self.started:
            raise PlayerError("This game is not started")
        if self.finished:
            raise PlayerError("This game is already finished, create a new game")
        if not self.is_current_turn(player):
            raise PlayerError("It's not your turn")

    def roll(self, player):
        """Roll a dice (initial)"""
        self.chk_command_usable(player)
        if self.hand:
            raise PlayerError("You've already rolled a hand")
        self.hand = sorted(Dice.roll())
        self.last_op = time()
        return self.hand

    def get_hand_score_options(self, player):
        """Get a list of possible ways to score your hand (in descending score order)"""
        self.chk_command_usable(player)
        if not self.hand:
            raise PlayerError("Cannot get move list - you didn't roll a hand yet")
        return self.scoreboard.get_score_options(player, self.hand)

    def commit_turn(self, player, move):
        """Commit a move and record it in scoreboard"""
        self.chk_command_usable(player)
        if not self.hand:
            raise PlayerError("Cannot move - you didn't roll a hand yet")
        score = self.scoreboard.commit_dice_combination(player, self.hand, move)
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

    def scores_all(self):
        """Get full scoreboard"""
        return self.scoreboard.print_scores()

    def scores_final(self):
        """Get final scores"""
        return self.scoreboard.print_final_scores()

    def reroll_check(self, player, query):
        """Reroll pre-checks"""
        self.chk_command_usable(player)
        if not self.hand:
            raise PlayerError("Cannot reroll - you didn't roll a hand yet")
        if len(query) > 5 or len(query) < 1:
            raise PlayerError("You should select from 1 to 5 dice to reroll")

    def reroll_dice(self, player, dice):
        """Reroll dice by positions"""
        self.reroll_check(player, dice)
        for i in dice:
            if i not in '12345':
                raise PlayerError("You should specify numbers in range 1-5 to reroll")
        dice = ''.join(list(set(dice)))
        if self.reroll >= 2:
            raise PlayerError("You cannot reroll more than twice!")
        self.reroll += 1
        for d in dice:
            self.hand[int(d) - 1] = Dice.roll_single()
        self.hand = sorted(self.hand)
        self.last_op = time()
        return self.hand

    def reroll_numbers(self, player, numbers):
        """Reroll dice by value"""
        self.reroll_check(player, numbers)
        for i in numbers:
            if i not in '123456':
                raise PlayerError("You should specify numbers in range 1-6 to reroll")
        to_reroll = [int(d) for d in numbers]
        positions = []
        for i in range(len(self.hand)):
            if int(self.hand[i]) in to_reroll:
                to_reroll.remove(int(self.hand[i]))
                positions.append(i + 1)
        if to_reroll or len(positions) < len(numbers):
            raise PlayerError("Cannot reroll all requested numbers")
        self.reroll_dice(player, ''.join([str(i) for i in positions]))
        return self.hand

    def reroll_pooled(self, player):
        """Reroll pooled dice"""
        self.reroll_dice(player, "".join(self.reroll_pool))
        self.reroll_pool = []
        return self.hand

    def reroll_pool_clear(self):
        """Clear pooled dice"""
        self.reroll_pool = []

    def reroll_pool_toggle(self, player, dice):
        """Toggle dice in reroll pool"""
        if len(dice) != 1:
            raise PlayerError("You should specify a single dice to reroll")
        self.reroll_check(player, dice)
        if dice in self.reroll_pool:
            self.reroll_pool.remove(dice)
        else:
            self.reroll_pool.append(dice)

    def reroll_pool_add(self, player, dice):
        """Add dice to reroll pool"""
        if len(dice) != 1:
            raise PlayerError("You should specify a single dice to reroll")
        self.reroll_check(player, dice)
        if dice in self.reroll_pool:
            raise PlayerError("This dice is already queued for reroll")
        self.reroll_pool.append(dice)

    def reroll_pool_del(self, player, dice):
        """Remove dice from reroll pool"""
        if len(dice) != 1:
            raise PlayerError("You should specify a single dice to reroll")
        self.reroll_check(player, dice)
        if dice not in self.reroll_pool:
            raise PlayerError("This dice is not queued for reroll")
        self.reroll_pool.remove(dice)

    def hand_to_str(self, player):
        """Hand to string representation"""
        self.chk_command_usable(player)
        if not self.hand:
            return None
        return ''.join([str(d) for d in self.hand])

    def get_hand(self, player):
        """Raw hand"""
        self.chk_command_usable(player)
        return self.hand

    def start_game(self, player):
        """Begin game"""
        if self.finished:
            raise PlayerError("This game is already finished")
        if len(self.players) < 1:
            raise PlayerError("At least one person should join a game to start")
        if player != self.owner:
            raise PlayerError("Only owner can do this!")
        self.scoreboard = Scoreboard(self.players, self.yahtzee)
        self.started = True
        self.last_op = time()

    def stop_game(self, player, completed=False):
        """Stop game"""
        if not completed and player != self.owner:
            raise PlayerError("Only owner can do this!")
        self.started = False
        self.finished = True
        self.last_op = 0


class Player(UserString):
    """Class for representing a player"""

    def __init__(self, user):
        self.user = user
        name = [user.first_name]
        if user.last_name:
            name.append(user.last_name)
        if user.username:
            name.append("({0})".format(user.username))
        UserString.__init__(self, " ".join(name))
