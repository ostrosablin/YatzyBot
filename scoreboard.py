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

"""Yahtzee introduces Yahtzee bonuses and a Joker rule when a player scores a second Yahtzee."""

from collections import Counter, OrderedDict

from tabulate import tabulate

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

    def __init__(self, players, yahtzee=False):
        self.players = players  # List of players
        self.yahtzee = yahtzee
        self.scores = {}
        for player in self.players:
            boxes = [
                Box("Aces" if yahtzee else "Ones", lambda dice: Box.sum_particular_digits(dice, 1), lambda dice: 0),
                Box("Twos", lambda dice: Box.sum_particular_digits(dice, 2), lambda dice: 0),
                Box("Threes", lambda dice: Box.sum_particular_digits(dice, 3), lambda dice: 0),
                Box("Fours", lambda dice: Box.sum_particular_digits(dice, 4), lambda dice: 0),
                Box("Fives", lambda dice: Box.sum_particular_digits(dice, 5), lambda dice: 0),
                Box("Sixes", lambda dice: Box.sum_particular_digits(dice, 6), lambda dice: 0),
                Box("Upper Section Totals", None, None, 0), Box("Upper Section Bonus", None, None, 0)]
            if not yahtzee:
                boxes.append(Box("One Pair", Box.sum_pair))
                boxes.append(Box("Two Pairs", Box.sum_two_pairs))
            boxes.append(Box("Three of a Kind", lambda dice: Box.sum_n_of_a_kind(dice, 3, yahtzee), Box.chance))
            boxes.append(Box("Four of a Kind", lambda dice: Box.sum_n_of_a_kind(dice, 4, yahtzee), Box.chance))
            boxes.append(Box("Full House", lambda dice: Box.full_house(dice, yahtzee), lambda dice: 25))
            if yahtzee:
                boxes.append(Box("Small Straight", lambda dice: Box.straight_yahtzee(dice, 4), lambda dice: 30))
                boxes.append(Box("Large Straight", lambda dice: Box.straight_yahtzee(dice, 5), lambda dice: 40))
            else:
                boxes.append(Box("Small Straight", lambda dice: Box.straight_yatzy(dice, 15)))
                boxes.append(Box("Large Straight", lambda dice: Box.straight_yatzy(dice, 20)))
            boxes.append(Box("Chance", Box.chance))
            boxes.append(Box("Yahtzee" if yahtzee else "Yatzy", Box.yatzy))
            if yahtzee:
                boxes.append(Box("Yahtzee Bonus", None, None, 0))
            boxes.append(Box("Total", None, None, 0))
            self.scores[player] = OrderedDict([(box.name, box) for box in boxes])

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

    def award_upper_section_bonus(self, player):
        """Check if Upper Section Bonus is to be awarded and give it"""
        # Upper Section Bonus - if we score 63 or more in upper section
        if self.scores[player].get("Upper Section Totals").score > 62:
            # And if we didn't score the bonus yet
            if not self.scores[player].get("Upper Section Bonus").score:
                # Add 50 extra points to Upper Section Bonus (35 for Yahtzee)
                bonus = 35 if self.yahtzee else 50
                self.scores[player]["Upper Section Bonus"].set_score(bonus)
                return bonus
        return 0

    def recompute_calculated_fields(self, player):
        """Compute all calculated boxes"""
        # Recompute Upper Section Totals
        total = 0
        for box in list(self.scores[player].values())[:6]:
            total += box.score if box.score is not None else 0
        self.scores[player]["Upper Section Totals"].set_score(total)
        # Compute and award upper section bonus
        bonus = self.award_upper_section_bonus(player)
        # Proceed to compute totals
        for box in list(self.scores[player].values())[7:-1]:
            total += box.score if box.score is not None else 0
        self.scores[player]["Total"].set_score(total)
        return bonus

    def get_score_options(self, player, dice):
        """Get viable scoring options, sorted in descending order"""
        # Special Yahtzee rules
        if self.yahtzee:
            # If we have already scored a Yahtzee with >0
            if self.scores[player]["Yahtzee"].score:
                # And if we're scored another valid Yahtzee
                if self.scores[player]["Yahtzee"].preview_dice(dice):
                    # Try to get a corresponding upper section box:
                    box = list(self.scores[player].values())[int(dice[0]) - 1]
                    if box.score is None:
                        return OrderedDict(((box.name, box.preview_dice(dice)),))
                    # If no free boxes - joker rules allow to use any of lower boxes
                    res = []
                    for box in list(self.scores[player].values())[8:15]:
                        if box.score is None:
                            res.append((box.name, box.preview_joker_dice(dice)))
                    if res:
                        return OrderedDict(sorted(res, reverse=True, key=lambda x: x[1]))
                    # Finally, if there's only non-matching upper boxes left, use them and score 0
                    for box in list(self.scores[player].values())[:6]:
                        if box.score is None:
                            res.append((box.name, box.preview_joker_dice(dice)))
                    return OrderedDict(res)
        # Regular scoring options
        scores = []
        for box in self.scores[player].values():
            if box.score is None:
                scores.append((box.name, box.preview_dice(dice)))
        return OrderedDict(sorted(scores, reverse=True, key=lambda x: x[1]))

    def commit_dice_combination(self, player, dice, boxname):
        """Commit dice combination"""
        options = self.get_score_options(player, dice)
        if boxname not in options:
            raise IllegalMoveError("This move is not allowed in this situation")
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
                    if boxname == list(self.scores[player].keys())[int(dice[0]) - 1]:
                        score += self.scores[player][boxname].commit_dice(dice)
                    else:
                        score += self.scores[player][boxname].commit_joker_dice(dice)
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
        for box in self.scores[player].values():
            output.append([box.name, "" if box.score is None else str(box.score)])
            if box.name == "Upper Section Bonus":
                output.append(["", ""])
        return tabulate(output, tablefmt="simple")

    def print_scores(self):
        """Print complete scoreboard"""
        output = [[""]]
        output[0].extend(self.players)
        for box in self.scores[self.players[0]]:
            scores = [box]
            for player in self.players:
                scores.append(self.scores[player][box].score if self.scores[player][box].score is not None else "")
            output.append(scores)
        return tabulate(output, tablefmt="simple")

    def final_scores(self):
        """Get final scoring"""
        scores = []
        for player in self.players:
            scores.append((player, self.scores[player]['Total'].score))
        return OrderedDict(sorted(scores, reverse=True, key=lambda x: x[1]))

    def print_final_scores(self):
        """Get string representation of final scores"""
        scores = self.final_scores()
        output = []
        place = 1
        last_score = 0
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}
        for player in scores:
            if scores[player] == last_score:
                place -= 1
            output.append(
                "{0}{1} place - {2} ({3} points)".format(place, suffix.get(place, 'th'), player, scores[player]))
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
    def sum_pair(cls, dice):
        """Count a sum of a largest pair in roll"""
        ctr = count_dice(dice)
        largest = 0
        for i in ctr:
            if ctr[i] > 1:
                largest = max(largest, int(i))
        return largest * 2

    @classmethod
    def sum_two_pairs(cls, dice):
        """Count a sum of two pairs in roll"""
        ctr = count_dice(dice)
        pairs = []
        for i in ctr:
            if ctr[i] > 1:
                pairs.append(int(i))
        if len(pairs) < 2:
            return 0
        return sum([pair * 2 for pair in pairs])

    @classmethod
    def sum_n_of_a_kind(cls, dice, n, yahtzee):
        """Count a sum for dice in N of a Kind"""
        ctr = count_dice(dice)
        for i in ctr:
            if ctr[i] >= n:
                if yahtzee:  # In Yahtzee, all hand is counted
                    return sum([int(d) for d in dice])
                else:
                    return int(i) * n
        return 0

    @classmethod
    def straight_yahtzee(cls, dice, n):
        """Find a run of N consecutive dice"""
        roll = sort_and_dedupe(dice)
        score = {4: 30, 5: 40}
        seq = 0
        for i in range(len(roll) - 1):
            if roll[i] + 1 == roll[i + 1]:
                seq = max(seq + 1, 2)
            else:
                seq = 0
            if seq >= n:
                break
        return score.get(n, 0) if seq >= n else 0

    @classmethod
    def straight_yatzy(cls, dice, target):
        """Find a one of two runs of 5 consecutive dice"""
        roll = sort_and_dedupe(dice)
        total = roll[0]
        for i in range(len(roll) - 1):
            if roll[i] + 1 == roll[i + 1]:
                total += roll[i + 1]
            else:
                return 0
        return total if total == target else 0

    @classmethod
    def full_house(cls, dice, yahtzee):
        """Find a Full House dice set"""
        ctr = count_dice(dice)
        if len(ctr) != 2:
            return 0
        for i in ctr:
            if ctr[i] not in (2, 3):
                return 0
        if yahtzee:
            return 25
        return sum([int(d) for d in dice])

    @classmethod
    def yatzy(cls, dice):
        """Find a Yatzy/Yahtzee dice set"""
        return 0 if len(count_dice(dice)) != 1 else 50

    @classmethod
    def chance(cls, dice):
        """Calculate a sum of a hand"""
        return sum([int(d) for d in dice])
