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
from functools import wraps
from time import time

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
from creds import TOKEN, REQUEST_KWARGS
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


def auto_group(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        chat_id = 0
        if "chat_id" in kwargs:
            chat_id = kwargs["chat_id"]
        elif len(args) > 0:
            chat_id = args[0]
        is_group = (chat_id < 0)
        return method(self, *args, **kwargs, isgroup=is_group)
    return wrapper


def answer(update, msg, parse_mode=None, delay=1.5):
    kw = {
        'quote': False, 'message_thread_id': update.message.message_thread_id
    }
    if parse_mode is not None:
        kw['parse_mode'] = parse_mode
    chat = update.message.chat
    current = time()
    real_delay = max(answer_timer.get(chat, 0.0) - current, 0.0)
    answer_timer[chat] = current + real_delay + delay
    answer_timer["queue"].run_once(
        answer_callback, real_delay, context=(update, msg, kw)
    )


def answer_callback(context):
    update, msg, kw = context.job.context
    update.message.reply_text(msg, **kw)


def get_game(update):
    return gamemanager.game(update.message.chat)


def get_player(update):
    return gamemanager.player(update.message.from_user)


def get_current_player(update):
    return gamemanager.current_turn(update.message.chat)


def _game_chooser_msg(update):
    msg = ""
    if is_private(update):
        msg = (
            f"{INFO} ПРИМЕЧАНИЕ: Соло-режим, если вы хотите сыграть игру с "
            f"друзьями, добавьте меня в какую-нибудь группу и используйте "
            f"команду {START} /start чтобы создать многопользовательскую "
            f"игру.\n\n"
        )
    reply = (
        f"Здравствуйте! {HELLO} Я - бот для игры в Йетзи и Яхтзи. Чтобы "
        f"почитать справку, используйте команду {HELP} /help.\n\n"
        f"Ну, что ж, давайте приступим?\n\n{msg}"
        f"Пожалуйста, выберите игру, в которую вы хотите сыграть:\n\n"
        f"{START} /startyatzy - Начать игру Йетзи.\n\n"
        f"{START} /startyahtzee - Начать игру Яхтзи.\n\n"
        f"{START} /startforcedyatzy - Начать игру Последовательное Йетзи.\n\n"
        f"{START} /startmaxiyatzy - Начать игру Макси Йетзи.\n\n"
        f"{START} /startforcedmaxiyatzy - Начать игру Последовательное Макси "
        f"Йетзи."
    )
    answer(update, reply)


def _game_start_msg(update, turn_order_messages, game):
    for msg in turn_order_messages:
        answer(update, msg, delay=5)
    player = gamemanager.current_turn(update.message.chat)
    msg = (
        f"{START} Игра началась!\n\n"
        f"{ROLL} /roll - бросить кубики.\n\n"
        f"{HELP} /help - правила варианта {game.get_name()}.\n\n"
        f"{STOP} /stop - остановить игру.\n\n"
        f"{INFO} Сейчас ходит ({game.turn}/{game.get_max_turn_number()}): "
        f"<a href=\"tg://user?id={player.id}\">{player}</a>"
    )
    answer(update, msg, parse_mode=ParseMode.HTML)


def start(update, _):
    logger.info(f"Попытка начать игру - chat_id {update.message.chat.id}")
    game = get_game(update)
    if not gamemanager.is_game_created(update.message.chat) or game.finished:
        _game_chooser_msg(update)
    elif not gamemanager.is_game_running(update.message.chat):
        try:
            turn_order_msgs = game.start_game(get_player(update))
            logger.info(f"Игра начата - chat_id {update.message.chat.id}")
            _game_start_msg(update, turn_order_msgs, game)
        except PlayerError as e:
            answer(update, str(e))
    else:
        answer(update, f"{ERROR} Игра уже начата.")


def _game_created_msg(update, player, gamename):
    if is_private(update):
        msg = (
            f"{CONGRATS} Успешно! Вы создали и подключились к новой одиночной "
            f"игре {gamename}!\n\n"
            f"{ROLL} /roll - бросить кубики.\n\n"
            f"{HELP} /help - правила для этого варианта игры.\n\n"
            f"{STOP} /stop - остановить игру."
        )
    else:
        msg = (
            f"{CONGRATS} Успешно! Вы создали и подключились к новой игре "
            f"{gamename}!\n\nДругие могут подключиться с помощью команды "
            f"{JOIN} /join.\n\nКогда все будут готовы, используйте команду "
            f"{START} /start чтобы начать игру.\n\n"
            f"{OWNER} Владелец игры: {player}"
        )
    answer(update, msg)


def startgame(update, yahtzee, forced=False, maxi=False):
    player = get_player(update)
    if yahtzee:
        gamename = "Яхтзи"
    else:
        gamename = []
        if forced:
            gamename.append("Последовательное")
        if maxi:
            gamename.append("Макси")
        gamename.append("Йетзи")
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
        answer(update, str(e))
        return
    logger.info(
        f"{player} создал новую игру {gamename}"
        f" - chat_id {update.message.chat.id}"
    )
    _game_created_msg(update, player, gamename)


def startyahtzee(update, _):
    startgame(update, True)


def startyatzy(update, _):
    startgame(update, False)


def startforcedyatzy(update, _):
    startgame(update, False, True, False)


def startmaxiyatzy(update, _):
    startgame(update, False, False, True)


def startforcedmaxiyatzy(update, _):
    startgame(update, False, True, True)


def chk_game_runs(func):
    @wraps(func)
    def wrapper(update, _):
        if not gamemanager.is_game_created(update.message.chat):
            answer(
                update,
                f"{ERROR} Игра не существует (попробуйте {START} /start)."
            )
            return
        if not gamemanager.is_game_running(update.message.chat):
            answer(
                update,
                f"{ERROR} Игра не начата (попробуйте {START} /start)."
            )
            return
        func(update, _)
    return wrapper


def roster_check(func):
    @wraps(func)
    def wrapper(update, _):
        if not gamemanager.is_game_created(update.message.chat):
            answer(
                update,
                f"{ERROR} Игра не существует (попробуйте {START} /start)."
            )
            return
        if get_game(update).finished:
            answer(
                update,
                f"{ERROR} Эта игра уже окончена, создайте новую игру "
                f"(попробуйте {START} /start)."
            )
            return
        func(update, _)
    return wrapper


def is_private(update):
    if update.message.chat.type == 'private':
        return True
    return False


@roster_check
def stop(update, _):
    try:
        get_game(update).stop_game(get_player(update))
        logger.info(f"Игра остановлена - chat_id {update.message.chat.id}")
        answer(update, f"{STOP} Текущая игра была остановлена.\n\n")
    except PlayerError as e:
        answer(update, str(e))


def owner_transfer_msg(update, oldowner, newowner):
    if oldowner != newowner:
        logger.info(
            f"Владелец {oldowner} покинул игру, новый владелец:"
            f" {newowner} - chat_id {update.message.chat.id}"
        )
        answer(
            update, f"{OWNER} Владелец {oldowner} покинул игру. "
                    f"Права владельца переданы игроку {newowner}."
        )


@roster_check
def kick(update, _):
    try:
        game = get_game(update)
        kicker = get_player(update)
        oldowner = game.owner
        kicked = game.kick_player(kicker)
        kicked_msg = f"{kicker} выгнал {kicked} из игры"
        if kicker == kicked or (kicked is None and kicker == oldowner):
            kicked_msg = f"{kicker} выгнал сам себя из игры"
        elif kicked is None:
            kicked_msg = f"{kicker} выгнал {oldowner} из игры"
        logger.info(f"{kicked_msg} - chat_id {update.message.chat.id}")
        answer(update, f"{KICK} {kicked_msg}.\n\n")
        if kicked is None:
            logger.info(
                f"Игра отменена (выгнан владелец) - "
                f"chat_id {update.message.chat.id}"
            )
            answer(update, f"{STOP} Владелец выгнан из игры, игра отменена.")
            return
        owner_transfer_msg(update, oldowner, game.owner)
        if game.finished and not game.has_active_players():
            logger.info(
                f"Игру покинули все игроки - chat_id {update.message.chat.id}"
            )
            answer(update, f"{STOP} Последний игрок выгнан. Игра окончена.")
        score_messages(update, kicked, game.finished)
        if game.finished:
            return
        current_turn_msg(update)
    except PlayerError as e:
        answer(update, str(e))


@roster_check
def join(update, _):
    player = get_player(update)
    try:
        get_game(update).add_player(player)
        logger.info(
            f"{player} подключился к игре - chat_id {update.message.chat.id}"
        )
    except PlayerError as e:
        answer(update, str(e))
        return
    answer(
        update,
        f"{JOIN} {player} подключился к игре!\n\n"
        f"{LEAVE} /leave - Покинуть лобби игры.\n\n"
        f"ПРИМЕЧАНИЕ: Вы можете также использовать команду /leave во время "
        f"игры, чтобы покинуть уже начатую игру. Это аннулирует все ваши "
        f"оставшиеся ходы и все незаполненные строчки таблицы очков будут "
        f"заполнены нулями. Однако, вы всё равно останетесь в таблице итогов "
        f"игры со счётом, который был у вас на момент выхода из игры.\n\n"
        f"Владелец также может выгонять командой {KICK} /kick игрока, который "
        f"ходит сейчас (например, чтобы избавиться от игрока, который "
        f"бездействует в свой ход и мешает игровому процессу)."
    )


@roster_check
def leave(update, _):
    player = get_player(update)
    game = get_game(update)
    try:
        is_lobby = not game.started
        turn = None
        oldowner = game.owner
        if not is_lobby:
            turn = game.get_current_player()
        lobby = "лобби игры" if is_lobby else "игру"
        logger.info(
            f"{player} покинул {lobby}"
            f" - chat_id {update.message.chat.id}"
        )
        game.del_player(player)
        switch_turn = not game.finished and turn == player
    except PlayerError as e:
        answer(update, str(e))
        return
    answer(update, f"{LEAVE} {player} покинул {lobby}!")
    owner_transfer_msg(update, oldowner, game.owner)
    if game.finished and not game.has_active_players():
        logger.info(
            f"Игру покинули все игроки - chat_id {update.message.chat.id}"
        )
        answer(update, f"{STOP} Последний игрок вышел из игры. Игра окончена.")
    if not is_lobby:
        score_messages(update, player, game.finished)
        if not switch_turn:
            return
        current_turn_msg(update)


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
            f"{option} - {options[option]} очков.\n\n"
        )
    if len(options) != len(best_list):
        movelink.append(f"{MOVE} /move - выбрать ход.\n\n")
        if not compact:
            movelink.append(
                f"\n{BEST} "
                f"{'Лучший ход' if len(best_list) == 1 else 'Лучшие ходы'}"
                f":\n\n"
            )
            best_list.append('\n')
    if not compact or len(options) == len(best_list):
        movelink.extend(best_list)
    return "".join(movelink)


