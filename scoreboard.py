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

from collections import Counter, OrderedDict

from tabulate import tabulate

from const import POSITIONS, LOLLIPOP, ERROR, SUFFIX
from error import IllegalMoveError


def count_dice(dice):
    ctr = Counter()
    for d in dice:
        ctr[str(d)] += 1
    return ctr


def sort_and_dedupe(dice):
    return list(OrderedDict.fromkeys([int(d) for d in sorted(dice)]))


class Scoreboard(object):
    """This class represents a Yatzy/Yahtzee scoreboard"""

    def __init__(self, players, yahtzee=False, forced=False, maxi=False):
        if (maxi or forced) and yahtzee:
            raise ValueError(
                "Ошибка, Макси и Последовательный режимы допустимы только для "
                "игры Йетзи!"
            )
        self.players = players  # List of players
        # If True - we play Yahtzee (strict commercial rules)
        self.yahtzee = yahtzee
        self.forced = forced  # If True - play Forced Yahtzee variant
        self.maxi = maxi  # If True - play Maxi Yahtzee variant
        self.scores = {}
        for player in self.players:
            boxes = [
                Box(
                    "Тузы" if yahtzee else "Единицы",
                    lambda dice: Box.sum_particular_digits(dice, 1),
                    lambda dice: 0
                ),
                Box(
                    "Двойки", lambda dice: Box.sum_particular_digits(dice, 2),
                    lambda dice: 0
                ),
                Box(
                    "Тройки", lambda dice: Box.sum_particular_digits(dice, 3),
                    lambda dice: 0
                ),
                Box(
                    "Четвёрки", lambda dice: Box.sum_particular_digits(dice, 4),
                    lambda dice: 0
                ),
                Box(
                    "Пятёрки", lambda dice: Box.sum_particular_digits(dice, 5),
                    lambda dice: 0
                ),
                Box(
                    "Шестёрки", lambda dice: Box.sum_particular_digits(dice, 6),
                    lambda dice: 0
                ),
                Box("Сумма Вер. Секц.", None, None, 0),
                Box("Бонус Вер. Секц.", None, None, 0)]
            if not yahtzee:
                boxes.append(
                    Box("Одна Пара", lambda dice: Box.groups(dice, [2])))
                boxes.append(
                    Box("Две Пары", lambda dice: Box.groups(dice, [2, 2])))
                if self.maxi:
                    boxes.append(
                        Box(
                            "Три Пары",
                            lambda dice: Box.groups(dice, [2, 2, 2])
                        )
                    )
            boxes.append(
                Box(
                    "3 Одинаковых",
                    lambda dice: Box.sum_n_of_a_kind(dice, 3, yahtzee),
                    Box.chance)
            )
            boxes.append(
                Box(
                    "4 Одинаковых",
                    lambda dice: Box.sum_n_of_a_kind(dice, 4, yahtzee),
                    Box.chance
                )
            )
            if self.maxi:
                boxes.append(
                    Box(
                        "5 Одинаковых",
                        lambda dice: Box.sum_n_of_a_kind(dice, 5, yahtzee)
                    )
                )
            boxes.append(Box("Фулл Хаус", lambda dice: Box.full_house(
                dice, yahtzee), lambda dice: 25))
            if self.maxi:
                boxes.append(
                    Box("Замок", lambda dice: Box.groups(dice, [3, 3])))
                boxes.append(
                    Box("Башня", lambda dice: Box.groups(dice, [2, 4])))
            if yahtzee:
                boxes.append(
                    Box(
                        "Малый Стрит",
                        lambda dice: Box.straight_yahtzee(dice, 4),
                        lambda dice: 30
                    )
                )
                boxes.append(
                    Box(
                        "Большой Стрит",
                        lambda dice: Box.straight_yahtzee(dice, 5),
                        lambda dice: 40
                    )
                )
            else:
                boxes.append(
                    Box(
                        "Малый Стрит",
                        lambda dice: Box.straight_yatzy(dice, 1, 5)
                    )
                )
                boxes.append(
                    Box(
                        "Большой Стрит",
                        lambda dice: Box.straight_yatzy(dice, 2, 6)
                    )
                )
                if self.maxi:
                    boxes.append(
                        Box(
                            "Полный Стрит",
                            lambda dice: Box.straight_yatzy(dice, 1, 6)
                        )
                    )
            boxes.append(Box("Шанс", Box.chance))
            if self.yahtzee:
                boxes.append(Box("Яхтзи", Box.yatzy))
            else:
                boxes.append(Box("Макси Йетзи" if self.maxi else "Йетзи",
                                 lambda dice: Box.yatzy(dice, self.maxi)))
            if yahtzee:
                boxes.append(Box("Бонус Яхтзи", None, None, 0))
            boxes.append(Box("Сумма Ниж. Секц.", None, None, 0))
            boxes.append(Box("Общая Сумма", None, None, 0))
            self.scores[player] = OrderedDict(
                [(box.name, box) for box in boxes])

    def award_yahtzee_bonus(self, player, dice):
        """Check if Yahtzee Bonus is to be awarded and give it"""
        # Yahtzee Bonus
        if self.yahtzee:
            # If we have already scored a Yahtzee
            if self.scores[player].get("Яхтзи").score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Яхтзи"].preview_dice(dice):
                    # Add 100 extra points to Yahtzee Bonus
                    self.scores[player]["Бонус Яхтзи"].score += 100
                    return 100
        return 0

    def get_upper_section_bonus_score(self):
        """Calculate the score needed to get upper section bonus"""
        # Upper Section Bonus - if we score 63 or more in upper section
        # 84 or more for Maxi Yatzy
        upper_section_bonus = 63 if not self.maxi else 84
        if self.forced:
            # 42 for Forced Yatzy (63 for Forced Maxi Yatzy)
            upper_section_bonus -= 21
        return upper_section_bonus

    def get_upper_section_bonus_value(self):
        return 35 if self.yahtzee else (50 if not self.maxi else 100)

    def award_upper_section_bonus(self, player):
        """Check if Upper Section Bonus is to be awarded and give it"""
        upper_section_bonus = self.get_upper_section_bonus_score()
        if self.scores[player].get(
                "Сумма Вер. Секц.").score >= upper_section_bonus:
            # And if we didn't score the bonus yet
            if not self.scores[player].get("Бонус Вер. Секц.").score:
                # Add 50 extra points to Upper Section Bonus (35 for Yahtzee)
                bonus = self.get_upper_section_bonus_value()
                self.scores[player]["Бонус Вер. Секц."].set_score(bonus)
                return bonus
        return 0

    def check_upper_section_bonus_achievable(self, player):
        dice_count = 6 if self.maxi else 5
        upper_boxes = list(self.scores[player].values())[:6]
        up_sec_target = self.get_upper_section_bonus_score()
        max_achievable = 0
        for i in range(6):
            if upper_boxes[i].score is not None:
                max_achievable += upper_boxes[i].score
            else:
                max_achievable += (i + 1) * dice_count
        unsatisfied_points = max(up_sec_target - max_achievable, 0)
        if unsatisfied_points:
            return False
        return True

    def calculate_expected_delta(self, player):
        upper_boxes = list(self.scores[player].values())[:6]
        avg_dice_for_bonus = self.get_upper_section_bonus_score() // 21
        delta = 0
        for i in range(6):
            if upper_boxes[i].score is not None:
                delta += upper_boxes[i].score - ((i + 1) * avg_dice_for_bonus)
        return delta

    def zero_scoreboard(self, player):
        for box in list(self.scores[player].values()):
            if box.score is None:
                box.set_score(0)
        self.recompute_calculated_fields(player)

    def recompute_calculated_fields(self, player):
        """Compute all calculated boxes"""
        # Recompute Upper Section Totals
        total = 0
        for box in list(self.scores[player].values())[:6]:
            total += box.score if box.score is not None else 0
        self.scores[player]["Сумма Вер. Секц."].set_score(total)
        # Compute and award upper section bonus
        bonus = self.award_upper_section_bonus(player)
        # Keep upper score to compute lower subtotal
        upper = total + self.scores[player].get("Бонус Вер. Секц.").score
        # Proceed to compute totals
        for box in list(self.scores[player].values())[7:-2]:
            total += box.score if box.score is not None else 0
        # Compute lower section subtotal
        self.scores[player]["Сумма Ниж. Секц."].set_score(total - upper)
        self.scores[player]["Общая Сумма"].set_score(total)
        return bonus

    def get_score_options(self, player, dice):
        """Get viable scoring options, sorted in descending order"""
        # Special Yahtzee rules
        if self.yahtzee:
            # If we have already scored a Yahtzee with >0
            if self.scores[player]["Яхтзи"].score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Яхтзи"].preview_dice(dice):
                    # Try to get a corresponding upper section box:
                    box = list(self.scores[player].values())[int(dice[0]) - 1]
                    if box.score is None:
                        return OrderedDict(
                            ((box.name, box.preview_dice(dice)),))
                    # If no free boxes - joker rules allow to use any of lower
                    # boxes
                    res = []
                    for box in list(self.scores[player].values())[8:15]:
                        if box.score is None:
                            res.append(
                                (box.name, box.preview_joker_dice(dice)))
                    if res:
                        return OrderedDict(
                            sorted(
                                res, reverse=True,
                                key=lambda x: x[1]))
                    # Finally, if there's only non-matching upper boxes left,
                    # use them and score 0
                    for box in list(self.scores[player].values())[:6]:
                        if box.score is None:
                            res.append(
                                (box.name, box.preview_joker_dice(dice)))
                    return OrderedDict(res)
        # Regular scoring options
        scores = []
        for box in self.scores[player].values():
            if box.score is None:
                scores.append((box.name, box.preview_dice(dice)))
                if self.forced:
                    break  # In Forced Yatzy, we only give a first unfilled box
        return OrderedDict(sorted(scores, reverse=True, key=lambda x: x[1]))

    def commit_dice_combination(self, player, dice, boxname):
        """Commit dice combination"""
        options = self.get_score_options(player, dice)
        if boxname not in options:
            raise IllegalMoveError(f"{ERROR} Этот ход сейчас недопустим.")
        score = 0
        # Special Yahtzee rules
        if self.yahtzee:
            # If we have already scored a Yahtzee with >0
            if self.scores[player]["Яхтзи"].score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Яхтзи"].preview_dice(dice):
                    # Award a Yahtzee Bonus
                    score += self.award_yahtzee_bonus(player, dice)
                    # Try to get a corresponding upper section box:
                    scoretable = self.scores[player]
                    box = scoretable[boxname]
                    if boxname == list(scoretable.keys())[int(dice[0]) - 1]:
                        score += box.commit_dice(dice)
                    else:
                        score += box.commit_joker_dice(dice)
                    # Update computable fields
                    score += self.recompute_calculated_fields(player)
                    return score
        # Regular scoring rules
        score += self.scores[player][boxname].commit_dice(dice)
        # Update computable fields
        score += self.recompute_calculated_fields(player)
        return score

    def is_filled(self, player):
        """Check, whether all player's scoring boxes are filled"""
        for box in self.scores[player].values():
            if box.score is None:
                return False
        return True

    def is_finished(self):
        """Check, whether scoreboard is completely filled (and so is game)"""
        for player in self.players:
            if not self.is_filled(player):
                return False
        return True

    def print_player_scores(self, player):
        """Print scoreboard for particular player"""
        output = [["", player.user.username or player.user.first_name]]
        up_sec_bonus = self.get_upper_section_bonus_score()
        up_sec_total = self.scores[player].get("Сумма Вер. Секц.").score
        remaining = max(up_sec_bonus - up_sec_total, 0)
        bonus_value = self.get_upper_section_bonus_value()
        lost = not self.check_upper_section_bonus_achievable(player)
        for box in self.scores[player].values():
            if box.name == "Сумма Вер. Секц.":
                delta_msg = ""
                if not lost and remaining:
                    delta = self.calculate_expected_delta(player)
                    if delta:
                        delta_msg = f" ({delta:+})"
                output.append([box.name, f"{box.score}{delta_msg}"])
            else:
                output.append(
                    [box.name, "" if box.score is None else str(box.score)]
                )
            if box.name == "Бонус Вер. Секц.":
                bonus = "Получен"
                if lost:
                    bonus = "Упущен"
                elif remaining:
                    bonus = f"ещё {remaining}"
                output.append(
                    [f"{bonus_value} очк. за ≥ {up_sec_bonus}", bonus]
                )
                output.append(["", ""])
        return tabulate(output, tablefmt="simple")

    def print_scores(self):
        """Print complete scoreboard"""
        output = [[""]]
        output[0].extend(self.players)
        for box in self.scores[self.players[0]]:
            scores = [box]
            for player in self.players:
                scores.append(
                    self.scores[player][box].score
                    if self.scores[player][box].score is not None else "")
            output.append(scores)
        return tabulate(output, tablefmt="simple")

    def final_scores(self):
        """Get final scoring"""
        scores = []
        for player in self.players:
            scores.append((player, self.scores[player]['Общая Сумма'].score))
        return OrderedDict(sorted(scores, reverse=True, key=lambda x: x[1]))

    def print_final_scores(self):
        """Get string representation of final scores"""
        scores = self.final_scores()
        output = []
        place = 1
        last_score = 0
        min_score = min(scores.values())
        max_score = max(scores.values())
        for player in scores:
            if scores[player] == last_score:
                place = max(1, place - 1)
            placeemoji = POSITIONS.get(place, LOLLIPOP)
            if len(scores) > 1 and min_score != max_score:
                if scores[player] == min_score:
                    placeemoji = LOLLIPOP
            output.append(
                f"{placeemoji} {place}-"
                f"{SUFFIX.get(place, 'ое')} место - "
                f"{player} ({scores[player]} очков)"
            )
            place += 1
            last_score = scores[player]
        return '\n'.join(output)


