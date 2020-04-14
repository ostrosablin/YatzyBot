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

from telegram import ParseMode, bot
from telegram.ext import Updater, CommandHandler, messagequeue
from telegram.utils.request import Request

from creds import TOKEN, REQUEST_KWARGS
from error import IllegalMoveError, PlayerError
from gamemanager import GameManager

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

gamemanager = GameManager()

WILDCARD_DICE = "*️⃣"
MAP_TURNS = {'on': "Ones", 'ac': "Aces", 'tw': "Twos", 'th': "Threes", 'fo': "Fours", 'fi': "Fives", 'si': "Sixes",
             'op': "One Pair", 'tp': "Two Pairs", '3p': "Three Pairs",
             'tk': "Three of a Kind", 'fk': "Four of a Kind", '5k': "Five of a Kind",
             'fh': "Full House", 'ca': "Castle", 'to': "Tower",
             'ss': "Small Straight", 'ls': "Large Straight", 'fs': "Full Straight",
             'ch': "Chance", 'ya': "Yatzy", 'yh': "Yahtzee", 'my': "Maxi Yatzy"}
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
                                  "Please, choose a game you want to play:\n/startyatzy - Start Yatzy game\n\n"
                                  "/startyahtzee - Start Yahtzee game\n\n/startforcedyatzy - Start Forced Yatzy game\n\n"
                                  "/startmaxiyatzy - Start Maxi Yatzy game\n\n/startforcedmaxiyatzy - Start Forced Maxi Yatzy game".format(msg),
                                  quote=False, isgroup=not is_private(update))
    elif not gamemanager.is_game_running(update.message.chat):
        try:
            logger.info("Game started - chat_id {0}".format(update.message.chat.id))
            gamemanager.game(update.message.chat).start_game(gamemanager.player(update.message.from_user))
            update.message.reply_text("Game begins! Roll dice with /roll", quote=False,
                                      isgroup=not is_private(update))
            update.message.reply_text("Current turn: {0}".format(gamemanager.current_turn(update.message.chat)),
                                      quote=False, isgroup=not is_private(update))
        except PlayerError as e:
            update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))


def startgame(bot, update, yahtzee, forced=False, maxi=False):
    if yahtzee:
        game = "Yahtzee"
    else:
        gname = []
        if forced:
            gname.append("Forced")
        if maxi:
            gname.append("Maxi")
        gname.append("Yatzy")
        game = ' '.join(gname)
    try:
        gamemanager.new_game(update.message.chat, update.message.from_user, yahtzee, forced, maxi)
        if update.message.chat.type == 'private':
            gamemanager.game(update.message.chat).start_game(gamemanager.player(update.message.from_user))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    player = gamemanager.player(update.message.from_user)
    logger.info("{0} has created a new {1} game - chat_id {2}".format(player, game, update.message.chat.id))
    if update.message.chat.type == 'private':
        update.message.reply_text("Success! You've created and joined a new solo {0} game! "
                                  "Roll dice with /roll".format(game), quote=False, isgroup=not is_private(update))
    else:
        update.message.reply_text(
            "Success! You've created and joined a new {0} game!\n\nOthers can join using /join command.\n\n"
            "When all set - use /start to begin.\n\nGame owner: {1}".format(game, player), quote=False,
            isgroup=not is_private(update))


def startyahtzee(bot, update):
    startgame(bot, update, True)


def startyatzy(bot, update):
    startgame(bot, update, False)


def startforcedyatzy(bot, update):
    startgame(bot, update, False, True, False)


def startmaxiyatzy(bot, update):
    startgame(bot, update, False, False, True)


def startforcedmaxiyatzy(bot, update):
    startgame(bot, update, False, True, True)


def chk_game_runs(update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game doesn't exist", quote=False, isgroup=not is_private(update))
        return False
    if not gamemanager.is_game_running(update.message.chat):
        update.message.reply_text("Game is not running", quote=False, isgroup=not is_private(update))
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
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))


def join(bot, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game doesn't exists", quote=False, isgroup=not is_private(update))
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).add_player(player)
        logger.info("{0} has joined a game - chat_id {1}".format(player, update.message.chat.id))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text("{0} has joined the game!".format(player), quote=False,
                              isgroup=not is_private(update))


def leave(bot, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text("Game is not exists", quote=False, isgroup=not is_private(update))
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).del_player(player)
        logger.info("{0} has left a game - chat_id {1}".format(player, update.message.chat.id))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text("{0} has left the game!".format(player), quote=False, isgroup=not is_private(update))


