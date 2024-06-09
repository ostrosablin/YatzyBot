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

import logging
from asyncio import sleep
from functools import wraps
from time import time

from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    AIORateLimiter,
    ContextTypes
)

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
    OWNER,
    KICK,
    MOVE_BOX_ICONS,
    MOVE_ICONS,
    MAP_TURNS,
    MAP_COMMANDS,
    SCORED,
    UPPER,
    LOWER,
    JOKER,
    BEST,
    RULES,
)
from creds import TOKEN
from error import IllegalMoveError, PlayerError
from gamemanager import GameManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

gamemanager = GameManager()
answer_timer = {}


def dice_to_wildcard(game):
    res = []
    for die in range(len(game.hand)):
        if str(die + 1) in game.reroll_pool:
            res.append(WILDCARD_DICE)
        else:
            res.append(game.hand[die].to_emoji())
    return ' '.join(res)


async def answer(update, msg, parse_mode=None, delay=1.5):
    kw = {
        'quote': False, 'message_thread_id': update.message.message_thread_id
    }
    if parse_mode is not None:
        kw['parse_mode'] = parse_mode
    chat = update.message.chat
    current = time()
    real_delay = max(answer_timer.get(chat, 0.0) - current, 0.0)
    answer_timer[chat] = current + real_delay + delay
    await sleep(real_delay)
    await update.message.reply_text(msg, **kw)


def get_game(update):
    return gamemanager.game(update.message.chat)


def get_player(update):
    return gamemanager.player(update.message.from_user)


def get_current_player(update):
    return gamemanager.current_turn(update.message.chat)


async def _game_chooser_msg(update):
    msg = ""
    if is_private(update):
        msg = (
            f"{INFO} NOTE: Solo mode, if you want to play a multiplayer "
            f"game with friends, add me to some group and use "
            f"{START} /start command there.\n\n"
        )
    reply = (
        f"Hello! {HELLO} I'm Yatzy/Yahtzee bot. To see the help, use "
        f"{HELP} /help command.\n\nLet's get started, eh?\n\n{msg}"
        f"Please, choose a game you want to play:\n\n"
        f"{START} /startyatzy - Start Yatzy game.\n\n"
        f"{START} /startyahtzee - Start Yahtzee game.\n\n"
        f"{START} /startforcedyatzy - Start Forced Yatzy game.\n\n"
        f"{START} /startmaxiyatzy - Start Maxi Yatzy game.\n\n"
        f"{START} /startforcedmaxiyatzy - Start Forced Maxi Yatzy game."
    )
    await answer(update, reply)


async def _game_start_msg(update, turn_order_messages, game):
    for msg in turn_order_messages:
        await answer(update, msg, delay=5)
    player = gamemanager.current_turn(update.message.chat)
    msg = (
        f"{START} Game begins! Roll dice with {ROLL} /roll command.\n\n"
        f"To see help for {game.get_name()}, use {HELP} /help command.\n\n"
        f"To stop the game, use {STOP} /stop command.\n\n"
        f"{INFO} Current turn ({game.turn}/{game.get_max_turn_number()}): "
        f"<a href=\"tg://user?id={player.id}\">{player}</a>"
    )
    await answer(update, msg, parse_mode=ParseMode.HTML)


