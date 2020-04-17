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

from const import (
    WILDCARD_DICE,
    ROLL,
    MOVE,
    SCORE,
    SCORE_ALL,
    RESET_REROLL,
    SELECT_ALL,
    DO_REROLL,
    HELP,
    START,
    STOP,
    JOIN,
    LEAVE,
    ERROR,
    INFO,
    HELLO,
    CONGRATS,
    MOVE_BOX_ICONS,
    MAP_TURNS,
    MAP_COMMANDS)
from creds import TOKEN, REQUEST_KWARGS
from error import IllegalMoveError, PlayerError
from gamemanager import GameManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

gamemanager = GameManager()


def dice_to_wildcard(game):
    res = []
    for i in range(len(game.hand)):
        if str(i + 1) in game.reroll_pool:
            res.append(WILDCARD_DICE)
        else:
            res.append(game.hand[i].to_emoji())
    return ' '.join(res)


def start(_, update):
    msg = ""
    logger.info(f"Start attempt - chat_id {update.message.chat.id}")
    if is_private(update):
        msg = (
            f"{INFO} NOTE: Solo mode, if you want to play a multiplayer "
            f"game with friends, add me to some group and use "
            f"{START} /start command there.\n\n"
        )
    if not gamemanager.is_game_created(
            update.message.chat) or gamemanager.game(
            update.message.chat).finished:
        update.message.reply_text(
            f"Hello! {HELLO} I'm Yatzy/Yahtzee bot. To see the help, use "
            f"{HELP} /help command.\n\nLet's get started, eh?\n\n{msg}"
            f"Please, choose a game you want to play:\n\n"
            f"{START} /startyatzy - Start Yatzy game.\n\n"
            f"{START} /startyahtzee - Start Yahtzee game.\n\n"
            f"{START} /startforcedyatzy - Start Forced Yatzy game.\n\n"
            f"{START} /startmaxiyatzy - Start Maxi Yatzy game.\n\n"
            f"{START} /startforcedmaxiyatzy - Start Forced Maxi Yatzy game.",
            quote=False, isgroup=not is_private(update)
        )
    elif not gamemanager.is_game_running(update.message.chat):
        try:
            logger.info(f"Game started - chat_id {update.message.chat.id}")
            gamemanager.game(
                update.message.chat).start_game(
                gamemanager.player(
                    update.message.from_user))
            update.message.reply_text(
                f"{START} Game begins! Roll dice with {ROLL} /roll command."
                f"\n\nTo stop the game, use {STOP} /stop command.\n\n"
                f"Current turn: "
                f"{gamemanager.current_turn(update.message.chat)}",
                quote=False, isgroup=not is_private(update)
            )
        except PlayerError as e:
            update.message.reply_text(
                str(e), quote=False, isgroup=not is_private(update))


def startgame(_, update, yahtzee, forced=False, maxi=False):
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
        gamemanager.new_game(
            update.message.chat,
            update.message.from_user,
            yahtzee,
            forced,
            maxi)
        if update.message.chat.type == 'private':
            gamemanager.game(
                update.message.chat).start_game(
                gamemanager.player(
                    update.message.from_user))
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    player = gamemanager.player(update.message.from_user)
    logger.info(
        f"{player} has created a new {game} game"
        f" - chat_id {update.message.chat.id}"
    )
    if update.message.chat.type == 'private':
        update.message.reply_text(
            f"{CONGRATS} Success! You've created and joined a new solo "
            f"{game} game!\n\nRoll dice with {ROLL} /roll command.\n\n"
            f"To stop the game, use {STOP} /stop command.",
            quote=False, isgroup=not is_private(update)
        )
    else:
        update.message.reply_text(
            f"{CONGRATS} Success! You've created and joined a new {game} game!"
            f"\n\nOthers can join using {JOIN} /join command.\n\n"
            f"When all set - use {START} /start to begin.\n\n"
            f"Game owner: {player}", quote=False,
            isgroup=not is_private(update)
        )


def startyahtzee(bot_instance, update):
    startgame(bot_instance, update, True)


def startyatzy(bot_instance, update):
    startgame(bot_instance, update, False)


def startforcedyatzy(bot_instance, update):
    startgame(bot_instance, update, False, True, False)


def startmaxiyatzy(bot_instance, update):
    startgame(bot_instance, update, False, False, True)


def startforcedmaxiyatzy(bot_instance, update):
    startgame(bot_instance, update, False, True, True)