def roll_msg(update, game, player, dice):
    rerolllink = f"{ROLL} /reroll - выбрать кубики для переброса.\n\n" \
                 f"{ROLL} /qr <позиции> - для быстрого переброса.\n\n"
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
            movelink = f"{INFO} У вас не осталось перебросов и есть только " \
                       f"один допустимый ход, ваш ход завершён " \
                       f"автоматически.\n\n"
            automove = MAP_COMMANDS[next(iter(options))]
    answer(
        update,
        f"{ROLL} {player} выбросил (Переброс {rollnumber}/2):\n\n"
        f"{' '.join([d.to_emoji() for d in dice])}\n\n"
        f"{rerolllink}{movelink}{saved}"
    )
    if automove:
        process_move(update, game, player, automove, auto=True)


@chk_game_runs
def roll(update, _):
    game = get_game(update)
    player = get_player(update)
    try:
        dice = game.roll(player)
    except PlayerError as e:
        answer(update, str(e))
        return
    roll_msg(update, game, player, dice)


def reroll_msg(update, game, player, dice):
    saved = get_extra_rerolls(game, player)
    sixth = ""
    if game.maxi:
        sixth = f"{dice[5].to_emoji()} " \
                f"/6 - Выбрать 6-ой кубик.\n\n"
    rollnumber = game.reroll
    options = game.get_hand_score_options(player)
    metrics = game.get_hand_score_options(player, True)
    movelink = mk_movelink(options, metrics, compact=True)
    msg = (
        f"{ROLL} Меню переброса (Переброс {rollnumber}/2):\n\n"
        f"{dice_to_wildcard(game)}\n\n"
        f"{RESET_REROLL} /rr - Снять выбор со всех кубиков.\n\n"
        f"{dice[0].to_emoji()} /1 - Выбрать 1-ый кубик.\n\n"
        f"{dice[1].to_emoji()} /2 - Выбрать 2-ой кубик.\n\n"
        f"{dice[2].to_emoji()} /3 - Выбрать 3-ий кубик.\n\n"
        f"{dice[3].to_emoji()} /4 - Выбрать 4-ый кубик.\n\n"
        f"{dice[4].to_emoji()} /5 - Выбрать 5-ый кубик.\n\n"
        f"{sixth}{SELECT_ALL} /sa - Выбрать все кубики.\n\n"
        f"{DO_REROLL} /dr - Перебросить выбранные кубики.\n\n"
        f"{movelink}{saved}"
    )
    if game.reroll > 1:
        if not saved:  # We don't have saved Maxi Yatzy turns
            maxi_remark = ""
            if game.maxi:
                maxi_remark = " (нет сохранённых перебросов)"
            msg = (
                f"{ERROR} Вы уже перебросили кубики дважды{maxi_remark}.\n\n"
                f"Используйте команду {MOVE} /move чтобы завершить ход."
            )
    answer(update, msg)


