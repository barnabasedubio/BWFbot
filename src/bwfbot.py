import os
import json
import datetime
import telebot
import ssl

from telebot import apihelper
from firebase_admin import credentials, initialize_app
from markups import *
from database import *
from redis_client import *
from utils import *
from uuid import uuid4
from aiohttp import web


# configuration
with open("../config.yml", "r") as fp:
    config = yaml.load(fp, yaml.FullLoader)
    API_TOKEN = config.get("telegram").get("api_token")


CRED = credentials.Certificate("../firebase_service_account_key.json")  # keep json secret at all times!
initialize_app(CRED, {"databaseURL": config.get("firebase").get("reference")})

apihelper.ENABLE_MIDDLEWARE = True

""" local development:
WEBHOOK_HOST = "cfa34f1a1d55.ngrok.io"
WEBHOOK_LISTEN = '0.0.0.0'
WEBHOOK_PORT = 8443
WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}/"
WEBHOOK_URL_PATH = f"{API_TOKEN}/"
"""

""" remote deploy (DigitalOcean)
"""
WEBHOOK_HOST = "164.90.172.233"
WEBHOOK_LISTEN = '0.0.0.0'
WEBHOOK_PORT = 8443
WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}:{WEBHOOK_PORT}/"
WEBHOOK_URL_PATH = f"{API_TOKEN}/"

WEBHOOK_SSL_CERT = '../ssl/webhook_cert.pem'
WEBHOOK_SSL_PRIV = '../ssl/webhook_pkey.pem'


BOT = telebot.TeleBot(API_TOKEN)
APP = web.Application()

"""
global variables stored in REDIS:
session:
    MESSAGE
    CHAT_ID
    SENT_MESSAGES
    USER
input state:
    WAITING_FOR_INPUT
    WAITING_FOR_WORKOUT_TITLE
    WAITING_FOR_EXERCISE_NAME
    WAITING_FOR_EXERCISE_VIDEO_LINK
    WAITING_FOR_MUSCLES_WORKED
    WAITING_FOR_REP_COUNT
    WAITING_FOR_USER_FEEDBACK
    RESET_STATE
workout-related data:
    WORKOUT
    WORKOUT_INDEX
    PAST_WORKOUT_DATA
exercise-related data:
    CURRENT_EXERCISE_INDEX
    CUSTOM_EXERCISE
    CATALOGUE_EXERCISE
    MOST_RECENTLY_ADDED_EXERCISE
    EXERCISE_PATH
"""


def confirm_reset_state(user_id):
    send_message(
        user_id,
        "Performing this action will cancel the running workout. Are you sure you want to continue?",
        reply_markup=reset_state_answer_markup()
    )


def reset_state(user_id):

    delete_from_redis(
        user_id,
        "WAITING_FOR_INPUT",
        "WAITING_FOR_WORKOUT_TITLE",
        "WAITING_FOR_EXERCISE_NAME",
        "WAITING_FOR_EXERCISE_VIDEO_LINK",
        "WAITING_FOR_MUSCLES_WORKED",
        "WAITING_FOR_REP_COUNT",
        "WAITING_FOR_USER_FEEDBACK",
        "WORKOUT",
        "WORKOUT_INDEX",
        "PAST_WORKOUT_DATA",
        "CUSTOM_EXERCISE",
        "CATALOGUE_EXERCISE",
        "MOST_RECENTLY_ADDED_EXERCISE",
        "EXERCISE_PATH",
        "RESET_STATE",
        "CURRENT_EXERCISE_INDEX",
        "PUBLISH_WORKOUT_ID",
        "RECOMMENDED_ROUTINE",
    )


# ------------- PROCESS WEBHOOK CALLS ----------------

async def handle(request):
    print(request)
    if request.match_info.get("token") == BOT.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)

        if update.message:
            print(update.update_id, update.message.from_user.id, update.message.text)
            # TODO: ignore updates with the same update id

        elif update.callback_query:
            print(update.update_id, update.callback_query.from_user.id, "callback")
            # TODO: ignore updates with the same update id

        BOT.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

APP.router.add_post("/{token}/", handle)


# ----------------- HANDLERS --------------------

@BOT.middleware_handler(update_types=["message"])
def set_user_id(bot_instance, message):
    user_id = str(message.from_user.id)
    # if the new message shares the same timestamp as the one currently saved in redis, it means that telegram
    # sent a batch of messages at once because the user had no internet when they sent them.
    # in that case, only handle the first of these messages, and ignore the rest.
    # however, if the message is numeric, it is most likely a rep count, in which case we want to handle them all the time.
    if message.text and not message.text.isnumeric():
        if get_from_redis(user_id, "LAST_MESSAGE_TIMESTAMP") and get_from_redis(user_id, "LAST_MESSAGE_TIMESTAMP") == message.date:
            message.text = ""
        else:
            set_to_redis(user_id, "LAST_MESSAGE_TIMESTAMP", message.date)

    elif message.text is None:
        message.text = ""


def show_maintenance_info(user_id):
    send_message(
        user_id,
        "Hey I'm currently fixing some internal issues. Would you mind coming back a bit later? Thanks a lot 😊")


@BOT.message_handler(commands=["start, begin, create, delete, view, stats, publish, export"])
def commands_handler(message):
    show_maintenance_info(message.from_user.id)


@BOT.message_handler(func=lambda message: message.text)
def input_handler(message):
    show_maintenance_info(message.from_user.id)