def chk_game_runs(update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text(
            f"{ERROR} Game doesn't exist (try {START} /start).",
            quote=False, isgroup=not is_private(update)
        )
        return False
    if not gamemanager.is_game_running(update.message.chat):
        update.message.reply_text(
            f"{ERROR} Game is not running (try {START} /start).",
            quote=False, isgroup=not is_private(update)
        )
        return False
    return True


def is_private(update):
    if update.message.chat.type == 'private':
        return True
    return False


def stop(_, update):
    if not chk_game_runs(update):
        return
    try:
        gamemanager.game(
            update.message.chat).stop_game(
            gamemanager.player(
                update.message.from_user))
        logger.info(f"Stopped game - chat_id {update.message.chat.id}")
        update.message.reply_text(
            f"{STOP} Current game has been stopped.\n\n", quote=False,
            isgroup=not is_private(update)
        )
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))


def join(_, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text(
            f"{ERROR} Game doesn't exist (try {START} /start).", quote=False,
            isgroup=not is_private(update)
        )
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).add_player(player)
        logger.info(
            f"{player} has joined a game - chat_id {update.message.chat.id}"
        )
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text(
        f"{JOIN} {player} has joined the game!\n\n"
        f"{LEAVE} /leave - Leave the game lobby.", quote=False,
        isgroup=not is_private(update)
    )


def leave(_, update):
    if not gamemanager.is_game_created(update.message.chat):
        update.message.reply_text(
            f"{ERROR} Game doesn't exist (try {START} /start).", quote=False,
            isgroup=not is_private(update)
        )
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).del_player(player)
        logger.info(
            f"{player} has left a game - chat_id {update.message.chat.id}"
        )
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text(
        f"{LEAVE} {player} has left the game!", quote=False,
        isgroup=not is_private(update)
    )


