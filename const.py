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

# Timing constants
INACTIVITY_TIMEOUT = 900

# General emojis
WILDCARD_DICE = "*️⃣"
ROLL = "🎲"
MOVE = "🎰"
SCORE = "📝"
SCORE_ALL = "🏆"
RESET_REROLL = "❌"
SELECT_ALL = WILDCARD_DICE
DO_REROLL = "✅"
HELP = "❓"
START = "🚀"
STOP = "⛔️"
JOIN = "🎮"
LEAVE = "🚪"
ERROR = "⚠️"
INFO = "💡"
HELLO = "✋"
CONGRATS = "🎉"
OWNER = "👮‍♂️"
KICK = "🥾"
SCORED = "💰"
TIE = "⚖️"
ORDER = "🔮"
FIRST = "🟢"
MIDDLE = "🟡"
LAST = "🔴"
UPPER = "🔼"
LOWER = "🔽"
JOKER = "🃏"
BEST = "📈"
RULES = "📖"

# Move icons
MOVE_ICONS = {
    'on': "1️⃣ ",
    'ac': "1️⃣ ",
    'tw': "2️⃣ ",
    'th': "3️⃣ ",
    'fo': "4️⃣ ",
    'fi': "5️⃣ ",
    'si': "6️⃣ ",
    'op': "👨‍👦",
    'tp': "👨‍👨‍👦‍👦",
    '3p': "👨‍👦‍👦",
    'tk': "🇨🇦",
    'fk': "🇬🇪",
    '5k': "🇰🇷",
    'fh': "🏠",
    'ca': "🏰",
    'to': "🗼",
    'ss': "▶️",
    'ls': "⏩",
    'fs': "⏭",
    'ch': "❓",
    'ya': "💎",
    'yh': "💎",
    'my': "💎"
}

# Dice faces (string-to-emoji mapping)
EMOJIS = {
    '1': '1️⃣',
    '2': '2️⃣',
    '3': '3️⃣',
    '4': '4️⃣',
    '5': '5️⃣',
    '6': '6️⃣'
}

# Dice faces (strings)
ONE = '1'
TWO = '2'
THREE = '3'
FOUR = '4'
FIVE = '5'
SIX = '6'

# Position emojis
LOLLIPOP = '🍭'
POSITIONS = {1: '🥇', 2: '🥈', 3: '🥉'}
SUFFIX = {1: 'ое', 2: 'ое', 3: 'ье'}

# Valid dice values
VALUES = (ONE, TWO, THREE, FOUR, FIVE, SIX)

# Mappings of commands to scoreboard boxes and vice versa
MAP_TURNS = {
    'on': "Единицы",
    'ac': "Тузы",
    'tw': "Двойки",
    'th': "Тройки",
    'fo': "Четвёрки",
    'fi': "Пятёрки",
    'si': "Шестёрки",
    'op': "Одна Пара",
    'tp': "Две Пары",
    '3p': "Три Пары",
    'tk': "3 Одинаковых",
    'fk': "4 Одинаковых",
    '5k': "5 Одинаковых",
    'fh': "Фулл Хаус",
    'ca': "Замок",
    'to': "Башня",
    'ss': "Малый Стрит",
    'ls': "Большой Стрит",
    'fs': "Полный Стрит",
    'ch': "Шанс",
    'ya': "Йетзи",
    'yh': "Яхтзи",
    'my': "Макси Йетзи"
}

# Generated mappings
MAP_COMMANDS = {v: k for k, v in MAP_TURNS.items()}
MOVE_BOX_ICONS = {MAP_TURNS[k]: v for k, v in MOVE_ICONS.items()}
