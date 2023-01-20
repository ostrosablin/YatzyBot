#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
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

from time import time

from const import ERROR, STOP, INACTIVITY_TIMEOUT
from error import PlayerError
from game import Game, Player


class GameManager(object):
    """Class for managing games"""

    def __init__(self):
        self.chats = {}
        self.players = {}

    def new_game(self, chat, owner, yahtzee, forced=False, maxi=False):
        if self.is_game_running(chat) or self.is_game_not_started(chat):
            if self.chats[chat.id].owner != self.player(owner):
                if (time() - INACTIVITY_TIMEOUT) < self.chats[chat.id].last_op:
                    raise PlayerError(
                        f"{ERROR} Только владелец может делать это!"
                    )
        if self.is_game_running(chat):
            raise PlayerError(
                f"{ERROR} Нельзя создать новую игру, пока активна предыдущая "
                f"(попробуйте {STOP} /stop)."
            )
        self.chats[chat.id] = Game(
            chat.id, self.player(owner), yahtzee, forced, maxi)

    def is_game_not_started(self, chat):
        if chat.id in self.chats and self.chats[chat.id].is_game_not_started():
            return True
        return False

    def is_game_created(self, chat):
        if chat.id in self.chats:
            return True
        return False

    def is_game_running(self, chat):
        if chat.id in self.chats and self.chats[chat.id].is_game_in_progress():
            return True
        return False

    def game(self, chat):
        return self.chats.get(chat.id, None)

    def player(self, user):
        if user.id not in self.players:
            self.players[user.id] = Player(user)
        return self.players[user.id]

    def current_turn(self, chat):
        return self.chats[chat.id].get_current_player()