class Box(object):
    """This represents a single scoreboard box"""

    def __init__(self, name, rule, joker_rule=None, score=None):
        self.name = name
        self.score = score
        self.rule = rule
        self.joker_rule = joker_rule

    def set_score(self, score):
        """Assign a score to this box"""
        self.score = score

    def commit_dice(self, dice):
        """Score a dice set into this box"""
        self.score = self.rule(dice)
        return self.score

    def commit_joker_dice(self, dice):
        """Score a joker dice set into this box"""
        if self.joker_rule is not None:
            self.score = self.joker_rule(dice)
        else:
            self.commit_dice(dice)
        return self.score

    def preview_dice(self, dice):
        """Calculate, how much a hand will score in this box"""
        return self.rule(dice)

    def preview_joker_dice(self, dice):
        """Calculate, how much a joker hand will score in this box"""
        if self.joker_rule is not None:
            return self.joker_rule(dice)
        else:
            return self.preview_dice(dice)

    @classmethod
    def sum_particular_digits(cls, dice, digit):
        """Count a sum of particular number dice"""
        ctr = count_dice(dice)
        return ctr[str(digit)] * digit

    @classmethod
    def sum_n_of_a_kind(cls, dice, n, yahtzee):
        """Count a sum for dice in N of a Kind"""
        ctr = count_dice(dice)
        max_suitable = 0
        for die in ctr:
            if ctr[die] >= n:
                if yahtzee:  # In Yahtzee, all hand is counted
                    return sum([int(d) for d in dice])
                else:
                    max_suitable = max(int(die), max_suitable)
        return max_suitable * n

    @classmethod
    def straight_yahtzee(cls, dice, n):
        """Find a run of N consecutive dice"""
        roll = sort_and_dedupe(dice)
        score = {4: 30, 5: 40}
        seq = 0
        for die in range(len(roll) - 1):
            if roll[die] + 1 == roll[die + 1]:
                seq = max(seq + 1, 2)
            else:
                seq = 0
            if seq >= n:
                break
        return score.get(n, 0) if seq >= n else 0

    @classmethod
    def straight_yatzy(cls, dice, start=1, end=5):
        """Find a specific run of consecutive dice"""
        roll = sort_and_dedupe(dice)
        expected = set(range(start, end + 1))
        if bool(expected - set(roll)):
            return 0
        return sum(expected)

    @classmethod
    def groups(cls, dice, groups):
        """Match an abstract dice groups by count"""
        ctr = count_dice(dice)
        expected = sorted(groups)
        totals = 0
        for group in reversed(expected):
            max_suitable = 0
            for j in ctr:
                if ctr[j] >= group:
                    max_suitable = max(int(j), max_suitable)
            if max_suitable:
                totals += (max_suitable * group)
                del ctr[str(max_suitable)]
            else:
                return 0
        return totals

    @classmethod
    def full_house(cls, dice, yahtzee):
        """Find a Full House dice set"""
        totals = cls.groups(dice, [2, 3])
        if totals and yahtzee:
            return 25
        return totals

    @classmethod
    def yatzy(cls, dice, maxi=False):
        """Find a Yatzy/Yahtzee dice set"""
        return 0 if len(count_dice(dice)) != 1 else (50 if not maxi else 100)

    @classmethod
    def chance(cls, dice):
        """Calculate a sum of a hand"""
        return sum([int(d) for d in dice])
