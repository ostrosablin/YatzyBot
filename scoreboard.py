#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# YatzyBot - A Telegram bot for playing Yatzy/Yahtzee
# Copyright (C) 2019-2024  Vitaly Ostrosablin
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
                "Error, Maxi and Forced mode is valid only for Yatzy game!")
        self.players = players  # List of players
        # If True - we play Yahtzee (strict commercial rules)
        self.yahtzee = yahtzee
        self.forced = forced  # If True - play Forced Yahtzee variant
        self.maxi = maxi  # If True - play Maxi Yahtzee variant
        self.scores = {}
        ndice = 6 if self.maxi else 5
        for player in self.players:
            boxes = [
                Box(
                    "Aces" if yahtzee else "Ones", 1 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 1),
                    lambda dice: 0
                ),
                Box(
                    "Twos", 2 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 2),
                    lambda dice: 0
                ),
                Box(
                    "Threes", 3 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 3),
                    lambda dice: 0
                ),
                Box(
                    "Fours", 4 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 4),
                    lambda dice: 0
                ),
                Box(
                    "Fives", 5 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 5),
                    lambda dice: 0
                ),
                Box(
                    "Sixes", 6 * ndice,
                    lambda dice: Box.sum_particular_digits(dice, 6),
                    lambda dice: 0
                ),
                Box("Up. Sect. Total", 0, None, None, 0),
                Box("Up. Sect. Bonus", 0, None, None, 0)]
            if not yahtzee:
                boxes.append(
                    Box("One Pair", 12, lambda dice: Box.groups(dice, [2])))
                boxes.append(
                    Box(
                        "Two Pairs", 22, lambda dice: Box.groups(dice, [2, 2])
                    ))
                if self.maxi:
                    boxes.append(
                        Box(
                            "Three Pairs", 30,
                            lambda dice: Box.groups(dice, [2, 2, 2])
                        )
                    )
            boxes.append(
                Box(
                    "Three of a Kind", 30 if yahtzee else 18,
                    lambda dice: Box.sum_n_of_a_kind(dice, 3, yahtzee),
                    Box.chance)
            )
            boxes.append(
                Box(
                    "Four of a Kind", 30 if yahtzee else 24,
                    lambda dice: Box.sum_n_of_a_kind(dice, 4, yahtzee),
                    Box.chance
                )
            )
            if self.maxi:
                boxes.append(
                    Box(
                        "Five of a Kind", 30,
                        lambda dice: Box.sum_n_of_a_kind(dice, 5, yahtzee)
                    )
                )
            boxes.append(
                Box(
                    "Full House", 25 if yahtzee else 28,
                    lambda dice: Box.full_house(dice, yahtzee), lambda dice: 25
                )
            )
            if self.maxi:
                boxes.append(
                    Box("Castle", 33, lambda dice: Box.groups(dice, [3, 3])))
                boxes.append(
                    Box("Tower", 34, lambda dice: Box.groups(dice, [2, 4])))
            if yahtzee:
                boxes.append(
                    Box(
                        "Small Straight", 30,
                        lambda dice: Box.straight_yahtzee(dice, 4),
                        lambda dice: 30
                    )
                )
                boxes.append(
                    Box(
                        "Large Straight", 40,
                        lambda dice: Box.straight_yahtzee(dice, 5),
                        lambda dice: 40
                    )
                )
            else:
                boxes.append(
                    Box(
                        "Small Straight", 15,
                        lambda dice: Box.straight_yatzy(dice, 1, 5)
                    )
                )
                boxes.append(
                    Box(
                        "Large Straight", 20,
                        lambda dice: Box.straight_yatzy(dice, 2, 6)
                    )
                )
                if self.maxi:
                    boxes.append(
                        Box(
                            "Full Straight", 21,
                            lambda dice: Box.straight_yatzy(dice, 1, 6)
                        )
                    )
            boxes.append(Box("Chance", 6 * ndice, Box.chance))
            if self.yahtzee:
                boxes.append(Box("Yahtzee", 50, Box.yatzy))
            else:
                boxes.append(Box("Maxi Yatzy" if self.maxi else "Yatzy",
                                 100 if self.maxi else 50,
                                 lambda dice: Box.yatzy(dice, self.maxi)))
            if yahtzee:
                boxes.append(Box("Yahtzee Bonus", 0, None, None, 0))
            boxes.append(Box("Low. Sect. Total", 0, None, None, 0))
            boxes.append(Box("Grand Total", 0, None, None, 0))
            self.scores[player] = OrderedDict(
                [(box.name, box) for box in boxes])

    def award_yahtzee_bonus(self, player, dice):
        """Check if Yahtzee Bonus is to be awarded and give it"""
        # Yahtzee Bonus
        if self.yahtzee:
            # If we have already scored a Yahtzee
            if self.scores[player].get("Yahtzee").score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Yahtzee"].preview_dice(dice):
                    # Add 100 extra points to Yahtzee Bonus
                    self.scores[player]["Yahtzee Bonus"].score += 100
                    return 100
        return 0

    @staticmethod
    def get_upper_section_bonus_score_static(maxi, forced):
        """Calculate the score needed to get upper section bonus"""
        # Upper Section Bonus - if we score 63 or more in upper section
        # 84 or more for Maxi Yatzy
        upper_section_bonus = 63 if not maxi else 84
        if forced:
            # 42 for Forced Yatzy (63 for Forced Maxi Yatzy)
            upper_section_bonus -= 21
        return upper_section_bonus

    def get_upper_section_bonus_score(self):
        return Scoreboard.get_upper_section_bonus_score_static(
            self.maxi, self.forced
        )

    @staticmethod
    def get_upper_section_bonus_value_static(maxi, yahtzee):
        return 35 if yahtzee else (50 if not maxi else 100)

    def get_upper_section_bonus_value(self):
        return Scoreboard.get_upper_section_bonus_value_static(
            self.maxi, self.yahtzee
        )

    def award_upper_section_bonus(self, player):
        """Check if Upper Section Bonus is to be awarded and give it"""
        upper_section_bonus = self.get_upper_section_bonus_score()
        if self.scores[player].get(
                "Up. Sect. Total").score >= upper_section_bonus:
            # And if we didn't score the bonus yet
            if not self.scores[player].get("Up. Sect. Bonus").score:
                # Add 50 extra points to Upper Section Bonus (35 for Yahtzee)
                bonus = self.get_upper_section_bonus_value()
                self.scores[player]["Up. Sect. Bonus"].set_score(bonus)
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
        self.scores[player]["Up. Sect. Total"].set_score(total)
        # Compute and award upper section bonus
        bonus = self.award_upper_section_bonus(player)
        # Keep upper score to compute lower subtotal
        upper = total + self.scores[player].get("Up. Sect. Bonus").score
        # Proceed to compute totals
        for box in list(self.scores[player].values())[7:-2]:
            total += box.score if box.score is not None else 0
        # Compute lower section subtotal
        self.scores[player]["Low. Sect. Total"].set_score(total - upper)
        self.scores[player]["Grand Total"].set_score(total)
        return bonus

    def get_score_options(self, player, dice, perf=False):
        """Get viable scoring options, sorted in descending order"""
        # Special Yahtzee rules
        if self.yahtzee:
            # If we have already scored a Yahtzee with >0
            if self.scores[player]["Yahtzee"].score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Yahtzee"].preview_dice(dice, perf):
                    # Try to get a corresponding upper section box:
                    box = list(self.scores[player].values())[int(dice[0]) - 1]
                    if box.score is None:
                        return OrderedDict(
                            ((box.name, box.preview_dice(dice, perf)),))
                    # If no free boxes - joker rules allow to use any of lower
                    # boxes
                    res = []
                    for box in list(self.scores[player].values())[8:15]:
                        if box.score is None:
                            res.append(
                                (box.name, box.preview_joker_dice(dice, perf)))
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
                                (box.name, box.preview_joker_dice(dice, perf)))
                    return OrderedDict(res)
        # Regular scoring options
        scores = []
        for box in self.scores[player].values():
            if box.score is None:
                scores.append((box.name, box.preview_dice(dice, perf)))
                if self.forced:
                    break  # In Forced Yatzy, we only give a first unfilled box
        return OrderedDict(sorted(scores, reverse=True, key=lambda x: x[1]))

    def commit_dice_combination(self, player, dice, boxname):
        """Commit dice combination"""
        options = self.get_score_options(player, dice)
        if boxname not in options:
            raise IllegalMoveError(
                f"{ERROR} This move is not allowed in this situation."
            )
        score = 0
        # Special Yahtzee rules
        if self.yahtzee:
            # If we have already scored a Yahtzee with >0
            if self.scores[player]["Yahtzee"].score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Yahtzee"].preview_dice(dice):
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
        up_sec_total = self.scores[player].get("Up. Sect. Total").score
        remaining = max(up_sec_bonus - up_sec_total, 0)
        bonus_value = self.get_upper_section_bonus_value()
        lost = not self.check_upper_section_bonus_achievable(player)
        for box in self.scores[player].values():
            if box.name == "Up. Sect. Total":
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
            if box.name == "Up. Sect. Bonus":
                bonus = "Awarded"
                if lost:
                    bonus = "Missed"
                elif remaining:
                    bonus = f"{remaining} more"
                output.append(
                    [f"{bonus_value} pts. if ≥ {up_sec_bonus}", bonus]
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
            scores.append((player, self.scores[player]['Grand Total'].score))
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
                f"{placeemoji} {place}"
                f"{SUFFIX.get(place, 'th')} place - "
                f"{player} ({scores[player]} points)"
            )
            place += 1
            last_score = scores[player]
        return '\n'.join(output)


class Box(object):
    """This represents a single scoreboard box"""

    def __init__(self, name, max_score, rule, joker_rule=None, score=None):
        self.name = name
        self.score = score
        self.max_score = max_score
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

    def preview_dice(self, dice, perf=False):
        """Calculate, how much a hand will score in this box"""
        if perf:
            return self.rule(dice) / self.max_score
        else:
            return self.rule(dice)

    def preview_joker_dice(self, dice, perf=False):
        """Calculate, how much a joker hand will score in this box"""
        if self.joker_rule is not None:
            if perf:
                return self.joker_rule(dice) / self.max_score
            else:
                return self.joker_rule(dice)
        else:
            return self.preview_dice(dice, perf)

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
