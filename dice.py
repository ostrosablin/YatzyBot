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

from random import randint

from error import InvalidDiceError

# Values
ONE = '1'
TWO = '2'
THREE = '3'
FOUR = '4'
FIVE = '5'
SIX = '6'

VALUES = (ONE, TWO, THREE, FOUR, FIVE, SIX)
EMOJIS = {'1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣', '6': '6️⃣'}


class Dice(object):
    """This class represents a dice"""

    def __init__(self, value):
        if type(value) == int:
            self.value = str(value)
        else:
            self.value = value
        if str(value) not in VALUES:
            raise InvalidDiceError("Invalid dice value: %s" % self.value)

    def __str__(self):
        return self.value

    def __int__(self):
        return int(self.value)

    def __eq__(self, other):
        """Needed for sorting the dice"""
        return int(self.value) == int(other.value)

    def __lt__(self, other):
        """Needed for sorting the dice"""
        return int(self.value) < int(other.value)

    def __gt__(self, other):
        """Needed for sorting the dice"""
        return int(self.value) > int(other.value)

    def to_emoji(self):
        """Convert dice to emoji"""
        return EMOJIS[self.value]

    @classmethod
    def from_str(cls, string):
        """Decodes a Dice object(s) from a string"""
        dice = []
        for i in string:
            dice.append(Dice(i))
        return dice

    @classmethod
    def roll(cls, n=5):
        dice = []
        for i in range(n):
            dice.append(Dice(randint(1, 6)))
        return dice

    @classmethod
    def roll_single(cls):
        return Dice(randint(1, 6))