@chk_game_runs
def reroll(update, _):
    game = get_game(update)
    player = get_player(update)
    try:
        game.chk_command_usable(player)
        if not game.hand:
            raise PlayerError(
                f"{ERROR} Невозможно перебросить кубики - вы ещё не сделали "
                f"первоначальный бросок (попробуйте {ROLL} /roll)."
            )
    except PlayerError as e:
        answer(update, str(e))
        return
    dice = game.hand
    reroll_msg(update, game, player, dice)


def send_dice(update, game):
    answer(update, dice_to_wildcard(game))


def explain_quick_reroll():
    raise PlayerError(
        f"{ERROR} Это команда быстрого переброса: она требует аргументов и "
        f"не может использоваться просто так, без них. Вы должны написать "
        f"после команды позиции кубиков для переброса.\n\n"
        f"Чтобы перебросить определённые кубики (например, первые три), "
        f"просто наберите их позиции, например:\n\n"
        f"/qr 123\n\n"
        f"Чтобы перебросить все кубики сразу, можно использовать любую из "
        f"команд ниже:\n\n/qr a\n/qr all\n/qr -\n/qr *\n\n"
        f"Если вы наоборот хотите оставить определённые кубики (например, "
        f"последние два), и перебросить все остальные - можно использовать "
        f"любую из команд ниже:"
        f"\n\n/qr !45\n/qr h45"
    )