@BOT.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """
    handles all inline keyboard responses
    :param call
    """

    user_id = str(call.from_user.id)

    # if the new callback data is the same as the one stored in redis (and the time is similar),
    # it means that the user sent consecutive
    # callbacks for the same inline response while having no internet, and telegram sent all at once upon
    # reconnection. Since the time is too close for them to be distinct, ignore all but the first callback
    if get_from_redis(user_id, "LAST_CALLBACK_DATA") \
            and get_from_redis(user_id, "LAST_CALLBACK_DATA") == call.data\
            and get_from_redis(user_id, "LAST_CALLBACK_DATA_TIMESTAMP") > int(time.time() - 2):
        return
    else:
        set_to_redis(user_id, "LAST_CALLBACK_DATA", call.data)
        set_to_redis(user_id, "LAST_CALLBACK_DATA_TIMESTAMP", int(time.time()))

    # ---------------------------------------------------------------------------------------------------

    if call.data not in ("add_catalogue_exercise", "ADD_RECOMMENDED_ROUTINE") \
            and "CONFIRM_DELETE_WORKOUT:" not in call.data:
        BOT.answer_callback_query(callback_query_id=call.id)  # remove loading spinner

    if call.data == "choose_workouts":
        choose_workout(user_id, call=call)

    elif call.data == "exercise_menu:choose_workouts":
        # user had the option to add another exercise, start workout, or go to the main menu.
        # clicking start workout should show the saved workout list, but the back button should not go
        # to the main menu (per usual), but back to to add another exercise option
        choose_workout(user_id, call=call, comes_from="add_another_exercise")

    elif call.data == "create_workout":
        get_workout_title_from_input(user_id, call)

    elif call.data == "add_exercise":
        add_custom_exercise(user_id, call=call)

    elif call.data == "add_catalogue_exercise":
        catalogue_exercise = get_from_redis(user_id, "CATALOGUE_EXERCISE")
        add_catalogue_exercise(call, catalogue_exercise)

    elif call.data == "ASK_TO_SHOW_RECOMMENDED_ROUTINES":
        ask_to_show_recommended_routines(call)

    elif call.data.endswith("START_MENU"):
        show_start_options(user_id, call=call)

    elif call.data == "exercise_added":
        exercise_added(user_id=user_id, call=call)

    elif call.data == "list_workouts_for_workout_details":
        handle_view_workout(user_id, call=call)

    elif call.data == "show_exercise_stats":
        show_exercise_stats(call)

    elif call.data == "choose_exercise_from_catalogue":
        choose_exercise_from_catalogue(call)

    elif call.data == "show_add_exercise_options":
        add_exercise_options(call)

    elif call.data.startswith("choose_exercise_from_catalogue:"):
        call.data = call.data.replace("choose_exercise_from_catalogue:", "")
        if call.data == "go_back":
            if get_from_redis(user_id, "EXERCISE_PATH"):
                pop_from_redis(user_id, "EXERCISE_PATH", "right")
            else:
                # user already was in root level (movement groups) when they clicked go back
                add_exercise_options(call)
                return
        else:
            push_to_redis(user_id, "EXERCISE_PATH", call.data)
        choose_exercise_from_catalogue(call, get_from_redis(user_id, "EXERCISE_PATH"))

    elif call.data.startswith("START_WORKOUT:"):
        workout_id = call.data.replace("START_WORKOUT:", "")
        temp_workout = {}
        counter = 0
        # get workout data from users saved workouts
        user = get_from_redis(user_id, "USER")
        for node_id in user.get('saved_workouts'):
            if user.get('saved_workouts').get(node_id).get('id') == workout_id:
                temp_workout = user.get('saved_workouts').get(node_id)
                break
            counter += 1
        set_to_redis(user_id, "WORKOUT_INDEX", counter)

        if user.get('completed_workouts'):
            # get previous workout data from user's completed workouts that use the saved workout as a template
            past_workout_data = {node: workout
                                 for (node, workout) in user.get('completed_workouts').items()
                                 if user.get('completed_workouts').get(node).get('template_id') == workout_id}
            set_to_redis(user_id, "PAST_WORKOUT_DATA", past_workout_data)

        if temp_workout.get('exercises'):
            send_edited_message(user_id, "Let's go! 💪", call.message.id)
            do_workout(user_id, workout_id=workout_id)
        else:
            send_edited_message(
                user_id,
                f"*{prepare_for_markdown_v2(temp_workout.get('title'))}* has no exercises\\. Do you want to add some?",
                call.message.id,
                reply_markup=add_exercise_markup(comes_from="start_menu"),
                parse_mode="MarkdownV2"
            )

    elif call.data.startswith("DELETE_WORKOUT:"):
        workout_id = call.data.replace("DELETE_WORKOUT:", "")
        delete_workout(call=call, workout_id=workout_id)

    elif call.data.startswith("CONFIRM_DELETE_WORKOUT:"):
        user = get_from_redis(user_id, "USER")
        workout_id = call.data.replace("CONFIRM_DELETE_WORKOUT:", "")
        workout = get_saved_workout_from_database(user.get("id"), workout_id)
        workout_key = list(workout.keys())[0]
        workout_title = workout.get(workout_key).get("title")

        user = delete_saved_workout_from_database(user.get("id"), workout_key)
        set_to_redis(user_id, "USER", user)
        BOT.answer_callback_query(callback_query_id=call.id)
        send_edited_message(
            user_id,
            f"Done\\! *{prepare_for_markdown_v2(workout_title)}* is gone from your saved workouts\\.",
            call.message.id,
            parse_mode="MarkdownV2"
        )

    elif call.data.startswith("ABORT_DELETE_WORKOUT:"):
        workout_id = call.data.replace("ABORT_DELETE_WORKOUT:", "")
        workout = get_saved_workout_from_user(user_id, workout_id)
        workout_title = prepare_for_markdown_v2(workout.get('title'))
        send_edited_message(user_id, f"Gotcha\\! Will not delete *{workout_title}*\\.", call.message.id, parse_mode="MarkdownV2")

    elif call.data.startswith("VIEW_WORKOUT:"):
        workout_id = call.data.replace("VIEW_WORKOUT:", "")
        workout = get_saved_workout_from_user(user_id, workout_id)
        show_saved_workout_details(call, workout)

    elif call.data.startswith("PUBLISH_WORKOUT:"):
        workout_id = call.data.replace("PUBLISH_WORKOUT:", "")
        publish_workout(call, workout_id, False)

    elif call.data.startswith("CONFIRM_PUBLISH_WORKOUT:"):
        workout_id = call.data.replace("CONFIRM_PUBLISH_WORKOUT:", "")
        publish_workout(call, workout_id, True)

    elif call.data.startswith("ABORT_PUBLISH_WORKOUT:"):
        workout_id = call.data.replace("ABORT_PUBLISH_WORKOUT:", "")
        workout = get_saved_workout_from_user(user_id, workout_id)
        workout_title = prepare_for_markdown_v2(workout.get('title'))
        send_edited_message(
            user_id,
            f"Alright, I'll not publish *{workout_title}*\\.",
            call.message.id,
            parse_mode="MarkdownV2"
        )

    elif call.data == "VIEW_RECOMMENDED_ROUTINES":
        view_recommended_routines(call)

    elif call.data.startswith("RECOMMENDED_ROUTINE:"):
        difficulty_level = call.data.replace("RECOMMENDED_ROUTINE:", "")
        view_recommended_routines(call, difficulty_level)

    elif call.data == "ADD_RECOMMENDED_ROUTINE":
        recommended_routine = get_from_redis(user_id, "RECOMMENDED_ROUTINE")
        add_recommended_routine(call, recommended_routine)

    elif call.data.startswith("RESET_STATE:"):
        answer = call.data.replace("RESET_STATE:", "")
        reset_state_flag = True if answer == "YES" else False
        if reset_state_flag:
            set_to_redis(user_id, "RESET_STATE", True)
            send_edited_message(
                user_id,
                "Done! The running workout has been cancelled.",
                call.message.id)
            send_message(user_id, "Please resend your command.", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            send_edited_message(user_id, "Okay, I'll not cancel the running workout.", call.message.id)
            delete_from_redis(user_id, "RESET_STATE")


# handle /start command
@BOT.message_handler(commands=["start"])
def initialize(message):

    user_id = str(message.from_user.id)

    set_to_redis(user_id, "CHAT_ID", str(message.chat.id))

    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)

    user = get_from_redis(user_id, "USER")
    if bool(user):
        show_start_options(user_id)

    else:
        user = get_user_from_database(user_id)
        set_to_redis(user_id, "USER", user)
        if not user:
            # new user
            new_user = add_user_to_database(
                user_id,
                message.from_user.first_name,
                message.from_user.last_name,
                message.from_user.username)
            set_to_redis(user_id, "USER", new_user)

        show_start_options(user_id)


