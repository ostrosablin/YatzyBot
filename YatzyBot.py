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

import logging

from telegram import ParseMode
from telegram.ext import Updater, CommandHandler

from creds import TOKEN, REQUEST_KWARGS
from error import IllegalMoveError, PlayerError
from gamemanager import GameManager

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

gamemanager = GameManager()

WILDCARD_DICE = "*️⃣"
MAP_TURNS = {'on': "Ones", 'ac': "Aces", 'tw': "Twos", 'th': "Threes", 'fo': "Fours", 'fi': "Fives", 'si': "Sixes",
             'op': "One Pair", 'tp': "Two Pairs", 'tk': "Three of a Kind", 'fk': "Four of a Kind", 'fh': "Full House",
             'ss': "Small Straight", 'ls': "Large Straight", 'ch': "Chance", 'ya': "Yatzy", 'yh': "Yahtzee"}
MAP_COMMANDS = {v: k for k, v in MAP_TURNS.items()}


def dice_to_wildcard(game):
    res = []
    for i in range(len(game.hand)):
        if str(i + 1) in game.reroll_pool:
            res.append(WILDCARD_DICE)
        else:
            res.append(game.hand[i].to_emoji())
    return ' '.join(res)


def start(bot, update):
    msg = ""
    logger.info("Start attempt - chat_id {0}".format(update.message.chat.id))
    if is_private(update):
        msg = "NOTE: Solo mode, if you want to play a multiplayer game with friends, add me to some group and use /start command there.\n\n"
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Hello! I'm Yatzy/Yahtzee bot. To see the help, use /help command.\n\n"
                                  "Let's get started, eh?\n\n{0}"
                                  "Please, choose a game you want to play:\n/startyatzy - Start Yatzy game\n"
                                  "/startyahtzee - Start Yahtzee game".format(msg),
                                  quote=False)
    elif not gamemanager.is_game_running(update.message.chat):
        try:
            logger.info("Game started - chat_id {0}".format(update.message.chat.id))
            gamemanager.game(update.message.chat).start_game(gamemanager.player(update.message.from_user))
            update.message.reply_text("Game begins! Roll dice with /roll", quote=False)
            update.message.reply_text("Current turn: {0}".format(gamemanager.current_turn(update.message.chat)),
                                      quote=False)
        except PlayerError as e:
            update.message.reply_text(str(e), quote=False)


def startgame(bot, update, yahtzee):
    game = "Yahtzee" if yahtzee else "Yatzy"
    try:
        gamemanager.new_game(update.message.chat, update.message.from_user, yahtzee)
        if update.message.chat.type == 'private':
            gamemanager.game(update.message.chat).start_game(gamemanager.player(update.message.from_user))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    player = gamemanager.player(update.message.from_user)
    logger.info("{0} has created a new {1} game - chat_id {2}".format(player, game, update.message.chat.id))
    if update.message.chat.type == 'private':
        update.message.reply_text("Success! You've created and joined a new solo {0} game! "
                                  "Roll dice with /roll".format(game), quote=False)
    else:
        update.message.reply_text(
            "Success! You've created and joined a new {0} game!\n\nOthers can join using /join command.\n"
            "When all set - use /start to begin.\n\nGame owner: {1}".format(game, player), quote=False)


def startyahtzee(bot, update):
    startgame(bot, update, True)


def startyatzy(bot, update):
    startgame(bot, update, False)


def chk_game_runs(update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game doesn't exist", quote=False)
        return False
    if not gamemanager.is_game_running(update.message.chat):
        update.message.reply_text("Game is not running", quote=False)
        return False
    return True


def is_private(update):
    if update.message.chat.type == 'private':
        return True
    return False


def stop(bot, update):
    if not chk_game_runs(update):
        return
    try:
        gamemanager.game(update.message.chat).stop_game(gamemanager.player(update.message.from_user))
        logger.info("Stopped game - chat_id {0}".format(update.message.chat.id))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)


def join(bot, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game is not exists", quote=False)
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).add_player(player)
        logger.info("{0} has joined a game - chat_id {1}".format(player, update.message.chat.id))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    update.message.reply_text("{0} has joined the game!".format(player), quote=False)


def leave(bot, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game is not exists", quote=False)
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).del_player(player)
        logger.info("{0} has left a game - chat_id {1}".format(player, update.message.chat.id))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    update.message.reply_text("{0} has left the game!".format(player), quote=False)