def quick_reroll_set(game, command):
    if not command:
        explain_quick_reroll()
    allowed = f"12345{'6' if game.maxi else ''}"
    if "a" in command or "-" in command or "*" in command or "а" in command:
        command = allowed
    for digit in allowed:
        if command.count(digit) > 1:
            raise PlayerError(
                f"{ERROR} В команде быстрого переброса найдены дублирующиеся "
                f"цифры. Скорее всего, допущена опечатка. Проверьте введённую "
                f"команду и попробуйте ещё раз."
            )
    for char in command:
        if char not in allowed and char not in " \t\nh!":
            raise PlayerError(
                f"{ERROR} В команде быстрого переброса найдены недопустимые "
                f"символы. Скорее всего, допущена опечатка. Проверьте "
                f"введённую команду и попробуйте ещё раз."
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
def reroll_process(update, _):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    args = update.message.text.strip().split(None)[1:]
    game = get_game(update)
    player = get_player(update)
    try:
        game.chk_command_usable(player)
        if not game.hand:
            raise PlayerError(
                f"{ERROR} Невозможно перебросить кубики - вы ещё не сделали "
                f"первоначальный бросок (попробуйте {ROLL} /roll)."
            )
        if arg in ['1', '2', '3', '4', '5', '6']:
            # 6 only for Maxi games
            if arg == '6' and not game.maxi:
                return
            game.reroll_pool_toggle(player, arg)
            send_dice(update, game)
        elif arg == 'rr':
            game.reroll_pool_clear(player)
            send_dice(update, game)
        elif arg == 'sa':
            game.reroll_pool_select_all(player)
            send_dice(update, game)
        elif arg == 'dr' or arg == 'qr' or arg == 'q':
            if arg == 'qr' or arg == 'q':
                to_reroll = quick_reroll_set(game, "".join(args).lower())
                dice = game.reroll_dice(player, to_reroll)
                game.reroll_pool_clear(player)
            else:
                dice = game.reroll_pooled(player)
            roll_msg(update, game, player, dice)
        else:
            answer(update, f"{ERROR} Неверная команда переброса.")
    except PlayerError as e:
        answer(update, str(e))
        return


@chk_game_runs
def commit(update, _):
    game = get_game(update)
    player = get_player(update)
    try:
        options = game.get_hand_score_options(player)
    except PlayerError as e:
        answer(update, str(e))
        return
    output = []
    for option in options:
        output.append(
            f"{MOVE_BOX_ICONS[option]} /{MAP_COMMANDS[option]} "
            f"{option} - {options[option]} очков."
        )
    if game.reroll < 2 or (game.maxi and game.saved_rerolls[player]):
        output.append(f"{ROLL} /reroll - выбрать кубики для переброса.")
        output.append(f"{ROLL} /qr <позиции> - для быстрого переброса.\n\n")
    table = '\n\n'.join(output)
    answer(update, f"{MOVE} Возможные варианты хода:\n\n{table}")


def get_extra_rerolls(game, player):
    saved = ""
    if game.maxi:
        extra = game.saved_rerolls[player]
        if extra:
            saved = f"{INFO} Сохранённые перебросы: {extra} шт.\n\n"
    return saved


def current_turn_msg(update):
    game = get_game(update)
    player = get_current_player(update)
    saved = get_extra_rerolls(game, player)
    answer(
        update,
        f"{INFO} Сейчас ходит ({game.turn}/{game.get_max_turn_number()}): "
        f"<a href=\"tg://user?id={player.id}\">{player}</a>\n\n"
        f"{ROLL} /roll - бросить кубики.\n\n"
        f"{SCORE} /score - посмотреть вашу таблицу очков.\n\n"
        f"{SCORE} /score_all - посмотреть таблицы очков всех игроков.\n\n"
        f"{SCORE_ALL} /score_total - посмотреть таблицу рейтинга.\n\n"
        f"{HELP} /help - правила для этого варианта игры.\n\n" 
        f"{saved}",
        parse_mode = ParseMode.HTML
    )


def move_msg(update, saved_rerolls, player, move, points, auto=False):
    acquired_extra = ""
    if saved_rerolls:
        acquired_extra = f"{INFO} +{saved_rerolls} переброс(а) сохранено"
    answer(
        update,
        f"{SCORED} {player} делает ход {MOVE_ICONS[move]} {MAP_TURNS[move]}"
        f" за {points} очков.\n\n"
        f"{acquired_extra}",
        delay=5 if auto else 1
    )


def process_move(update, game, player, move, auto=False):
    saved_rerolls = 0
    if game.maxi:
        saved_rerolls = (2 - game.reroll)
    try:
        score_pos = game.commit_turn(player, MAP_TURNS[move])
    except (PlayerError, IllegalMoveError) as e:
        answer(update, str(e))
        return
    move_msg(update, saved_rerolls, player, move, score_pos, auto)
    scoreboard_msg(update, player)
    if gamemanager.game(update.message.chat).is_completed():
        totalscore_msg(update, finished=True)
    else:
        current_turn_msg(update)


@chk_game_runs
def commit_move(update, _):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    game = get_game(update)
    player = get_player(update)
    process_move(update, game, player, arg)


def scoreboard_msg(update, player):
    try:
        game = get_game(update)
        if player is None:
            playerlist = game.players
        else:
            playerlist = [player]
        for plr in playerlist:
            scores = game.scores_player(plr)
            answer(
                update,
                f"{SCORE} Таблица очков для {plr}:\n\n`{scores}`",
                parse_mode=ParseMode.MARKDOWN
            )
    except PlayerError as e:
        answer(update, str(e))


@chk_game_runs
def score(update, _):
    arg = update.message.text.strip()[1:].split(None)[0].split("@")[0]
    requestor = get_player(update)
    if arg == "score":
        player = requestor
    else:
        player = None
    try:
        get_game(update).chk_command_usable_any_turn(requestor)
    except PlayerError as e:
        answer(update, str(e))
        return
    scoreboard_msg(update, player)


def totalscore_msg(update, finished=False):
    player = get_player(update)
    emoji = SCORE_ALL
    msg = "Текущий рейтинг"
    if finished:
        emoji = CONGRATS
        msg = "Игра окончена! Финальный счёт"
        logger.info(
            f"Игра окончена - chat_id {update.message.chat.id}"
        )
    try:
        scores = get_game(update).scores_final(player)
    except PlayerError as e:
        answer(update, str(e))
        return
    answer(update, f"{emoji} {msg}:\n\n{scores}")


def score_messages(update, player, finished):
    scoreboard_msg(update, player)
    totalscore_msg(update, finished)


@chk_game_runs
def score_all(update, _):
    try:
        player = get_player(update)
        get_game(update).chk_command_usable_any_turn(player)
    except PlayerError as e:
        answer(update, str(e))
        return
    totalscore_msg(update)


def bot_help(update, _):
    logger.info("Вызвана справка")
    game = get_game(update)
    chat = update.message.chat
    if not gamemanager.is_game_created(chat) or game.finished:
        answer(
            update,
            f"{HELP} Используйте команду {START} /start чтобы начать работу "
            f"с ботом и следуйте инструкциям. Вы можете почитать об играх "
            f"Яхтзи и Йетзи (покере на костях) тут:\n"
            f"https://ru.wikipedia.org/wiki/Покер_на_костях\n\n"
            f"Или в англоязычных статьях:\n"
            f"https://en.wikipedia.org/wiki/Yatzy\n"
            f"https://en.wikipedia.org/wiki/Yahtzee\n\n"
            f"Используйте команду {HELP} /help после начала игры, чтобы "
            f"почитать правила текущего варианта игры."
        )
    else:
        avg_dice = 3 + (1 if game.maxi else 0) - (1 if game.forced else 0)
        avg_dice_words = {2: "два", 3: "три", 4: "четыре"}
        msg = [f"{HELP} Правила для игры {game.get_name()}.\n"]
        if game.forced:
            msg.append(f"{INFO} Правило последовательных ходов: В этом "
                       f"варианте вы должны делать ходы точно в том же "
                       f"порядке, в котором они указаны в таблице очков, т.е. "
                       f"начиная с Единиц, потом Двойки и так далее. "
                       f"Поскольку это добавляет сложности, требование по "
                       f"количеству очков для получения бонуса верхней секции "
                       f"уменьшено до "
                       f"{game.get_upper_section_bonus_score()} очков.\n")
        dice_count = "шесть" if game.maxi else "пять"
        rolls_remark = ""
        if game.maxi:
            rolls_remark = " (не считая сохранённых перебросов)"
        rounds = "пятнадцати"
        if game.yahtzee:
            rounds = "тринадцати"
        elif game.maxi:
            rounds = "двадцати"
        msg.append(f"{RULES} Цель игры состоит в том, чтобы набирать очки, "
                   f"бросая {dice_count} кубиков и собирая из них разные "
                   f"комбинации. Кубики можно бросать до трёх раз за "
                   f"ход{rolls_remark} чтобы попытаться составить различные "
                   f"комбинации, дающие очки. После первого броска, игрок "
                   f"может оставить любые кубики и перебросить все остальные. "
                   f"Игра состоит из {rounds} раундов. После каждого раунда, "
                   f"игрок должен выбрать категорию таблицы очков, которая "
                   f"будет использована для этого раунда (даже если она даст "
                   f"ноль очков). После того, как категория была "
                   f"использована, она не может быть использована повторно. "
                   f"Разные категории дают разное количество очков. Некоторые "
                   f"дают фиксированное количество очков, а другие зависят от "
                   f"значений на кубиках. Игрок, набравший наибольшее "
                   f"количество очков становится победителем в игре. Ниже "
                   f"приведены описания категорий таблицы очков.\n")
        msg.append(f"{UPPER} Верхняя секция:\n")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['ac']} Тузы: Любая комбинация. "
                       f"Количество очков равно сумме кубиков с цифрой 1.")
        else:
            msg.append(f"{MOVE_ICONS['on']} Единицы: Любая комбинация. "
                       f"Количество очков равно сумме кубиков с цифрой 1.")
        msg.append(f"{MOVE_ICONS['tw']} Двойки: Любая комбинация. "
                   f"Количество очков равно сумме кубиков с цифрой 2.")
        msg.append(f"{MOVE_ICONS['th']} Тройки: Любая комбинация. "
                   f"Количество очков равно сумме кубиков с цифрой 3.")
        msg.append(f"{MOVE_ICONS['fo']} Четвёрки: Любая комбинация. "
                   f"Количество очков равно сумме кубиков с цифрой 4.")
        msg.append(f"{MOVE_ICONS['fi']} Пятёрки: Любая комбинация. "
                   f"Количество очков равно сумме кубиков с цифрой 5.")
        msg.append(f"{MOVE_ICONS['si']} Шестёрки: Любая комбинация. "
                   f"Количество очков равно сумме кубиков с цифрой 6.\n")
        msg.append(f"{SCORED} Бонус верхней секции: Если вы наберёте хотя бы "
                   f"{game.get_upper_section_bonus_score()} очков "
                   f"(в среднем {avg_dice_words[avg_dice]} кубика в каждой "
                   f"категории) в верхней секции, вы получите бонус в "
                   f"{game.get_upper_section_bonus_value()} очков.\n")
        msg.append(f"{LOWER} Нижняя секция:\n")
        if not game.yahtzee:
            msg.append(f"{MOVE_ICONS['op']} Одна Пара: Два кубика с "
                       f"одинаковой цифрой (если есть несколько пар - "
                       f"считается наибольшая). Количество очков равно сумме "
                       f"этих двух кубиков.")
            if game.maxi:
                maxi_pair_remark = " (если есть три пары - считаются две " \
                                   "наибольшие)"
            else:
                maxi_pair_remark = ""
            msg.append(f"{MOVE_ICONS['tp']} Две Пары: Две разные пары "
                       f"кубиков{maxi_pair_remark}. Количество очков равно "
                       f"сумме кубиков в этих двух парах.")
            if game.maxi:
                msg.append(f"{MOVE_ICONS['3p']} Три Пары: Три разные пары "
                           f"кубиков. Количество очков равно сумме всех "
                           f"кубиков.")
        maxi_tk_remark = ""
        if game.maxi:
            maxi_tk_remark = " (если есть две группы по 3 Одинаковых, " \
                               "считается наибольшая)"
        msg.append(
            f"{MOVE_ICONS['tk']} 3 Одинаковых: Три кубика с одинаковой "
            f"цифрой{maxi_tk_remark}. Количество очков равно сумме "
            f"{'всех кубиков' if game.yahtzee else 'этих трёх кубиков'}."
        )
        msg.append(
            f"{MOVE_ICONS['fk']} 4 Одинаковых: Четыре кубика с одинаковой "
            f"цифрой. Количество очков равно сумме "
            f"{'всех кубиков' if game.yahtzee else 'этих четырёх кубиков'}."
        )
        if game.maxi:
            msg.append(f"{MOVE_ICONS['5k']} 5 Одинаковых: Пять кубиков с "
                       f"одинаковой цифрой. Количество очков равно сумме этих "
                       f"пяти кубиков.")
        fh_points = 'сумма всех кубиков'
        if game.yahtzee:
            fh_points = '25'
        elif game.maxi:
            fh_points = 'сумма этих пяти кубиков'
        msg.append(f"{MOVE_ICONS['fh']} Фулл Хаус: Комбинация из трёх кубиков "
                   f"с одной цифрой и пары кубиков с другой цифрой. "
                   f"Количество очков - {fh_points}.")
        if game.maxi:
            msg.append(f"{MOVE_ICONS['ca']} Замок: Два разных комплекта из "
                       f"трёх одинаковых кубиков. Количество очков равно "
                       f"сумме всех кубиков.")
            msg.append(f"{MOVE_ICONS['to']} Башня: Комбинация из четырёх "
                       f"кубиков с одной цифрой и пары кубиков с другой "
                       f"цифрой. Количество очков равно сумме всех кубиков.")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['ss']} Малый Стрит: Любые четыре кубика, "
                       f"идущие подряд (т.е. 1-2-3-4, 2-3-4-5 или 3-4-5-6). "
                       f"Количество очков - 30.")
            msg.append(f"{MOVE_ICONS['ls']} Большой Стрит: Любые пять "
                       f"кубиков, идущие подряд (т.е. 1-2-3-4-5 или "
                       f"2-3-4-5-6). Количество очков - 40.")
        else:
            st_points = 'сумма всех кубиков'
            if game.maxi:
                st_points = 'сумма этих пяти кубиков'
            msg.append(f"{MOVE_ICONS['ss']} Малый Стрит: Комбинация "
                       f"1-2-3-4-5. Количество очков - 15 ({st_points}).")
            msg.append(f"{MOVE_ICONS['ls']} Большой Стрит: Комбинация "
                       f"2-3-4-5-6. Количество очков - 20 ({st_points}).")
            if game.maxi:
                msg.append(f"{MOVE_ICONS['fs']} Полный Стрит: Комбинация "
                           f"1-2-3-4-5-6. Количество очков - 21 (сумма всех "
                           f"кубиков).")
        msg.append(f"{MOVE_ICONS['ch']} Шанс: Любая комбинация. Количество "
                   f"очков равно сумме всех кубиков.")
        if game.yahtzee:
            msg.append(f"{MOVE_ICONS['yh']} Яхтзи: Одинаковая цифра на всех "
                       f"пяти кубиках. Количество очков - 50.\n")
        else:
            if game.maxi:
                msg.append(f"{MOVE_ICONS['my']} Макси Йетзи: Одинаковая цифра "
                           f"на всех шести кубиках. Количество очков - 100.\n")
            else:
                msg.append(f"{MOVE_ICONS['ya']} Йетзи: Одинаковая цифра на "
                           f"всех пяти кубиках. Количество очков - 50.\n")
        if game.maxi:
            msg.append(f"{INFO} Механика сохранения перебросов: Вы можете "
                       f"сохранять неиспользованные перебросы (например, если "
                       f"вы сделаете ход после первоначального броска или "
                       f"первого переброса) и использовать их в последующие "
                       f"ходы.\n")
        if game.yahtzee:
            msg.append(f"{SCORED} Бонус Яхтзи: Если вы соберёте более одного "
                       f"Яхтзи за игру и уже заполнили категорию Яхтзи на 50 "
                       f"очков - вы получаете дополнительный бонус в 100 "
                       f"очков за второй и все последующие Яхтзи.\n")
            msg.append(f"{JOKER} Правило Джокера: Если вы получили Бонус "
                       f"Яхтзи, вы можете использовать вашу комбинацию как "
                       f"Джокер по следующим правилам:\n\n{MOVE_ICONS['ac']} "
                       f"Если соответствующая категория Верхней Секции "
                       f"свободна - вы должны использовать её.\n"
                       f"{MOVE_ICONS['tw']} Если соответствующая категория "
                       f"Верхней Секции уже использована, вы должны "
                       f"использовать любую категорию Нижней Секции. Яхтзи "
                       f"работает как Джокер, так что Фулл Хаус, Малый Стрит "
                       f"и Большой Стрит могут быть использованы, чтобы "
                       f"получить 25, 30 или 40 очков (соответственно), "
                       f"несмотря на то, что кубики не соответствуют обычным "
                       f"требованиям для этих категорий.\n{MOVE_ICONS['th']} "
                       f"Если соответствующая категория Верхней Секции и все "
                       f"категории Нижней Секции уже использованы, любая "
                       f"свободная категория Верхней Секции должна быть "
                       f"использована. В таком случае вы получаете 0 очков за "
                       f"комбинацию.\n")
        answer(
            update,
            "\n".join(msg)
        )