@BOT.message_handler(commands=["begin"])
def begin_workout(message):

    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    reset_state(user_id)
    choose_workout(user_id)


@BOT.message_handler(commands=["create"])
def create_workout(message):

    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    reset_state(user_id)

    get_workout_title_from_input(user_id)


# handle /next command
@BOT.message_handler(commands=["next"])
def proceed_to_next(message):
    """
    advances the chat conversation based on context
    the context is derived from the global variables
    since only one of them can be true at a time (in addition to WAITING_FOR_USER_INPUT), the chat flow
    can be handled fairly straightforwardly
    :param message
    """
    user_id = str(message.from_user.id)

    if get_from_redis(user_id, "WAITING_FOR_EXERCISE_VIDEO_LINK"):
        # user skipped the video link entry
        add_custom_exercise(user_id, message=message, message_type="EXERCISE_VIDEO_LINK", skip_setting=True)

    elif get_from_redis(user_id, "WAITING_FOR_MUSCLES_WORKED"):
        # user skipped the muscles worked entry
        add_custom_exercise(user_id, message=message, message_type="EXERCISE_MUSCLES_WORKED", skip_setting=True)

    elif get_from_redis(user_id, "WAITING_FOR_REP_COUNT") and \
            get_from_redis(user_id, "CURRENT_EXERCISE_INDEX") != len(get_from_redis(user_id, "WORKOUT").get('exercises')) - 1:
        # display the next exercise in the workout to the user
        # if the user is on their last exercise, this logic is handled by the /finish handler instead
        increment_in_redis(user_id, "CURRENT_EXERCISE_INDEX")
        do_workout(user_id)


# handle /previous command
@BOT.message_handler(commands=["previous"])
def return_to_previous(message):
    user_id = str(message.from_user.id)
    if get_from_redis(user_id, "WAITING_FOR_REP_COUNT") and get_from_redis(user_id, "CURRENT_EXERCISE_INDEX") > 0:
        decrement_in_redis(user_id, "CURRENT_EXERCISE_INDEX")
        do_workout(user_id)


# handle /finish command
@BOT.message_handler(commands=["finish"])
def finish(message):
    user_id = str(message.from_user.id)
    workout = get_from_redis(user_id, "WORKOUT")
    if get_from_redis(user_id, "WAITING_FOR_REP_COUNT") and \
            get_from_redis(user_id, "CURRENT_EXERCISE_INDEX") == len(workout.get('exercises')) - 1:
        # user is done with their workout. End workout and add it to their completed workouts
        workout['duration'] = int(time.time()) - workout.get('started_at')
        workout['running'] = False

        set_to_redis(user_id, "WORKOUT", workout)
        user = get_from_redis(user_id, "USER")
        user = add_completed_workout_to_database(user.get("id"), workout)
        set_to_redis(user_id, "USER", user)

        delete_from_redis(user_id, "WAITING_FOR_INPUT", "WAITING_FOR_REP_COUNT", "CURRENT_EXERCISE_INDEX")
        workout_completed(user_id)


@BOT.message_handler(commands=["delete"])
def handle_delete_workout(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    reset_state(user_id)
    user = get_from_redis(user_id, "USER")
    if user.get('saved_workouts'):
        message_text = \
            "*Delete workout*\n\nWhich workout would you like to delete?\n\n" \
            "*Note:* this doesn't affect your already completed workouts\\."

        send_message(
            user_id,
            message_text,
            reply_markup=delete_workout_markup(user.get('saved_workouts')),
            parse_mode="MarkdownV2")
    else:
        send_message(user_id, "You don't have any stored workouts.")


@BOT.message_handler(commands=["view"])
def view_workout(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)

    handle_view_workout(user_id)


@BOT.message_handler(commands=["feedback"])
def user_feedback(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)
    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)

    # check if user has sent feedback in the last 5 minutes
    user = get_from_redis(user_id, "USER")
    if user.get("sent_last_feedback_at") and \
            user.get("sent_last_feedback_at") > int(time.time()) - 300:
        send_message(
            user_id,
            "Would you mind waiting a few minutes before posting more feedback? Thanks a lot 😄"
        )
    else:
        handle_user_feedback(user_id)


@BOT.message_handler(commands=["stats", "publish"])
def feature_in_progress(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)

    send_message(
        user_id,
        "🚧 Please be patient, I am currently still working on this feature."
        "\n\nIn the meantime, please send me some /feedback as to what you would like to see once it's done!")

    increment_in_redis("0000", f"{message.text[1:].upper()}_REQUESTED")


@BOT.message_handler(commands=["export"])
def handle_export(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)
    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)
    # check if user has exported data in the last 24 hours
    user = get_from_redis(user_id, "USER")
    if user.get("exported_last_workout_data_at") and \
            user.get("exported_last_workout_data_at") > int(time.time()) - 86400:
        send_message(
            user_id,
            "You have already exported your data once in the last 24 hours. "
            "Please wait a bit before exporting again."
        )
    else:
        export(message)