def roll(_, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        dice = gamemanager.game(update.message.chat).roll(player)
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    saved = ""
    if gamemanager.game(update.message.chat).maxi:
        extra = gamemanager.game(update.message.chat).saved_rerolls[player]
        if extra:
            saved = f"{INFO} You have {extra} extra saved reroll(s).\n\n"
    update.message.reply_text(
        f"{ROLL} {player} has rolled (Reroll 0/2):\n\n"
        f"{' '.join([d.to_emoji() for d in dice])}\n\n"
        f"Use {ROLL} /reroll to choose dice for reroll.\n\n"
        f"Use {MOVE} /move to choose a move.\n\n{saved}",
        quote=False, isgroup=not is_private(update))


def reroll(_, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).chk_command_usable(player)
        if not gamemanager.game(update.message.chat).hand:
            raise PlayerError(
                f"{ERROR} Cannot reroll - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    dice = gamemanager.game(update.message.chat).hand
    sixth = ""
    saved = ""
    if gamemanager.game(update.message.chat).maxi:
        sixth = f"{dice[5].to_emoji()} /6 - Toggle reroll sixth dice.\n\n"
        extra = gamemanager.game(update.message.chat).saved_rerolls[player]
        if extra:
            saved = f"{INFO} You have {extra} extra saved reroll(s).\n\n"
    rollnumber = gamemanager.game(update.message.chat).reroll
    msg = (f"{ROLL} Reroll menu (Reroll {rollnumber}/2):\n\n"
           f"{dice_to_wildcard(gamemanager.game(update.message.chat))}\n\n"
           f"{RESET_REROLL} /rr - Reset reroll (deselect all).\n\n"
           f"{dice[0].to_emoji()} /1 - Toggle reroll first dice.\n\n"
           f"{dice[1].to_emoji()} /2 - Toggle reroll second dice.\n\n"
           f"{dice[2].to_emoji()} /3 - Toggle reroll third dice.\n\n"
           f"{dice[3].to_emoji()} /4 - Toggle reroll fourth dice.\n\n"
           f"{dice[4].to_emoji()} /5 - Toggle reroll fifth dice.\n\n"
           f"{sixth}{SELECT_ALL} /sa - Select all.\n\n"
           f"{DO_REROLL} /dr - Do reroll.\n\n"
           f"{MOVE} /move - Choose a move.\n\n{saved}"
           )
    if gamemanager.game(update.message.chat).reroll > 1:
        if not saved:  # We don't have saved Maxi Yatzy turns
            msg = (
                f"{ERROR} You have already rerolled twice.\n"
                f"Use {MOVE} /move command to finish your move."
            )
    update.message.reply_text(msg, quote=False, isgroup=not is_private(update))


def reroll_process(_, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        gamemanager.game(update.message.chat).chk_command_usable(player)
        if not gamemanager.game(update.message.chat).hand:
            raise PlayerError(
                f"{ERROR} Cannot reroll - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
        if arg in ['1', '2', '3', '4', '5', '6']:
            # 6 only for Maxi games
            if arg == '6' and not gamemanager.game(update.message.chat).maxi:
                return
            gamemanager.game(
                update.message.chat).reroll_pool_toggle(
                player, arg)
            update.message.reply_text(
                f"{dice_to_wildcard(gamemanager.game(update.message.chat))}",
                quote=False, isgroup=not is_private(update)
            )
        elif arg == 'rr':
            gamemanager.game(update.message.chat).reroll_pool_clear(player)
            update.message.reply_text(
                f"{dice_to_wildcard(gamemanager.game(update.message.chat))}",
                quote=False, isgroup=not is_private(update)
            )
        elif arg == 'sa':
            gamemanager.game(
                update.message.chat).reroll_pool_select_all(player)
            update.message.reply_text(
                f"{dice_to_wildcard(gamemanager.game(update.message.chat))}",
                quote=False, isgroup=not is_private(update)
            )
        elif arg == 'dr':
            dice = gamemanager.game(update.message.chat).reroll_pooled(player)
            rerolllink = f"{ROLL} /reroll - Do reroll.\n\n"
            if gamemanager.game(update.message.chat).reroll > 1:
                if gamemanager.game(update.message.chat).maxi:
                    if not gamemanager.game(
                            update.message.chat).saved_rerolls[player]:
                        rerolllink = ""
                else:
                    rerolllink = ""
            saved = ""
            if gamemanager.game(update.message.chat).maxi:
                extra = gamemanager.game(
                    update.message.chat).saved_rerolls[player]
                if extra:
                    saved = (
                        f"{INFO} You have {extra} "
                        f"extra saved reroll(s).\n\n"
                    )
            rollnumber = gamemanager.game(update.message.chat).reroll
            update.message.reply_text(
                f"{ROLL} {player} has rolled (Reroll {rollnumber}/2):\n\n"
                f"{' '.join([d.to_emoji() for d in dice])}\n\n"
                f"{rerolllink}{MOVE} /move - Do a move.\n\n{saved}",
                quote=False, isgroup=not is_private(update)
            )
        else:
            update.message.reply_text(
                f"{ERROR} Invalid reroll action.", quote=False,
                isgroup=not is_private(update)
            )
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return


def commit(_, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        options = gamemanager.game(
            update.message.chat).get_hand_score_options(player)
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    output = []
    for i in options:
        output.append(
            f"{MOVE_BOX_ICONS[i]} /{MAP_COMMANDS[i]} "
            f"{i} - {options[i]} points."
        )
    if gamemanager.game(update.message.chat).reroll < 2:
        output.append(f"{ROLL} /reroll - Do reroll.")
    else:
        if gamemanager.game(update.message.chat).maxi:
            if gamemanager.game(update.message.chat).saved_rerolls[player]:
                output.append(f"{ROLL} /reroll - Do reroll.")
    table = '\n\n'.join(output)
    update.message.reply_text(
        f"{MOVE} Your scoring options:\n\n{table}", quote=False,
        isgroup=not is_private(update)
    )


def commit_move(_, update):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    acquired_extra = ""
    if gamemanager.game(update.message.chat).maxi:
        saved_rerolls = (2 - gamemanager.game(update.message.chat).reroll)
        if saved_rerolls:
            acquired_extra = f"{INFO} Saved +{saved_rerolls} extra reroll(s)"
    try:
        score_pos = gamemanager.game(
            update.message.chat).commit_turn(
            player, MAP_TURNS[arg])
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except (PlayerError, IllegalMoveError) as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text(
        f"{MOVE} {player} scores {MAP_TURNS[arg]} for {score_pos} points.\n\n"
        f"{acquired_extra}",
        quote=False, isgroup=not is_private(update)
    )
    update.message.reply_text(
        f"{SCORE} Scoreboard for {player}:\n\n`{scores}`", quote=False,
        parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update)
    )
    if gamemanager.game(update.message.chat).is_completed():
        logger.info(
            f"The game is completed - chat_id {update.message.chat.id}"
        )
        update.message.reply_text(
            f'{CONGRATS} The game has ended! Final scores:\n\n'
            f'{gamemanager.game(update.message.chat).scores_final()}',
            quote=False, isgroup=not is_private(update))
    else:
        saved = ""
        if gamemanager.game(update.message.chat).maxi:
            player = gamemanager.game(update.message.chat).get_current_player()
            extra = gamemanager.game(update.message.chat).saved_rerolls[player]
            if extra:
                saved = f"{INFO} You have {extra} extra saved reroll(s).\n\n"
        update.message.reply_text(
            f"{INFO} Current turn: "
            f"{gamemanager.current_turn(update.message.chat)}\n\n"
            f"Use {ROLL} /roll to roll dice.\n\n"
            f"Use {SCORE} /score to view your scoreboard.\n\n"
            f"Use {SCORE_ALL} /score_all to view everyone's total score.\n\n"
            f"{saved}",
            quote=False, isgroup=not is_private(update)
        )


def score(_, update):
    if not chk_game_runs(update):
        return
    player = gamemanager.player(update.message.from_user)
    try:
        scores = gamemanager.game(update.message.chat).scores_player(player)
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text(
        f"{SCORE} Scoreboard for {player}:\n\n`{scores}`", quote=False,
        parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update)
    )


def score_all(_, update):
    if not chk_game_runs(update):
        return
    try:
        scores = gamemanager.game(update.message.chat).scores_final()
    except PlayerError as e:
        update.message.reply_text(
            str(e), quote=False, isgroup=not is_private(update))
        return
    update.message.reply_text(
        f"{SCORE_ALL} Current total scores:\n\n{scores}", quote=False,
        parse_mode=ParseMode.MARKDOWN, isgroup=not is_private(update)
    )


def bot_help(_, update):
    logger.info("Help invoked")
    update.message.reply_text(
        f"{HELP} Use {START} /start command to begin and follow the"
        f" instructions.\n\nYou can read on Yatzy and Yahtzee rules here:\n"
        f"https://en.wikipedia.org/wiki/Yatzy\n"
        f"https://en.wikipedia.org/wiki/Yahtzee",
        quote=False, isgroup=not is_private(update)
    )


def error(_, update, err):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, err)


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
        except (ValueError, BaseException):
            pass

    @messagequeue.queuedmessage
    def send_message(self, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments"""
        return super(MQBot, self).send_message(*args, **kwargs)


def main():
    mq = messagequeue.MessageQueue()
    request = Request(con_pool_size=8, **REQUEST_KWARGS)
    yatzybot = MQBot(TOKEN, request=request, mqueue=mq)
    updater = Updater(bot=yatzybot)

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('startyatzy', startyatzy))
    updater.dispatcher.add_handler(
        CommandHandler(
            'startyahtzee',
            startyahtzee))
    updater.dispatcher.add_handler(
        CommandHandler(
            'startforcedyatzy',
            startforcedyatzy))
    updater.dispatcher.add_handler(
        CommandHandler(
            'startmaxiyatzy',
            startmaxiyatzy))
    updater.dispatcher.add_handler(
        CommandHandler(
            'startforcedmaxiyatzy',
            startforcedmaxiyatzy))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CommandHandler('join', join))
    updater.dispatcher.add_handler(CommandHandler('leave', leave))
    updater.dispatcher.add_handler(CommandHandler('roll', roll))
    updater.dispatcher.add_handler(CommandHandler('reroll', reroll))
    updater.dispatcher.add_handler(CommandHandler('help', bot_help))
    updater.dispatcher.add_handler(CommandHandler('move', commit))
    updater.dispatcher.add_handler(CommandHandler('score', score))
    updater.dispatcher.add_handler(CommandHandler('score_all', score_all))
    updater.dispatcher.add_handler(
        CommandHandler(
            ['1', '2', '3', '4', '5', '6', 'dr', 'rr', 'sa'],
            reroll_process))
    updater.dispatcher.add_handler(
        CommandHandler(
            ['on', 'ac', 'tw', 'th', 'fo', 'fi',
             'si', 'op', 'tp', '3p', 'tk', 'fk',
             '5k', 'fh', 'ca', 'to', 'ss', 'ls',
             'fs', 'ch', 'ya', 'yh', 'my'],
            commit_move))
    updater.dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    logger.info("YatzyBot has started.")
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

    logger.info("Shutting down the bot...")
    yatzybot.__del__()  # Force thread stop to allow process termination.


if __name__ == '__main__':
    main()