def error(update, context):
    """Log Errors caused by Updates."""
    logger.error('Событие "%s" вызвало ошибку "%s"', update, context.error)


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

    @auto_group
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
    updater.dispatcher.add_handler(CommandHandler('kick', kick))
    updater.dispatcher.add_handler(CommandHandler('roll', roll))
    updater.dispatcher.add_handler(CommandHandler('reroll', reroll))
    updater.dispatcher.add_handler(CommandHandler('help', bot_help))
    updater.dispatcher.add_handler(CommandHandler('move', commit))
    updater.dispatcher.add_handler(CommandHandler('score_total', score_all))
    updater.dispatcher.add_handler(
        CommandHandler(['score', 'score_all'], score)
    )
    updater.dispatcher.add_handler(
        CommandHandler(
            ['1', '2', '3', '4', '5', '6', 'dr', 'rr', 'sa', 'qr', 'q'],
            reroll_process
        )
    )
    updater.dispatcher.add_handler(
        CommandHandler(
            ['on', 'ac', 'tw', 'th', 'fo', 'fi',
             'si', 'op', 'tp', '3p', 'tk', 'fk',
             '5k', 'fh', 'ca', 'to', 'ss', 'ls',
             'fs', 'ch', 'ya', 'yh', 'my'],
            commit_move
        )
    )
    updater.dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Get the job queue
    answer_timer['queue'] = updater.job_queue
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    logger.info("YatzyBot запущен.")
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

    logger.info("Завершаем работу бота...")
    yatzybot.__del__()  # Force thread stop to allow process termination.


if __name__ == '__main__':
    main()