# implement once you have users that are actually interested in this
@BOT.message_handler(commands=["publish"])
def handle_publish_workout(message):
    user_id = str(message.from_user.id)
    remove_inline_replies(user_id)

    workout = get_from_redis(user_id, "WORKOUT")
    if workout and workout.get('running') and not get_from_redis(user_id, "RESET_STATE"):
        confirm_reset_state(user_id)
        return

    # reset application state for every new session
    reset_state(user_id)

    user = get_from_redis(user_id, "USER")
    if user.get('saved_workouts'):
        # if any one of users saved workouts has been published in the last 24 hours send error message
        if user.get("published_last_workout_at") and user.get("published_last_workout_at") > int(time.time()) - 2:
            send_message(user_id, "You have already published a workout in the last 24 hours. "
                         "Please wait a bit before publishing another one.")
        else:
            send_message(
                user_id,
                "*Publish workout*\n\nWhich of your workouts would you like to share with the community?",
                reply_markup=publish_workout_markup(user.get('saved_workouts')), parse_mode="MarkdownV2")
    else:
        send_message(user_id, "You don't have any stored workouts. Please create one first before publishing.")


# only if bot is expecting user input
# needs to be the very last handler!!
@BOT.message_handler(func=lambda message: message.text)
def handle_user_input(message):
    """
    handles actual user input written to chat.
    similar to func proceed_to_next(), the context is derived from the global variables
    :param message
    """
    user_id = str(message.from_user.id)
    # only handle if the bot is also waiting for user input
    if get_from_redis(user_id, "WAITING_FOR_INPUT"):
        # create workout
        if get_from_redis(user_id, "WAITING_FOR_WORKOUT_TITLE"):
            get_workout_title_from_input(message.from_user.id, message=message)
        # create exercise
        elif get_from_redis(user_id, "WAITING_FOR_EXERCISE_NAME"):
            add_custom_exercise(user_id, message=message, message_type="EXERCISE_NAME")
        elif get_from_redis(user_id, "WAITING_FOR_EXERCISE_VIDEO_LINK"):
            add_custom_exercise(user_id, message=message, message_type="EXERCISE_VIDEO_LINK")
        elif get_from_redis(user_id, "WAITING_FOR_MUSCLES_WORKED"):
            add_custom_exercise(user_id, message=message, message_type="EXERCISE_MUSCLES_WORKED")
        # add reps to exercise
        elif get_from_redis(user_id, "WAITING_FOR_REP_COUNT"):
            if message.text.isnumeric():
                do_workout(user_id, new_rep_entry=True, message=message)
        elif get_from_redis(user_id, "WAITING_FOR_USER_FEEDBACK"):
            handle_user_feedback(message)


# ----------------- FUNCTIONS ------------------

def show_start_options(user_id, call=None):
    if call:
        message_text = \
            "What can I help you with?\n\n" \
            "Type '/' to see all commands you can give me."
        send_edited_message(user_id, message_text, call.message.id, reply_markup=start_options_markup())
    else:
        username = get_from_redis(user_id, "USER").get("first_name")
        message_text = f'''
                Hey, {username}! What would you like to do today?
                \nType '/' to see all commands you can give me.'''

        send_message(user_id, message_text.strip(), reply_markup=start_options_markup())


def send_message(user_id, message_text, reply_markup=None, parse_mode=""):
    print("sending message")
    global BOT

    chat_id = get_from_redis(user_id, "CHAT_ID")
    sent_message = BOT.send_message(
        chat_id,
        message_text,
        reply_markup=reply_markup, disable_web_page_preview=True,
        parse_mode=parse_mode)

    push_to_redis(user_id, "SENT_MESSAGES", jsonpickle.dumps(sent_message))
    print("sent message")


def send_edited_message(user_id, message_text, previous_message_id, reply_markup=None, parse_mode=""):
    global BOT
    print("sending edited message")
    message_to_edit = None
    message_index = None
    chat_id = get_from_redis(user_id, "CHAT_ID")

    messages = \
        [jsonpickle.loads(x) for x in get_from_redis(user_id, "SENT_MESSAGES")] \
        if exists_in_redis(user_id, "SENT_MESSAGES") \
        else []

    for ix, message in enumerate(messages):
        if message.id == previous_message_id:
            message_to_edit = message
            message_index = ix
            break

    new_message = BOT.edit_message_text(
        message_text,
        chat_id,
        message_to_edit.id,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode=parse_mode)

    if not new_message:
        send_message(user_id, "Whoops I think I messed up 🙈. You can reset me by clearing the history and pressing start again."
                     "(Don't worry. All your data is still safe 😉)")
        print("sent error message")
        delete_from_redis(user_id, "SENT_MESSAGES")

    else:
        set_list_index_to_redis(user_id, "SENT_MESSAGES", message_index, jsonpickle.dumps(new_message))
        print("sent edited message")
        return new_message