def roll(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        dice = gamemanager.game(update.message.chat).roll(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    saved = ""
    if gamemanager.game(update.message.chat).maxi:
        extra = gamemanager.game(update.message.chat).saved_rerolls[player]
        if extra:
            saved = "You have {0} extra saved reroll(s)\n\n".format(extra)
    update.message.reply_text(
        "{0} has rolled {1}\n\n"
        "Use /reroll to choose dice for reroll.\n\n"
        "Use /move to choose a move.\n\n{2}".format(player, ' '.join([d.to_emoji() for d in dice]), saved),
        quote=False, isgroup=not is_private(update))


def reroll(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).chk_command_usable(player)
        if not gamemanager.game(update.message.chat).hand:
            raise PlayerError("Cannot reroll - you didn't roll a hand yet")
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    sixth = ""
    saved = ""
    if gamemanager.game(update.message.chat).maxi:
        sixth = "/6 - Toggle reroll sixth dice.\n\n"
        extra = gamemanager.game(update.message.chat).saved_rerolls[player]
        if extra:
            saved = "You have {0} extra saved reroll(s)\n\n".format(extra)
    msg = "Reroll menu:\n\n{0}\n\n/rr - Reset reroll.\n\n/1 - Toggle reroll first dice.\n\n" \
          "/2 - Toggle reroll second dice.\n\n/3 - Toggle reroll third dice.\n\n/4 - Toggle reroll fourth dice.\n\n" \
          "/5 - Toggle reroll fifth dice.\n\n{1}/sa - Select all.\n\n/dr - Do reroll.\n\n" \
          "/move - Choose a move.\n\n{2}".format(dice_to_wildcard(gamemanager.game(update.message.chat)), sixth, saved)
    if gamemanager.game(update.message.chat).reroll > 1:
        if not saved:  # We we don't have saved Maxi Yatzy turns
            msg = "You have already rerolled twice. Use /move command to finish your move."
    update.message.reply_text(msg, quote=False, isgroup=not is_private(update))


def reroll_process(bot, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).chk_command_usable(player)
        if not gamemanager.game(update.message.chat).hand:
            raise PlayerError("You didn't roll a hand yet")
        if arg in ['1', '2', '3', '4', '5', '6']:
            if arg == '6' and not gamemanager.game(update.message.chat).maxi:  # 6 only for Maxi games
                return
            gamemanager.game(update.message.chat).reroll_pool_toggle(player, arg)
            update.message.reply_text("{0}".format(dice_to_wildcard(gamemanager.game(update.message.chat))),
                                      quote=False, isgroup=not is_private(update))
        elif arg == 'rr':
            gamemanager.game(update.message.chat).reroll_pool_clear(player)
            update.message.reply_text("{0}".format(dice_to_wildcard(gamemanager.game(update.message.chat))),
                                      quote=False, isgroup=not is_private(update))
        elif arg == 'sa':
            gamemanager.game(update.message.chat).reroll_pool_select_all(player)
            update.message.reply_text("{0}".format(dice_to_wildcard(gamemanager.game(update.message.chat))),
                                      quote=False, isgroup=not is_private(update))
        elif arg == 'dr':
            dice = gamemanager.game(update.message.chat).reroll_pooled(player)
            rerolllink = "/reroll - Do reroll.\n\n"
            if gamemanager.game(update.message.chat).reroll > 1:
                if gamemanager.game(update.message.chat).maxi:
                    if not gamemanager.game(update.message.chat).saved_rerolls[player]:
                        rerolllink = ""
                else:
                    rerolllink = ""
            saved = ""
            if gamemanager.game(update.message.chat).maxi:
                extra = gamemanager.game(update.message.chat).saved_rerolls[player]
                if extra:
                    saved = "You have {0} extra saved reroll(s)\n\n".format(extra)
            update.message.reply_text(
                "{0} has rolled {1}\n\n{2}/move - Do a move.\n\n{3}".format(player, ' '.join([d.to_emoji() for d in dice]),
                                                                     rerolllink, saved),
                quote=False, isgroup=not is_private(update))
        else:
            update.message.reply_text("Invalid reroll action", quote=False, isgroup=not is_private(update))
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return


def commit(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        options = gamemanager.game(update.message.chat).get_hand_score_options(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    output = []
    for i in options:
        output.append("/{0} {1} - {2} points.".format(MAP_COMMANDS[i], i, options[i]))
    if gamemanager.game(update.message.chat).reroll < 2:
        output.append("/reroll - Do reroll.")
    table = '\n\n'.join(output)
    update.message.reply_text("Your scoring options:\n\n{1}".format(player, table), quote=False,
                              isgroup=not is_private(update))


def commit_move(bot, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        score = gamemanager.game(update.message.chat).commit_turn(player, MAP_TURNS[arg])
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except (PlayerError, IllegalMoveError) as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text("{0} scores {1} for {2} points.\n\n".format(player, MAP_TURNS[arg], score), quote=False,
                              isgroup=not is_private(update))
    update.message.reply_text("Scoreboard for {0}:\n\n`{1}`".format(player, scores), quote=False,
                              parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update))
    if gamemanager.game(update.message.chat).is_completed():
        logger.info("The game is completed - chat_id {0}".format(update.message.chat.id))
        update.message.reply_text(
            'The game has ended! Final scores:\n\n{0}'.format(gamemanager.game(update.message.chat).scores_final()),
            quote=False, isgroup=not is_private(update))
    else:
        saved = ""
        if gamemanager.game(update.message.chat).maxi:
            player = gamemanager.game(update.message.chat).get_current_player()
            extra = gamemanager.game(update.message.chat).saved_rerolls[player]
            if extra:
                saved = "You have {0} extra saved reroll(s)\n\n".format(extra)
        update.message.reply_text(
            "Current turn: {0}\n\nUse /roll to roll dice.\n\nUse /score to view your scoreboard.\n\n"
            "Use /score_all to view everyone's total score.\n\n{1}".format(
                gamemanager.current_turn(update.message.chat), saved), quote=False, isgroup=not is_private(update))


def score(bot, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text("Scoreboard for {0}:\n\n`{1}`".format(player, scores), quote=False,
                              parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update))


def score_all(bot, update):
    if not chk_game_runs(update):
        return
    try:
        scores = gamemanager.game(update.message.chat).scores_final()
    except PlayerError as e:
        update.message.reply_text(str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text("Current total scores:\n\n{0}".format(scores), quote=False,
                              parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update))


def help(bot, update):
    logger.info("Help invoked")
    update.message.reply_text("Use /start command to begin and follow the instructions.\n\n"
                              "You can read on Yatzy and Yahtzee rules here:\n"
                              "https://en.wikipedia.org/wiki/Yatzy\n"
                              "https://en.wikipedia.org/wiki/Yahtzee", quote=False, isgroup=not is_private(update))


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


class MQBot(bot.Bot):
    """A subclass of Bot which delegates send method handling to MQ"""
    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or messagequeue.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop(timeout=10.0)
            super(MQBot, self).__del__()
        except:
            pass

    @messagequeue.queuedmessage
    def send_message(self, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments"""
        return super(MQBot, self).send_message(*args, **kwargs)

def main():
    mq = messagequeue.MessageQueue()
    request = Request(con_pool_size=8, **REQUEST_KWARGS)
    bot = MQBot(TOKEN, request=request, mqueue=mq)
    updater = Updater(bot=bot)

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('startyatzy', startyatzy))
    updater.dispatcher.add_handler(CommandHandler('startyahtzee', startyahtzee))
    updater.dispatcher.add_handler(CommandHandler('startforcedyatzy', startforcedyatzy))
    updater.dispatcher.add_handler(CommandHandler('startmaxiyatzy', startmaxiyatzy))
    updater.dispatcher.add_handler(CommandHandler('startforcedmaxiyatzy', startforcedmaxiyatzy))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CommandHandler('join', join))
    updater.dispatcher.add_handler(CommandHandler('leave', leave))
    updater.dispatcher.add_handler(CommandHandler('roll', roll))
    updater.dispatcher.add_handler(CommandHandler('reroll', reroll))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CommandHandler('move', commit))
    updater.dispatcher.add_handler(CommandHandler('score', score))
    updater.dispatcher.add_handler(CommandHandler('score_all', score_all))
    updater.dispatcher.add_handler(CommandHandler(['1', '2', '3', '4', '5', '6', 'dr', 'rr', 'sa'], reroll_process))
    updater.dispatcher.add_handler(
        CommandHandler(
            ['on', 'ac', 'tw', 'th', 'fo', 'fi', 'si', 'op', 'tp', '3p', 'tk', 'fk', '5k', 'fh', 'ca', 'to', 'ss', 'ls', 'fs', 'ch', 'ya', 'yh', 'my'],
            commit_move))
    updater.dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    logger.info("YatzyBot has started.")
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

    logger.info("Shutting down the bot...")
    bot.__del__()  # Force thread stop to allow process termination.

if __name__ == '__main__':
    main()