async def start(update, _: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start attempt - chat_id {update.message.chat.id}")
    game = get_game(update)
    if not gamemanager.is_game_created(update.message.chat) or game.finished:
        await _game_chooser_msg(update)
    elif not gamemanager.is_game_running(update.message.chat):
        try:
            turn_order_msgs = game.start_game(get_player(update))
            logger.info(f"Game started - chat_id {update.message.chat.id}")
            await _game_start_msg(update, turn_order_msgs, game)
        except PlayerError as e:
            await answer(update, str(e))
    else:
        await answer(update, f"{ERROR} Game is already started.")


async def _game_created_msg(update, player, gamename):
    if is_private(update):
        msg = (
            f"{CONGRATS} Success! You've created and joined a new solo "
            f"{gamename} game!\n\nRoll dice with {ROLL} /roll command.\n\n"
            f"To see help for this game variant, use {HELP} /help command.\n\n"
            f"To stop the game, use {STOP} /stop command."
        )
    else:
        msg = (
            f"{CONGRATS} Success! You've created and joined a new {gamename}"
            f" game!\n\nOthers can join using {JOIN} /join command.\n\n"
            f"When all set - use {START} /start to begin.\n\n"
            f"{OWNER} Game owner: {player}"
        )
    await answer(update, msg)


async def startgame(update, yahtzee, forced=False, maxi=False):
    player = get_player(update)
    if yahtzee:
        gamename = "Yahtzee"
    else:
        gamename = []
        if forced:
            gamename.append("Forced")
        if maxi:
            gamename.append("Maxi")
        gamename.append("Yatzy")
        gamename = ' '.join(gamename)
    try:
        gamemanager.new_game(
            update.message.chat,
            update.message.from_user,
            yahtzee,
            forced,
            maxi
        )
        game = get_game(update)
        if is_private(update):
            game.start_game(player)
    except PlayerError as e:
        await answer(update, str(e))
        return
    logger.info(
        f"{player} has created a new {gamename} game"
        f" - chat_id {update.message.chat.id}"
    )
    await _game_created_msg(update, player, gamename)


async def startyahtzee(update, _: ContextTypes.DEFAULT_TYPE):
    await startgame(update, True)


async def startyatzy(update, _: ContextTypes.DEFAULT_TYPE):
    await startgame(update, False)


async def startforcedyatzy(update, _: ContextTypes.DEFAULT_TYPE):
    await startgame(update, False, True, False)


async def startmaxiyatzy(update, _: ContextTypes.DEFAULT_TYPE):
    await startgame(update, False, False, True)


async def startforcedmaxiyatzy(update, _: ContextTypes.DEFAULT_TYPE):
    await startgame(update, False, True, True)


def chk_game_runs(func):
    @wraps(func)
    async def wrapper(update, _: ContextTypes.DEFAULT_TYPE):
        if not gamemanager.is_game_created(update.message.chat):
            await answer(
                update, f"{ERROR} Game doesn't exist (try {START} /start)."
            )
            return
        if not gamemanager.is_game_running(update.message.chat):
            await answer(
                update,
                f"{ERROR} Game is not running (try {START} /start)."
            )
            return
        await func(update, _)

    return wrapper


def roster_check(func):
    @wraps(func)
    async def wrapper(update, _: ContextTypes.DEFAULT_TYPE):
        if not gamemanager.is_game_created(update.message.chat):
            await answer(
                update, f"{ERROR} Game doesn't exist (try {START} /start)."
            )
            return
        if get_game(update).finished:
            await answer(
                update,
                f"{ERROR} This game is already finished, create a new game "
                f"(try {START} /start)."
            )
            return
        await func(update, _)

    return wrapper


def is_private(update):
    if update.message.chat.type == ChatType.PRIVATE:
        return True
    return False


@roster_check
async def stop(update, _: ContextTypes.DEFAULT_TYPE):
    try:
        get_game(update).stop_game(get_player(update))
        logger.info(f"Stopped game - chat_id {update.message.chat.id}")
        await answer(update, f"{STOP} Current game has been stopped.\n\n")
    except PlayerError as e:
        await answer(update, str(e))


async def owner_transfer_msg(update, oldowner, newowner):
    if oldowner != newowner:
        logger.info(
            f"Owner {oldowner} left the game, new owner is"
            f" {newowner} - chat_id {update.message.chat.id}"
        )
        await answer(
            update, f"{OWNER} Owner {oldowner} has left the game. "
                    f"Ownership is transferred to player {newowner}."
        )


@roster_check
async def kick(update, _: ContextTypes.DEFAULT_TYPE):
    try:
        game = get_game(update)
        kicker = get_player(update)
        oldowner = game.owner
        kicked = game.kick_player(kicker)
        kicked_msg = f"{kicker} has kicked {kicked} from the game"
        if kicker == kicked or (kicked is None and kicker == oldowner):
            kicked_msg = f"{kicker} kicks self from the game"
        elif kicked is None:
            kicked_msg = f"{kicker} has kicked {oldowner} from the game"
        logger.info(f"{kicked_msg} - chat_id {update.message.chat.id}")
        await answer(update, f"{KICK} {kicked_msg}.\n\n")
        if kicked is None:
            logger.info(
                f"Game stopped (owner is kicked) - "
                f"chat_id {update.message.chat.id}"
            )
            await answer(update, f"{STOP} Owner was kicked. Game is aborted.")
            return
        await owner_transfer_msg(update, oldowner, game.owner)
        if game.finished and not game.has_active_players():
            logger.info(
                f"Game stopped (abandoned) - chat_id {update.message.chat.id}"
            )
            await answer(update, f"{STOP} Last player kicked. Game is over.")
        await score_messages(update, kicked, game.finished)
        if game.finished:
            return
        await current_turn_msg(update)
    except PlayerError as e:
        await answer(update, str(e))


@roster_check
async def join(update, _: ContextTypes.DEFAULT_TYPE):
    player = get_player(update)
    try:
        get_game(update).add_player(player)
        logger.info(
            f"{player} has joined a game - chat_id {update.message.chat.id}"
        )
    except PlayerError as e:
        await answer(update, str(e))
        return
    await answer(
        update,
        f"{JOIN} {player} has joined the game!\n\n"
        f"{LEAVE} /leave - Leave the game lobby.\n\n"
        f"NOTE: You can also use /leave later to leave a game in progress. "
        f"This will forfeit your remaining turns and any remaining unfilled "
        f"scoreboard boxes will be filled with zeros. However, you will still "
        f"be listed in game totals with your last score.\n\n"
        f"Owner can also {KICK} /kick player, whose turn is it now "
        f"(e.g. to get rid of idling player, who blocks the game progress)."
    )


@roster_check
async def leave(update, _: ContextTypes.DEFAULT_TYPE):
    player = get_player(update)
    game = get_game(update)
    try:
        is_lobby = not game.started
        turn = None
        oldowner = game.owner
        if not is_lobby:
            turn = game.get_current_player()
        lobby = " lobby" if is_lobby else ""
        logger.info(
            f"{player} has left a game{lobby}"
            f" - chat_id {update.message.chat.id}"
        )
        game.del_player(player)
        switch_turn = not game.finished and turn == player
    except PlayerError as e:
        await answer(update, str(e))
        return
    await answer(update, f"{LEAVE} {player} has left the game{lobby}!")
    await owner_transfer_msg(update, oldowner, game.owner)
    if game.finished and not game.has_active_players():
        logger.info(
            f"Game stopped (abandoned) - chat_id {update.message.chat.id}"
        )
        await answer(
            update, f"{STOP} Last player has left the game. Game is over."
        )
    if not is_lobby:
        await score_messages(update, player, game.finished)
        if not switch_turn:
            return
        await current_turn_msg(update)


def mk_movelink(options, metrics, compact=False):
    movelink = []
    best_value = None
    best_list = []
    for option in metrics:
        if best_value is None:
            best_value = metrics[option]
        if metrics[option] < best_value and metrics[option] <= 0.5:
            break
        best_list.append(
            f"{MOVE_BOX_ICONS[option]} /{MAP_COMMANDS[option]} "
            f"{option} - {options[option]} points.\n\n"
        )
    if len(options) != len(best_list):
        movelink.append(f"{MOVE} /move to choose a move.\n\n")
        if not compact:
            movelink.append(
                f"\n{BEST} Best move{'' if len(best_list) == 1 else 's'}:\n\n"
            )
            best_list.append('\n')
    if not compact or len(options) == len(best_list):
        movelink.extend(best_list)
    return "".join(movelink)


async def roll_msg(update, game, player, dice):
    rerolllink = (f"{ROLL} /reroll to choose dice for reroll.\n\n"
                  f"{ROLL} /qr <positions> to do a quick reroll.\n\n")
    if game.reroll > 1:
        if game.maxi:
            if not game.saved_rerolls[player]:
                rerolllink = ""
        else:
            rerolllink = ""
    saved = get_extra_rerolls(game, player)
    rollnumber = game.reroll
    options = game.get_hand_score_options(player)
    metrics = game.get_hand_score_options(player, True)
    movelink = mk_movelink(options, metrics)
    automove = ""
    if not rerolllink:
        if len(options) == 1:
            movelink = (f"{INFO} You have no rerolls left and only one valid"
                        f" move, finishing turn automatically.\n\n")
            automove = MAP_COMMANDS[next(iter(options))]
    await answer(
        update,
        f"{ROLL} {player} has rolled (Reroll {rollnumber}/2):\n\n"
        f"{' '.join([d.to_emoji() for d in dice])}\n\n"
        f"{rerolllink}{movelink}{saved}"
    )
    if automove:
        await process_move(update, game, player, automove, auto=True)


@chk_game_runs
async def roll(update, _: ContextTypes.DEFAULT_TYPE):
    game = get_game(update)
    player = get_player(update)
    try:
        dice = game.roll(player)
    except PlayerError as e:
        await answer(update, str(e))
        return
    await roll_msg(update, game, player, dice)


async def reroll_msg(update, game, player, dice):
    saved = get_extra_rerolls(game, player)
    sixth = ""
    if game.maxi:
        sixth = f"{dice[5].to_emoji()} /6 - Toggle reroll sixth dice.\n\n"
    rollnumber = game.reroll
    options = game.get_hand_score_options(player)
    metrics = game.get_hand_score_options(player, True)
    movelink = mk_movelink(options, metrics, compact=True)
    msg = (
        f"{ROLL} Reroll menu (Reroll {rollnumber}/2):\n\n"
        f"{dice_to_wildcard(game)}\n\n"
        f"{RESET_REROLL} /rr - Reset reroll (deselect all).\n\n"
        f"{dice[0].to_emoji()} /1 - Toggle reroll first dice.\n\n"
        f"{dice[1].to_emoji()} /2 - Toggle reroll second dice.\n\n"
        f"{dice[2].to_emoji()} /3 - Toggle reroll third dice.\n\n"
        f"{dice[3].to_emoji()} /4 - Toggle reroll fourth dice.\n\n"
        f"{dice[4].to_emoji()} /5 - Toggle reroll fifth dice.\n\n"
        f"{sixth}{SELECT_ALL} /sa - Select all.\n\n"
        f"{DO_REROLL} /dr - Do reroll.\n\n"
        f"{movelink}{saved}"
    )
    if game.reroll > 1:
        if not saved:  # We don't have saved Maxi Yatzy turns
            maxi_remark = ""
            if game.maxi:
                maxi_remark = " (no saved rerolls)"
            msg = (
                f"{ERROR} You have already rerolled twice{maxi_remark}.\n\n"
                f"Use {MOVE} /move command to finish your move."
            )
    await answer(update, msg)


@chk_game_runs
async def reroll(update, _: ContextTypes.DEFAULT_TYPE):
    game = get_game(update)
    player = get_player(update)
    try:
        game.chk_command_usable(player)
        if not game.hand:
            raise PlayerError(
                f"{ERROR} Cannot reroll - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
    except PlayerError as e:
        await answer(update, str(e))
        return
    dice = game.hand
    await reroll_msg(update, game, player, dice)


async def send_dice(update, game):
    await answer(update, dice_to_wildcard(game))


def explain_quick_reroll():
    raise PlayerError(
        f"{ERROR} This is a quick reroll command: it requires "
        f"arguments and cannot be used without any like that. "
        f"You should pass positions of dice to reroll.\n\n"
        f"To reroll specific dice (e.g. first three), just "
        f"type their positions, like that:\n\n"
        f"/qr 123\n\n"
        f"To reroll all dice, any of these commands will work:"
        f"\n\n/qr a\n/qr all\n/qr -\n/qr *\n\n"
        f"If you wish to hold particular dice (e.g. keep last "
        f"two), and reroll others, any of these will work:"
        f"\n\n/qr h45\n/qr !45"
    )


def quick_reroll_set(game, command):
    if not command:
        explain_quick_reroll()
    allowed = f"12345{'6' if game.maxi else ''}"
    if "a" in command or "-" in command or "*" in command:
        command = allowed
    for digit in allowed:
        if command.count(digit) > 1:
            raise PlayerError(
                f"{ERROR} Duplicate digits were found in quick reroll"
                f" command. This likely indicates a typo. Please"
                f" check your input and try again."
            )
    for char in command:
        if char not in allowed and char not in " \t\nh!":
            raise PlayerError(
                f"{ERROR} Illegal characters were found in quick reroll"
                f" command. This might be a typo. Please check your"
                f" input and try again."
            )
    if "h" in command or "!" in command:
        inverse = list(allowed)
        for char in command:
            if char in allowed:
                if char in inverse:
                    inverse.remove(char)
            elif char in "h!":
                pass
            else:
                inverse.append(char)
                break
        command = "".join(inverse)
    return command


@chk_game_runs
async def reroll_process(update, _: ContextTypes.DEFAULT_TYPE):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    args = update.message.text.strip().split(None)[1:]
    game = get_game(update)
    player = get_player(update)
    try:
        game.chk_command_usable(player)
        if not game.hand:
            raise PlayerError(
                f"{ERROR} Cannot reroll - you didn't roll a hand yet "
                f"(try {ROLL} /roll)."
            )
        if arg in ['1', '2', '3', '4', '5', '6']:
            # 6 only for Maxi games
            if arg == '6' and not game.maxi:
                return
            game.reroll_pool_toggle(player, arg)
            await send_dice(update, game)
        elif arg == 'rr':
            game.reroll_pool_clear(player)
            await send_dice(update, game)
        elif arg == 'sa':
            game.reroll_pool_select_all(player)
            await send_dice(update, game)
        elif arg == 'dr' or arg == 'qr' or arg == 'q':
            if arg == 'qr' or arg == 'q':
                to_reroll = quick_reroll_set(game, "".join(args).lower())
                dice = game.reroll_dice(player, to_reroll)
                game.reroll_pool_clear(player)
            else:
                dice = game.reroll_pooled(player)
            await roll_msg(update, game, player, dice)
        else:
            await answer(update, f"{ERROR} Invalid reroll action.")
    except PlayerError as e:
        await answer(update, str(e))
        return


@chk_game_runs
async def commit(update, _: ContextTypes.DEFAULT_TYPE):
    game = get_game(update)
    player = get_player(update)
    try:
        options = game.get_hand_score_options(player)
    except PlayerError as e:
        await answer(update, str(e))
        return
    output = []
    for option in options:
        output.append(
            f"{MOVE_BOX_ICONS[option]} /{MAP_COMMANDS[option]} "
            f"{option} - {options[option]} points."
        )
    if game.reroll < 2 or (game.maxi and game.saved_rerolls[player]):
        output.append(f"{ROLL} /reroll - to choose dice for reroll.")
        output.append(f"{ROLL} /qr <positions> - to do a quick reroll.\n\n")
    table = '\n\n'.join(output)
    await answer(update, f"{MOVE} Your scoring options:\n\n{table}")


def get_extra_rerolls(game, player):
    saved = ""
    if game.maxi:
        extra = game.saved_rerolls[player]
        if extra:
            saved = f"{INFO} You have {extra} extra saved reroll(s).\n\n"
    return saved


async def current_turn_msg(update):
    game = get_game(update)
    player = get_current_player(update)
    saved = get_extra_rerolls(game, player)
    await answer(
        update,
        f"{INFO} Current turn ({game.turn}/{game.get_max_turn_number()}): "
        f"<a href=\"tg://user?id={player.id}\">{player}</a>\n\n"
        f"Use {ROLL} /roll to roll dice.\n\n"
        f"Use {SCORE} /score to view your scoreboard.\n\n"
        f"Use {SCORE} /score_all to view everyone's scoreboards.\n\n"
        f"Use {SCORE_ALL} /score_total to view everyone's total score.\n\n"
        f"Use {HELP} /help to see help for this game variant.\n\n"
        f"{saved}",
        parse_mode=ParseMode.HTML
    )


async def move_msg(update, saved_rerolls, player, move, points, auto=False):
    acquired_extra = ""
    if saved_rerolls:
        acquired_extra = f"{INFO} Saved +{saved_rerolls} extra reroll(s)"
    await answer(
        update,
        f"{SCORED} {player} scores {MOVE_ICONS[move]} {MAP_TURNS[move]}"
        f" for {points} points.\n\n"
        f"{acquired_extra}",
        delay=5 if auto else 1
    )


async def process_move(update, game, player, move, auto=False):
    saved_rerolls = 0
    if game.maxi:
        saved_rerolls = (2 - game.reroll)
    try:
        score_pos = game.commit_turn(player, MAP_TURNS[move])
    except (PlayerError, IllegalMoveError) as e:
        await answer(update, str(e))
        return
    await move_msg(update, saved_rerolls, player, move, score_pos, auto)
    await scoreboard_msg(update, player)
    if gamemanager.game(update.message.chat).is_completed():
        await totalscore_msg(update, finished=True)
    else:
        await current_turn_msg(update)


@chk_game_runs
async def commit_move(update, _: ContextTypes.DEFAULT_TYPE):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    game = get_game(update)
    player = get_player(update)
    await process_move(update, game, player, arg)


async def scoreboard_msg(update, player):
    try:
        game = get_game(update)
        if player is None:
            playerlist = game.players
        else:
            playerlist = [player]
        for plr in playerlist:
            scores = game.scores_player(plr)
            await answer(
                update,
                f"{SCORE} Scoreboard for {plr}:\n\n`{scores}`",
                parse_mode=ParseMode.MARKDOWN
            )
    except PlayerError as e:
        await answer(update, str(e))


@chk_game_runs
async def score(update, _: ContextTypes.DEFAULT_TYPE):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    requestor = get_player(update)
    if arg == "score":
        player = requestor
    else:
        player = None
    try:
        get_game(update).chk_command_usable_any_turn(requestor)
    except PlayerError as e:
        await answer(update, str(e))
        return
    await scoreboard_msg(update, player)


async def totalscore_msg(update, finished=False):
    player = get_player(update)
    emoji = SCORE_ALL
    msg = "Current total scores"
    if finished:
        emoji = CONGRATS
        msg = "The game has ended! Final scores"
        logger.info(
            f"The game is completed - chat_id {update.message.chat.id}"
        )
    try:
        scores = get_game(update).scores_final(player)
    except PlayerError as e:
        await answer(update, str(e))
        return
    await answer(update, f"{emoji} {msg}:\n\n{scores}")


async def score_messages(update, player, finished):
    await scoreboard_msg(update, player)
    await totalscore_msg(update, finished)


@chk_game_runs
async def score_all(update, _: ContextTypes.DEFAULT_TYPE):
    try:
        player = get_player(update)
        get_game(update).chk_command_usable_any_turn(player)
    except PlayerError as e:
        await answer(update, str(e))
        return
    await totalscore_msg(update)


async def bot_help(update, _: ContextTypes.DEFAULT_TYPE):
    logger.info("Help invoked")
    game = get_game(update)
    chat = update.message.chat
    if not gamemanager.is_game_created(chat) or game.finished:
        await answer(
            update,
            f"{HELP} Use {START} /start command to begin and follow the "
            f"instructions.\n\nYou can read on Yatzy and Yahtzee rules here:\n"
            f"https://en.wikipedia.org/wiki/Yatzy\n"
            f"https://en.wikipedia.org/wiki/Yahtzee\n\n"
            f"Use {HELP} /help command again during a game to see help for "
            f"current game variation."
        )
    else:
        avg_dice = 3 + (1 if game.maxi else 0) - (1 if game.forced else 0)
        avg_dice_words = {2: "two", 3: "three", 4: "four"}
        msg = [f"{HELP} {game.get_name()} rules.\n"]
        if game.forced:
            msg.append(f"{INFO} Forced rule: In this variant you must "
                       f"score combinations in exactly same sequence as "
                       f"listed in scoreboard, i.e. starting with Ones, then "
                       f"Twos and so on. Due to added difficulty, requirement "
                       f"for upper section bonus is reduced to "
                       f"{game.get_upper_section_bonus_score()}.\n")
        dice_count = "six" if game.maxi else "five"
        rolls_remark = ""
        if game.maxi:
            rolls_remark = " (not counting saved rerolls)"
        rounds = "fifteen"
        if game.yahtzee:
            rounds = "thirteen"
        elif game.maxi:
            rounds = "twenty"
        msg.append(f"{RULES} The objective of the game is to score points by "
                   f"rolling {dice_count} dice to make certain combinations. "
                   f"The dice can be rolled up to three times in a "
                   f"turn{rolls_remark} to try to make various scoring "
                   f"combinations. After first roll, player can keep any dice "
                   f"they want, and reroll others. The game consists of "
                   f"{rounds} rounds. After each round, the player must "
                   f"choose which scoring category is to be used for that "
                   f"round (even if it's scores for zero points). Once a "
                   f"category has been used in the game, it cannot be used "
                   f"again. The scoring categories have varying point values, "
                   f"some of which are fixed values and others for which the "
                   f"score depends on the value of the dice. The player who "
                   f"scores the most points is winner of the game. You can "
                   f"find scoring categories descriptions below.\n")
        msg.append(f"{UPPER} Upper section:\n")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['ac']} Aces: Any combination. Score is "
                       f"sum of dice showing the number 1.")
        else:
            msg.append(f"{MOVE_ICONS['on']} Ones: Any combination. Score is "
                       f"sum of dice showing the number 1.")
        msg.append(f"{MOVE_ICONS['tw']} Twos: Any combination. Score is sum "
                   f"of dice showing the number 2.")
        msg.append(f"{MOVE_ICONS['th']} Threes: Any combination. Score is sum "
                   f"of dice showing the number 3.")
        msg.append(f"{MOVE_ICONS['fo']} Fours: Any combination. Score is sum "
                   f"of dice showing the number 4.")
        msg.append(f"{MOVE_ICONS['fi']} Fives: Any combination. Score is sum "
                   f"of dice showing the number 5.")
        msg.append(f"{MOVE_ICONS['si']} Sixes: Any combination. Score is sum "
                   f"of dice showing the number 6.\n")
        msg.append(f"{SCORED} Upper section bonus: If you manage to score "
                   f"at least {game.get_upper_section_bonus_score()} points "
                   f"(an average of {avg_dice_words[avg_dice]} in each box) "
                   f"in the upper section, you are awarded a bonus of "
                   f"{game.get_upper_section_bonus_value()} points.\n")
        msg.append(f"{LOWER} Lower section:\n")
        if not game.yahtzee:
            msg.append(f"{MOVE_ICONS['op']} One Pair: Two dice showing the "
                       f"same number (if there's more than one pair, highest "
                       f"one is chosen). Score is sum of those two dice.")
            if game.maxi:
                maxi_pair_remark = (" (if there's more than two pairs, "
                                    "highest two are chosen)")
            else:
                maxi_pair_remark = ""
            msg.append(f"{MOVE_ICONS['tp']} Two Pairs: Two different pairs "
                       f"of dice{maxi_pair_remark}. Score is sum of dice in "
                       f"those two pairs.")
            if game.maxi:
                msg.append(f"{MOVE_ICONS['3p']} Three Pairs: Three different "
                           f"pairs of dice. Score is sum of all dice.")
        maxi_tk_remark = ""
        if game.maxi:
            maxi_tk_remark = (" (if there's more than one Three of a Kind, "
                              "highest one is chosen)")
        msg.append(f"{MOVE_ICONS['tk']} Three of a Kind: Three dice showing "
                   f"same number{maxi_tk_remark}. Score is sum of "
                   f"{'all dice' if game.yahtzee else 'those three dice'}.")
        msg.append(f"{MOVE_ICONS['fk']} Four of a Kind: Four dice showing "
                   f"same number. Score is sum of "
                   f"{'all dice' if game.yahtzee else 'those four dice'}.")
        if game.maxi:
            msg.append(f"{MOVE_ICONS['5k']} Five of a Kind: Five dice showing "
                       f"same number. Score is sum of those five dice.")
        fh_points = 'sum of all dice'
        if game.yahtzee:
            fh_points = '25 points'
        elif game.maxi:
            fh_points = 'sum of those five dice'
        msg.append(f"{MOVE_ICONS['fh']} Full House: A set of three dice of "
                   f"one number and two dice of different number. Score is "
                   f"{fh_points}.")
        if game.maxi:
            msg.append(f"{MOVE_ICONS['ca']} Castle: Two different sets of "
                       f"three dice showing same number. Score is sum of all "
                       f"dice.")
            msg.append(f"{MOVE_ICONS['to']} Tower: A set of four dice of one "
                       f"number and two dice of different number. Score is "
                       f"sum of all dice.")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['ss']} Small Straight: Any set of four "
                       f"sequential dice (e.g. 1-2-3-4, 2-3-4-5 or 3-4-5-6). "
                       f"Score is 30 points.")
            msg.append(f"{MOVE_ICONS['ls']} Large Straight: Any set of five "
                       f"sequential dice (e.g. 1-2-3-4-5 or 2-3-4-5-6). Score "
                       f"is 40 points.")
        else:
            st_points = 'sum of all dice'
            if game.maxi:
                st_points = 'sum of those five dice'
            msg.append(f"{MOVE_ICONS['ss']} Small Straight: The combination "
                       f"1-2-3-4-5. Score is 15 points ({st_points}).")
            msg.append(f"{MOVE_ICONS['ls']} Large Straight: The combination "
                       f"2-3-4-5-6. Score is 20 points ({st_points}).")
            if game.maxi:
                msg.append(f"{MOVE_ICONS['fs']} Full Straight: The "
                           f"combination 1-2-3-4-5-6. Score is 21 points "
                           f"(sum of all dice).")
        msg.append(f"{MOVE_ICONS['ch']} Chance: Any combination. Score is sum "
                   f"of all dice.")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['yh']} Yahtzee: All five dice showing "
                       f"the same number. Score is 50 points.\n")
        else:
            if game.maxi:
                msg.append(f"{MOVE_ICONS['my']} Maxi Yatzy: All six dice "
                           f"showing the same number. Score is 100 points.\n")
            else:
                msg.append(f"{MOVE_ICONS['ya']} Yatzy: All five dice showing "
                           f"the same number. Score is 50 points.\n")
        if game.maxi:
            msg.append(f"{INFO} Reroll saving mechanics: You can save unused "
                       f"rerolls (e.g. if you move right after initial roll "
                       f"or after first reroll) and use them during future "
                       f"turns.\n")
        if game.yahtzee:
            msg.append(f"{SCORED} Yahtzee Bonus: If you roll more than one "
                       f"Yahtzee during a game and have Yahtzee box filled "
                       f"with 50 points, you are awarded a bonus of "
                       f"100 points for second and any subsequent Yahtzees.\n")
            msg.append(f"{JOKER} Joker Rule: If you are awarded a "
                       f"Yahtzee Bonus, you can score your hand as a Joker "
                       f"under following rules:\n\n{MOVE_ICONS['ac']} If the "
                       f"corresponding Upper Section box is unused then that "
                       f"category must be used.\n{MOVE_ICONS['tw']} If the "
                       f"corresponding Upper Section box has been used "
                       f"already, a Lower Section box must be used. The "
                       f"Yahtzee acts as a Joker so that the Full House, "
                       f"Small Straight and Large Straight categories can be "
                       f"used to score 25, 30 or 40 points (respectively), "
                       f"even though the dice do not meet the normal "
                       f"requirement for those categories.\n"
                       f"{MOVE_ICONS['th']} If the corresponding Upper "
                       f"Section box and all Lower Section boxes have been "
                       f"used, an unused Upper Section box must be used, "
                       f"scoring 0 points.\n")
        await answer(
            update,
            "\n".join(msg)
        )


