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

from const import VALUES, EMOJIS
from error import InvalidDiceError


class Dice(object):
    """This class represents a dice"""

    def __init__(self, value=None):
        if value is None:
            self.value = str(randint(1, 6))
        elif isinstance(value, int):
            self.value = str(value)
        else:
            self.value = value
        if self.value not in VALUES:
            raise InvalidDiceError(f"Неверное значение кубика: {self.value}")

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
        for char in string:
            dice.append(Dice(char))
        return dice

    @classmethod
    def roll(cls, n=5):
        dice = []
        for _ in range(n):
            dice.append(Dice())
        return dice

    @classmethod
    def roll_single(cls):
        return Dice()