def choose_workout(user_id, call=None, comes_from=None):

    user = get_from_redis(user_id, "USER")
    if user.get('saved_workouts'):
        message_text = \
            "*Start workout*\n\nWhich workout routine would you like to start?\n\n" \
            "If you want to view the exercises in each workout, click /view\\."

        if comes_from == "add_another_exercise":
            reply_markup = list_workouts_markup(user.get('saved_workouts'), comes_from="add_another_exercise")
        else:
            reply_markup = list_workouts_markup(user.get('saved_workouts'))

        if call:
            send_edited_message(
                user_id,
                message_text,
                call.message.id,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2")
        else:
            send_message(
                user_id,
                message_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2")
    else:
        if call:
            message_text = "You don't have any stored workouts. Would you like to create a new one?"
            send_edited_message(
                user_id,
                message_text,
                call.message.id,
                reply_markup=create_workout_answer_markup())
        else:
            # if the user wants to start a working by sending /begin command
            message_text = "You don't have any stored workouts. Would you like to create a new one?"
            send_message(
                user_id,
                message_text,
                reply_markup=create_workout_answer_markup())


def get_workout_title_from_input(user_id, call=None, message=None):
    """
    This function gets called twice. Once upon creating a new workout, and once after the
    user has typed in the workout name. The initial call has no message value, thus the first
    condition gets executed. After user input has been handled by handle_workout_title()
    and this function gets called again, it enters the else block, with the received
    message from the input handler.
    :param user_id
    :param call
    :param message:
    :return:
    """
    if not message:
        message_text = '''*New workout*\n\nWhat would you like to name your workout?'''
        if call:
            send_edited_message(
                user_id,
                message_text,
                call.message.id,
                reply_markup=create_workout_go_back_markup(),
                parse_mode="MarkdownV2")
        else:
            send_message(
                user_id,
                message_text,
                reply_markup=create_workout_go_back_markup(),
                parse_mode="MarkdownV2")

        set_to_redis(user_id, "WAITING_FOR_INPUT", True)
        set_to_redis(user_id, "WAITING_FOR_WORKOUT_TITLE", True)

    else:
        # received input, set global flags back to false
        remove_inline_replies(user_id)
        delete_from_redis(user_id, "WAITING_FOR_INPUT", "WAITING_FOR_WORKOUT_TITLE")
        set_workout(message)


def set_workout(message):
    """
    create a new workout
    :param message:
    :return:
    """
    user_id = str(message.from_user.id)
    workout_title = message.text
    new_workout = {
        "id": str(uuid4()),
        "title": workout_title,
        "created_by": message.from_user.id,
        "created_at": int(time.time()),
        "running": False,
        "saves": 0
    }

    # append new workout to user's list of saved workouts
    user = get_from_redis(user_id, "USER")
    user = add_to_saved_workouts(user.get("id"), new_workout)
    set_to_redis(user_id, "USER", user)

    message_text = \
        f"*New Workout*\n\n*{prepare_for_markdown_v2(workout_title)}* has been created\\! " \
        f"Now let's add some exercises\\.\n\n" \
        f"*Note*: the order in which you add exercises will be the order in " \
        f"which I'll display them during a workout\\."
    send_message(user_id, message_text.strip(), reply_markup=add_exercise_markup(), parse_mode="MarkdownV2")


def add_exercise_options(call):
    user_id = str(call.from_user.id)
    # in case the user clicked the back button after "add custom exercise", disable input flags
    delete_from_redis(user_id, "WAITING_FOR_INPUT", "WAITING_FOR_EXERCISE_NAME")

    send_edited_message(
        user_id,
        "How would you like to add a new exercise?",
        call.message.id,
        reply_markup=add_exercise_markup()
    )


def add_custom_exercise(user_id, call=None, message=None, message_type="", skip_setting=False):
    """
    in a similar vein to get_workout_title(), this function gets called multiple times in order to store user input
    :param user_id
    :param call
    :param message:
    :param message_type
    :param skip_setting
    :return:
    """

    set_to_redis(user_id, "WAITING_FOR_INPUT", True)

    if not message and call:
        message_text = "Please give the exercise a name."
        send_edited_message(user_id, message_text, call.message.id, reply_markup=add_custom_exercise_go_back_markup())
        set_to_redis(user_id, "WAITING_FOR_EXERCISE_NAME", True)
    else:
        remove_inline_replies(user_id)  # remove the "go back" option, as it is clear the user wants to continue

        if message_type == "EXERCISE_NAME":
            custom_exercise = dict()
            custom_exercise["id"] = str(uuid4())
            custom_exercise['name'] = message.text
            set_to_redis(user_id, "CUSTOM_EXERCISE", custom_exercise)
            delete_from_redis(user_id, "WAITING_FOR_EXERCISE_NAME")
            # retrieved exercise name. Ask for youtube link
            send_message(
                user_id,
                "Great!"
                "\nWould you like to add a Youtube link associated with this exercise? If not, simply click /next.")
            set_to_redis(user_id, "WAITING_FOR_EXERCISE_VIDEO_LINK", True)

        elif message_type == "EXERCISE_VIDEO_LINK":
            delete_from_redis(user_id, "WAITING_FOR_EXERCISE_VIDEO_LINK")
            if not skip_setting:
                custom_exercise = get_from_redis(user_id, "CUSTOM_EXERCISE")
                custom_exercise['video_link'] = message.text
                set_to_redis(user_id, "CUSTOM_EXERCISE", custom_exercise)

            # muscles worked here
            send_message(
                user_id,
                "How about a brief description of muscles worked?"
                "\n\n(e.g 'chest, triceps, front delts')\n\nIf not, click /next to continue.")
            set_to_redis(user_id, "WAITING_FOR_MUSCLES_WORKED", True)

        elif message_type == "EXERCISE_MUSCLES_WORKED":
            delete_from_redis(user_id, "WAITING_FOR_MUSCLES_WORKED")
            if not skip_setting:
                # handle for empty entries (e.g ", , chest, ,")
                muscles_worked = [x.strip() for x in message.text.split(",")]
                muscles_worked = [x for x in muscles_worked if x]
                muscles_worked = [muscle.strip().title() for muscle in muscles_worked]
                custom_exercise = get_from_redis(user_id, "CUSTOM_EXERCISE")
                custom_exercise['muscles_worked'] = muscles_worked
                set_to_redis(user_id, "CUSTOM_EXERCISE", custom_exercise)

            # done. Add workout to users workouts.
            delete_from_redis(user_id, "WAITING_FOR_INPUT")

            # default location to add exercise is the most recently added workout
            # unless specified (workout index in redis is not None)
            workout_index_from_redis = get_from_redis(user_id, "WORKOUT_INDEX")
            workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1

            custom_exercise = get_from_redis(user_id, "CUSTOM_EXERCISE")
            user = get_from_redis(user_id, "USER")
            user = add_exercise_to_database(user, custom_exercise, workout_index)
            set_to_redis(user_id, "USER", user)
            # the most recently added exercise was this one, so update the global variable
            set_to_redis(user_id, "MOST_RECENTLY_ADDED_EXERCISE", custom_exercise)

            exercise_added(user_id)


def choose_exercise_from_catalogue(call, path=None):
    """
    :param call:
    :param path: array containing the keys of the current path. That way this function knows where in the
    dictionary to enter
    :return:
    """
    user_id = str(call.from_user.id)
    with open("exercise_catalogue.json", "r") as f:
        exercise_data = json.loads(f.read())

    # list view is used when listing exercises
    # (as opposed to the grid view, which is used for movement groups and progressions)
    list_view = False
    if path:
        if len(path) == 3:
            # user has clicked on an exercise. Show exercise details
            catalogue_exercise = exercise_data.get(path[0]).get(path[1]).get(path[2])
            set_to_redis(user_id, "CATALOGUE_EXERCISE", catalogue_exercise)
            message_text = stringify_exercise(catalogue_exercise)
            send_edited_message(
                user_id,
                message_text,
                call.message.id,
                reply_markup=add_catalogue_exercise_markup(),
                parse_mode="MarkdownV2"
            )

        else:
            if len(path) == 1:
                message_text = "Progressions"
            elif len(path) == 2:
                message_text = "Exercises"
                list_view = True
            else:
                message_text = "UNKNOWN"

            current_keys = []
            while path:
                current_keys = exercise_data.get(path[0]).keys()
                exercise_data = exercise_data.get(path[0])
                path = path[1:]

            send_edited_message(
                user_id,
                message_text,
                call.message.id,
                reply_markup=exercise_selector_markup(current_keys, list_view))
    else:
        movement_groups = exercise_data.keys()
        send_edited_message(
            user_id,
            "Movement Groups",
            call.message.id,
            reply_markup=exercise_selector_markup(movement_groups)
        )


def add_catalogue_exercise(call, catalogue_exercise):
    user_id = str(call.from_user.id)

    workout_index_from_redis = get_from_redis(user_id, "WORKOUT_INDEX")
    workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1
    catalogue_exercise["id"] = str(uuid4())
    set_to_redis(user_id, "CATALOGUE_EXERCISE", catalogue_exercise)
    user = get_from_redis(user_id, "USER")
    user = add_exercise_to_database(user, catalogue_exercise, workout_index)
    set_to_redis(user_id, "USER", user)

    # the most recently added exercise was this one, so update the global variable
    set_to_redis(user_id, "MOST_RECENTLY_ADDED_EXERCISE", catalogue_exercise)

    # reset the exercise path
    delete_from_redis(user_id, "EXERCISE_PATH")

    exercise_added(user_id, call)


def exercise_added(user_id, call=None):
    user = get_from_redis(user_id, "USER")
    workout_index_from_redis = get_from_redis(user_id, "WORKOUT_INDEX")
    workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1
    workout_node_id = list(user.get('saved_workouts'))[workout_index]
    most_recently_added_exercise = get_from_redis(user_id, "MOST_RECENTLY_ADDED_EXERCISE")

    exercise_summary_text = \
        f"Exercise summary:\n\n" \
        f"{stringify_exercise(most_recently_added_exercise)}\n"

    confirmation_text = \
        f"Added *{prepare_for_markdown_v2(most_recently_added_exercise.get('name'))}* to " \
        f"*{prepare_for_markdown_v2(user.get('saved_workouts').get(workout_node_id).get('title'))}*\\!\n" \
        f"Would you like to add another exercise?"

    message_text = exercise_summary_text + "\n" + confirmation_text

    if call:
        # answer callback query here for catalogue exercises that have been added
        # (in order to display loading spinner until confirmation message has been sent)
        BOT.answer_callback_query(callback_query_id=call.id)

        send_edited_message(
            user_id,
            message_text,
            call.message.id,
            parse_mode="MarkdownV2",
            reply_markup=add_another_exercise_markup())
    else:
        send_message(
            user_id,
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=add_another_exercise_markup())


def do_workout(user_id, new_rep_entry=False, message=None, workout_id=None):
    """
    start workout
    :param user_id
    :param new_rep_entry:
    :param message:
    :param workout_id
    :return:
    """

    if not get_from_redis(user_id, "WORKOUT"):  # only happens once (when the workout gets started initially)
        remove_inline_replies(user_id)
        new_workout = get_saved_workout_from_user(user_id, workout_id)
        # give the new workout a new id
        new_workout['id'] = str(uuid4())
        new_workout['template_id'] = workout_id
        new_workout['created_at'] = None  # this is only needed for the template
        new_workout['running'] = True
        new_workout['started_at'] = int(time.time())

        set_to_redis(user_id, "WORKOUT", new_workout)
        set_to_redis(user_id, "CURRENT_EXERCISE_INDEX", 0)

    # create a list of exercises. Whenever the user has completed the sets for that exercise, increment index parameter
    exercise_node_ids = list(get_from_redis(user_id, "WORKOUT").get('exercises'))
    current_exercise_node_id = exercise_node_ids[get_from_redis(user_id, "CURRENT_EXERCISE_INDEX")]
    workout = get_from_redis(user_id, "WORKOUT")
    current_exercise = workout.get('exercises').get(current_exercise_node_id)

    if not new_rep_entry:
        about_to_finish = False
        pre_text = "Next up:\n\n"
        next_command = "/next"

        if current_exercise.get('id') == workout.get('exercises').get(exercise_node_ids[-1]).get('id'):
            about_to_finish = True
            pre_text = "Almost done\\!\n\n"
            next_command = "/finish"

        # if the current exercise already contains the reps property, this means that the user proceeded to the next
        # exercise before returning to continue this one. If that happens, give the use a brief overview of already
        # completed sets in this workout session
        stats_text = ""
        if current_exercise.get('reps'):
            stats_text = f"_Stats for this current session:" \
                         f"_\n*{', '.join([str(x) for x in current_exercise.get('reps')])}*\n\n"

        message_text = pre_text + f"{stringify_exercise(current_exercise)}\n" + stats_text + \
            f"Send me the rep count for each set\\. Once you're done, click {next_command}\\."

        send_message(
            user_id,
            message_text,
            reply_markup=number_pad_markup(get_from_redis(user_id, "CURRENT_EXERCISE_INDEX") != 0, about_to_finish),
            parse_mode="MarkdownV2")

        # view exercise details (such as the rolling average and other stats)
        if get_from_redis(user_id, "PAST_WORKOUT_DATA"):
            send_message(
                user_id,
                "Do you want to view your past performance with this exercise?",
                reply_markup=view_exercise_details_markup()
            )

        set_to_redis(user_id, "WAITING_FOR_REP_COUNT", True)
        set_to_redis(user_id, "WAITING_FOR_INPUT", True)

    else:
        rep_count = int(message.text)
        if not current_exercise.get('reps'):
            current_exercise['reps'] = []

        current_exercise['reps'].append(rep_count)
        set_to_redis(user_id, "WORKOUT", workout)


def show_exercise_stats(call):

    user_id = str(call.from_user.id)
    exercise_performance_history = []  # e.g: user's past performance on dips: [[8, 8, 7, 6] , [7, 7, 6, 7] , [9, 8, 9]]
    message_text = ""

    past_workout_data = get_from_redis(user_id, "PAST_WORKOUT_DATA")
    for workout_node_id in past_workout_data:
        current_exercise_node_id = \
            list(past_workout_data.get(workout_node_id).get('exercises'))[get_from_redis(user_id, "CURRENT_EXERCISE_INDEX")]
        current_exercise = past_workout_data.get(workout_node_id).get('exercises').get(current_exercise_node_id)
        exercise_performance_history.append(current_exercise.get('reps') or [])

    # [[1,2,3] , [1,2,3,4] , [1,2,3,4,5]] --> most sets: 5 ([1,2,3,4,5])
    most_sets = 0
    for sets in exercise_performance_history:
        if len(sets) > most_sets:
            most_sets = len(sets)

    # [[1,2,3] , [1,2,3,4] , [1,2,3,4,5]] --> [[1,2,3,0,0], [1,2,3,4,0], [1,2,3,4,5]]
    for sets in exercise_performance_history:
        while len(sets) < most_sets:
            sets.append(0)

    # iterate over exercise performance history. For each set, display 3-workout MA and 6-workout MA (if exist)
    for set_nr in range(most_sets):
        # 3 workout moving average:
        past_three_workouts = exercise_performance_history[-3:]
        current_set_sum = 0
        for sets in past_three_workouts:
            current_set_sum += sets[set_nr]
        three_workout_moving_average = round(current_set_sum / len(past_three_workouts), 1)

        past_six_workouts = exercise_performance_history[-6:]
        current_set_sum = 0
        for sets in past_six_workouts:
            current_set_sum += sets[set_nr]
        six_workout_moving_average = round(current_set_sum / len(past_six_workouts), 1)

        if int(three_workout_moving_average) == 0 and int(six_workout_moving_average) == 0:
            # user has probably sto
            message_text += ""
        else:
            message_text += f"_{get_digit_as_word(set_nr)} set_\n"
            three_workout_moving_average_string = \
                f"*{three_workout_moving_average}*".replace(".", "\\.")

            six_workout_moving_average_string = \
                f"*{six_workout_moving_average}*".replace(".", "\\.")
            message_text += f"🔸 {three_workout_moving_average_string}      🔹 {six_workout_moving_average_string}\n\n"

    message_text += "🔸 _average of last 3 sessions_\n🔹 _average of last 6 sessions_"

    send_edited_message(user_id, message_text, call.message.id, parse_mode="MarkdownV2")


def workout_completed(user_id):

    send_message(user_id, "Great job 💫 You're done!")

    # send workout report
    # the report consists of: total rep amount | average reps per set for ever exercise.
    report = "📝 *Workout Report*\n\n"
    workout = get_from_redis(user_id, "WORKOUT")
    report += f"_Duration_: \\~ *{round(workout.get('duration') / 60)}* minutes\n\n"
    for exercise_node_id in workout.get('exercises'):
        exercise = workout.get('exercises').get(exercise_node_id)
        if exercise.get('reps'):
            total = sum(exercise.get('reps'))
            sets = len(exercise.get('reps'))
        else:
            total = 0
            sets = 0
        average = "0" if total == 0 else str(round(total / len(exercise.get('reps')), 1)).replace(".", "\\.")
        report += \
            f"*{prepare_for_markdown_v2(exercise.get('name'))}*\n_Total_: " \
            f"*{total}*\n_No\\. of sets_: *{sets}*\n_Average per set_: *{average}*\n\n"

    # number pad custom keyboard is not needed anymore
    send_message(user_id, report, reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="MarkdownV2")


def delete_workout(call, workout_id):
    user_id = str(call.from_user.id)
    workout_title = get_saved_workout_from_user(user_id, workout_id).get('title')
    send_edited_message(
        user_id,
        f"Are you sure you want to delete *{prepare_for_markdown_v2(workout_title)}*?",
        call.message.id, reply_markup=delete_workout_confirmation_markup(workout_id), parse_mode="MarkdownV2")


def handle_view_workout(user_id, call=None):
    user = get_from_redis(user_id, "USER")
    if user.get('saved_workouts'):
        if call:
            send_edited_message(
                user_id,
                "*View workout*\n\nWhich workout would you like to view?",
                call.message.id,
                reply_markup=view_workout_details_markup(user.get('saved_workouts')), parse_mode="MarkdownV2")
        else:
            send_message(
                user_id,
                "*View workout*\n\nWhich workout would you like to view?",
                reply_markup=view_workout_details_markup(user.get('saved_workouts')), parse_mode="MarkdownV2")
    else:
        send_message(user_id, "You don't have any stored workouts.")


def show_saved_workout_details(call, workout):
    user_id = str(call.from_user.id)
    send_edited_message(
        user_id,
        stringify_workout(workout),
        call.message.id,
        parse_mode="MarkdownV2",
        reply_markup=return_to_view_workout_details_markup())


def show_recommended_routine_details(call, workout):
    user_id = str(call.from_user.id)
    send_edited_message(
        user_id,
        stringify_workout(workout),
        call.message.id,
        parse_mode="MarkdownV2",
        reply_markup=add_recommended_routine_markup(workout.get("id"))
    )


def remove_inline_replies(user_id):

    # since user interaction has proceeded, remove any previous inline reply markups.
    if exists_in_redis(user_id, "SENT_MESSAGES"):
        for ix, message in enumerate(get_from_redis(user_id, "SENT_MESSAGES")):
            message = jsonpickle.loads(message)
            if type(message.reply_markup) is telebot.types.InlineKeyboardMarkup:
                # TODO: if message doesnt exist anymore in telegram, handle for that
                send_edited_message(user_id, message.text, message.id, reply_markup=None)

    delete_from_redis(user_id, "SENT_MESSAGES")


def ask_to_show_recommended_routines(call):
    user_id = call.from_user.id
    message_text = "Would you like to view the Recommended Routine?"
    send_edited_message(user_id, message_text, call.message.id, reply_markup=view_recommended_routines_answer_markup())


def publish_workout(call, workout_id, confirmed):
    user_id = str(call.from_user.id)

    workout = get_saved_workout_from_user(user_id, workout_id)

    if not confirmed:
        message_text = f"Are you sure you want to publish *{prepare_for_markdown_v2(workout.get('title'))}*?"
        send_edited_message(
            user_id,
            message_text,
            call.message.id,
            reply_markup=confirm_publish_workout_markup(workout_id),
            parse_mode="MarkdownV2"
        )

    else:
        workout = get_saved_workout_from_database(user_id, workout_id)
        workout_key = list(workout.keys())[0]
        workout = workout.get(workout_key)
        if workout.get("published"):
            send_edited_message(
                user_id,
                f"*{prepare_for_markdown_v2(workout.get('title'))}* is already published\\. 😉",
                call.message.id,
                parse_mode="MarkdownV2"
            )
        else:
            update_saved_workout_in_database(user_id, workout_key, {"published": True})
            user = update_user_property_in_database(user_id, {"published_last_workout_at": int(time.time())})

            set_to_redis(user_id, "USER", user)
            workout = get_saved_workout_from_user(user_id, workout_id)
            # publish_to_DB() function only to be implemented if you have users interested in publishing their workouts.

            BOT.answer_callback_query(call.id)
            send_edited_message(
                user_id,
                f"Great\\! Thank you for publishing *{prepare_for_markdown_v2(workout.get('title'))}*\\. 😊",
                call.message.id,
                reply_markup=start_options_markup(),
                parse_mode="MarkdownV2"
            )


def get_saved_workout_from_user(user_id, workout_id):
    user = get_from_redis(user_id, "USER")
    if user.get("saved_workouts"):
        for workout_node in list(user.get("saved_workouts").keys()):
            if user.get("saved_workouts").get(workout_node).get("id") == workout_id:
                return user.get("saved_workouts").get(workout_node)


def view_recommended_routines(call, difficulty=None):
    user_id = str(call.from_user.id)
    if difficulty:
        title = f"Recommended Routine ({difficulty.lower()})"
        workout = get_recommended_routine_from_database(title)
        workout_key = list(workout.keys())[0]
        workout = workout.get(workout_key)
        set_to_redis(user_id, "RECOMMENDED_ROUTINE", workout)
        show_recommended_routine_details(call, workout)
    else:
        send_edited_message(
            user_id,
            "*Recommended Routine*\n\nWhich recommended routine progression would you like to view?",
            call.message.id,
            reply_markup=choose_recommended_routine_markup(),
            parse_mode="MarkdownV2"
        )


def add_recommended_routine(call, routine):
    user_id = str(call.from_user.id)
    # check if user already has this workout in his saved workouts
    if not get_saved_workout_from_user(user_id, routine.get("id")):
        user = add_to_saved_workouts(user_id, routine)
        set_to_redis(user_id, "USER", user)
        message_text = f"Done\\! Added *{prepare_for_markdown_v2(routine.get('title'))}* to your saved workouts\\."
    else:
        message_text = f"*{prepare_for_markdown_v2(routine.get('title'))}* is already in your saved workouts\\."

    send_edited_message(user_id, message_text, call.message.id, parse_mode="MarkdownV2")


def export(message):
    user_id = str(message.from_user.id)
    user = get_from_redis(user_id, "USER")
    if user.get("saved_workouts") or user.get("completed_workouts"):
        send_message(user_id, "Hodl on a sec...")
        export_data = {
            "saved_workouts": {},
            "completed_workouts": {}
        }
        if user.get("saved_workouts"):
            for ix, workout_node in enumerate(list(user.get("saved_workouts"))):
                workout = user.get("saved_workouts").get(workout_node)
                export_data.get("saved_workouts")[str(ix)] = {
                    "created_at": datetime.datetime.fromtimestamp(workout.get("created_at")).strftime('%Y-%m-%d %H:%M:%S'),
                    "title": workout.get("title"),
                    "exercises": {}
                }
                if workout.get("exercises"):
                    for iy, exercise_node in enumerate(list(workout.get("exercises"))):
                        exercise = workout.get("exercises").get(exercise_node)
                        export_data.get("saved_workouts").get(str(ix)).get("exercises")[str(iy)] = {}
                        export_data.get("saved_workouts").get(str(ix)).get("exercises")[str(iy)]["name"] = \
                            exercise.get("name")
                        if exercise.get("video_link"):
                            export_data.get("saved_workouts").get(str(ix)).get("exercises")[str(iy)]["video_link"] = \
                                exercise.get("video_link")
                        if exercise.get("muscles_worked"):
                            export_data.get("saved_workouts").get(str(ix)).get("exercises")[str(iy)]["muscles_worked"] = \
                                exercise.get("muscles_worked")

        if user.get("completed_workouts"):
            for ix, workout_node in enumerate(list(user.get("completed_workouts"))):
                workout = user.get("completed_workouts").get(workout_node)
                export_data.get("completed_workouts")[str(ix)] = {
                    "started_at": datetime.datetime.fromtimestamp(workout.get("started_at")).strftime('%Y-%m-%d %H:%M:%S'),
                    "title": workout.get("title"),
                    "duration": workout.get("duration"),
                    "exercises": {}
                }
                if workout.get("exercises"):
                    for iy, exercise_node in enumerate(list(workout.get("exercises"))):
                        exercise = workout.get("exercises").get(exercise_node)
                        export_data.get("completed_workouts").get(str(ix)).get("exercises")[str(iy)] = {}
                        export_data.get("completed_workouts").get(str(ix)).get("exercises")[str(iy)]["name"] = \
                            exercise.get("name")
                        if exercise.get("video_link"):
                            export_data.get("completed_workouts").get(str(ix)).get("exercises")[str(iy)]["video_link"] = \
                                exercise.get("video_link")
                        if exercise.get("muscles_worked"):
                            export_data.get("completed_workouts").get(str(ix)).get("exercises")[str(iy)]["muscles_worked"] = \
                                exercise.get("muscles_worked")
                        if exercise.get("reps"):
                            export_data.get("completed_workouts").get(str(ix)).get("exercises")[str(iy)]["reps"] = \
                                exercise.get("reps")

        with open("workout_data.json", "w") as fo:
            fo.write(jsonpickle.dumps(export_data))

        with open("workout_data.json", "r") as fo:
            time.sleep(0.5)
            send_message(user_id, "Here you go!")
            BOT.send_document(get_from_redis(user_id, "CHAT_ID"), fo)

        if os.path.exists("workout_data.json"):
            os.remove("workout_data.json")

        user = update_user_property_in_database(user_id, {"exported_last_workout_data_at": int(time.time())})
        set_to_redis(user_id, "USER", user)

    else:
        send_message(user_id, "You have neither created nor completed a workout. Theres nothing to export. 🙈")


def handle_user_feedback(user_id, message=None):
    if not message:
        send_message(
            user_id,
            "*Feedback*\n\nHere you can report issues you have encountered or let me know of any things you would "
            "like me to include or improve upon\\.\n\n"
            "I'm constantly aiming to improve the _myBWF_ Workout Assistant, "
            "so every bit of feedback is incredibly valuable\\.",
            parse_mode="MarkdownV2"
        )
        set_to_redis(user_id, "WAITING_FOR_INPUT", True)
        set_to_redis(user_id, "WAITING_FOR_USER_FEEDBACK", True)
    else:
        # received message. post it to feedback node in firebase
        feedback_object = {
            'user_id': message.from_user.id,
            'feedback_text': message.text
        }
        add_feedback_to_database(feedback_object)

        send_message(user_id, "Thanks a lot for your feedback! 😊")
        delete_from_redis(user_id, "WAITING_FOR_INPUT", "WAITING_FOR_USER_FEEDBACK")

        user = update_user_property_in_database(user_id, {"sent_last_feedback_at": int(time.time())})
        set_to_redis(user_id, "USER", user)


# -------------------------- webhook configuration -------------------------------

# certificate = None
certificate = open(WEBHOOK_SSL_CERT, "r")  # for prod

BOT.remove_webhook()
BOT.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, certificate=certificate)

# -------------------------- server configuration --------------------------------

CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
CONTEXT.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# web.run_app(APP, host=WEBHOOK_LISTEN, port=WEBHOOK_PORT)  # local
print("running...")
web.run_app(APP, host=WEBHOOK_LISTEN, port=WEBHOOK_PORT, ssl_context=CONTEXT)  # remote