async def error(update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.error('Update "%s" caused error "%s"', update, context.error)


def main():
    application = (
        Application.
        builder().
        token(TOKEN).
        rate_limiter(AIORateLimiter()).
        build()
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('startyatzy', startyatzy))
    application.add_handler(
        CommandHandler(
            'startyahtzee',
            startyahtzee))
    application.add_handler(
        CommandHandler(
            'startforcedyatzy',
            startforcedyatzy))
    application.add_handler(
        CommandHandler(
            'startmaxiyatzy',
            startmaxiyatzy))
    application.add_handler(
        CommandHandler(
            'startforcedmaxiyatzy',
            startforcedmaxiyatzy))
    application.add_handler(CommandHandler('stop', stop))
    application.add_handler(CommandHandler('join', join))
    application.add_handler(CommandHandler('leave', leave))
    application.add_handler(CommandHandler('kick', kick))
    application.add_handler(CommandHandler('roll', roll))
    application.add_handler(CommandHandler('reroll', reroll))
    application.add_handler(CommandHandler('help', bot_help))
    application.add_handler(CommandHandler('move', commit))
    application.add_handler(CommandHandler('score_total', score_all))
    application.add_handler(
        CommandHandler(['score', 'score_all'], score)
    )
    application.add_handler(
        CommandHandler(
            ['1', '2', '3', '4', '5', '6', 'dr', 'rr', 'sa', 'qr', 'q'],
            reroll_process
        )
    )
    application.add_handler(
        CommandHandler(
            ['on', 'ac', 'tw', 'th', 'fo', 'fi',
             'si', 'op', 'tp', '3p', 'tk', 'fk',
             '5k', 'fh', 'ca', 'to', 'ss', 'ls',
             'fs', 'ch', 'ya', 'yh', 'my'],
            commit_move
        )
    )
    application.add_error_handler(error)

    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    # Start the Bot
    logger.info("YatzyBot has started.")
    application.run_polling()


if __name__ == '__main__':
    main()