def roll(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        dice = gamemanager.game(update.message.chat).roll(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    update.message.reply_text(
        "{0} has rolled {1}\n\n"
        "Use /reroll to choose dice for reroll.\n"
        "Use /move to choose a move.\n".format(player, ' '.join([d.to_emoji() for d in dice])),
        quote=False)


def reroll(bot, update):
    if not chk_game_runs(update):
        return
    msg = "Reroll menu:\n\n{0}\n\n/rr - Reset reroll.\n\n/1 - Toggle reroll first dice.\n\n" \
          "/2 - Toggle reroll second dice.\n\n/3 - Toggle reroll third dice.\n\n/4 - Toggle reroll fourth dice.\n\n" \
          "/5 - Toggle reroll fifth dice.\n\n/dr - Do reroll.\n\n" \
          "/move - Choose a move.".format(dice_to_wildcard(gamemanager.game(update.message.chat)))
    if gamemanager.game(update.message.chat).reroll > 1:
        msg = "You have already rerolled twice. Proceed to /move move."
    update.message.reply_text(msg, quote=False)


def reroll_process(bot, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        if arg in ['1', '2', '3', '4', '5']:
            gamemanager.game(update.message.chat).reroll_pool_toggle(player, arg)
            update.message.reply_text("{0}".format(dice_to_wildcard(gamemanager.game(update.message.chat))),
                                      quote=False)
        elif arg == 'rr':
            gamemanager.game(update.message.chat).reroll_pool_clear()
            update.message.reply_text("{0}".format(dice_to_wildcard(gamemanager.game(update.message.chat))),
                                      quote=False)
        elif arg == 'dr':
            dice = gamemanager.game(update.message.chat).reroll_pooled(player)
            rerolllink = ""
            if gamemanager.game(update.message.chat).reroll < 2:
                rerolllink = "/reroll - Do reroll.\n"
            update.message.reply_text(
                "{0} has rolled {1}\n\n{2}/move - Do a move.".format(player, ' '.join([d.to_emoji() for d in dice]),
                                                                     rerolllink), quote=False)
        else:
            update.message.reply_text("Invalid reroll action", quote=False)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return


def commit(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        options = gamemanager.game(update.message.chat).get_hand_score_options(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    output = []
    for i in options:
        output.append("/{0} {1} - {2} points.".format(MAP_COMMANDS[i], i, options[i]))
    if gamemanager.game(update.message.chat).reroll < 2:
        output.append("/reroll - Do reroll.")
    table = '\n\n'.join(output)
    update.message.reply_text("Your scoring options:\n\n{1}".format(player, table), quote=False)


def commit_move(bot, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        score = gamemanager.game(update.message.chat).commit_turn(player, MAP_TURNS[arg])
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except (PlayerError, IllegalMoveError) as e:
        update.message.reply_text(str(e), quote=False)
        return
    update.message.reply_text("{0} scores {1} for {2} points.\n\n".format(player, MAP_TURNS[arg], score), quote=False)
    update.message.reply_text("Scoreboard for {0}:\n\n`{1}`".format(player, scores), quote=False,
                              parse_mode=ParseMode.MARKDOWN)
    if gamemanager.game(update.message.chat).is_completed():
        logger.info("The game is completed - chat_id {0}".format(player, update.message.chat.id))
        update.message.reply_text(
            'The game has ended! Final scores:\n\n{0}'.format(gamemanager.game(update.message.chat).scores_final()))
    else:
        update.message.reply_text(
            "Current turn: {0}\n\nUse /roll to roll dice.\n\nUse /score to view your scoreboard.".format(
                gamemanager.current_turn(update.message.chat)),
            quote=False)


def score(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False)
        return
    update.message.reply_text("Scoreboard for {0}:\n\n`{1}`".format(player, scores), quote=False,
                              parse_mode=ParseMode.MARKDOWN)


def help(bot, update):
    logger.info("Help invoked")
    update.message.reply_text("Use /start command to begin and follow the instructions.\n\n"
                              "You can read on Yatzy and Yahtzee rules here:\n"
                              "https://en.wikipedia.org/wiki/Yatzy\n"
                              "https://en.wikipedia.org/wiki/Yahtzee", quote=False)


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    updater = Updater(TOKEN, request_kwargs=REQUEST_KWARGS)

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('startyatzy', startyatzy))
    updater.dispatcher.add_handler(CommandHandler('startyahtzee', startyahtzee))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CommandHandler('join', join))
    updater.dispatcher.add_handler(CommandHandler('leave', leave))
    updater.dispatcher.add_handler(CommandHandler('roll', roll))
    updater.dispatcher.add_handler(CommandHandler('reroll', reroll))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CommandHandler('move', commit))
    updater.dispatcher.add_handler(CommandHandler('score', score))
    updater.dispatcher.add_handler(CommandHandler(['1', '2', '3', '4', '5', 'dr', 'rr'], reroll_process))
    updater.dispatcher.add_handler(
        CommandHandler(
            ['on', 'ac', 'tw', 'th', 'fo', 'fi', 'si', 'op', 'tp', 'tk', 'fk', 'fh', 'ss', 'ls', 'ch', 'ya', 'yh'],
            commit_move))
    updater.dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
