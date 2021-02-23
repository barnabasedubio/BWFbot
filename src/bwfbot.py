import yaml
import json
import time
import telebot
import redis
import jsonpickle

from firebase_admin import \
    credentials, \
    initialize_app

from markups import *
from database import *

from uuid import uuid4

# configuration
with open("../config.yml", "r") as fp:
    config = yaml.load(fp, yaml.FullLoader)

CRED = credentials.Certificate("../firebase_service_account_key_SECRET.json")
initialize_app(CRED, {"databaseURL": config.get("firebase").get("reference")})

CONN = redis.Redis(decode_responses=True)

TOKEN = config.get("telegram").get("token")
BOT = telebot.TeleBot(TOKEN)

USER = dict()

global \
    WAITING_FOR_INPUT, \
    WORKOUT, \
    WORKOUT_INDEX, \
    WAITING_FOR_WORKOUT_TITLE, \
    CUSTOM_EXERCISE, \
    CATALOGUE_EXERCISE, \
    MOST_RECENTLY_ADDED_EXERCISE, \
    WAITING_FOR_EXERCISE_NAME, \
    WAITING_FOR_EXERCISE_VIDEO_LINK, \
    WAITING_FOR_MUSCLES_WORKED, \
    WAITING_FOR_SETUP_DONE, \
    WAITING_FOR_REP_COUNT, \
    WAITING_FOR_USER_FEEDBACK, \
    CURRENT_EXERCISE_INDEX, \
    PAST_WORKOUT_DATA, \
    EXERCISE_PATH, \
    RESET_STATE


def confirm_reset_state():
    send_message(
        "Performing this action will cancel the running workout. Are you sure you want to continue?",
        reply_markup=reset_state_answer_markup()
    )


def reset_state():
    # reset the global state
    global \
        WAITING_FOR_INPUT, \
        WORKOUT, \
        WORKOUT_INDEX, \
        WAITING_FOR_WORKOUT_TITLE, \
        CUSTOM_EXERCISE, \
        CATALOGUE_EXERCISE, \
        MOST_RECENTLY_ADDED_EXERCISE, \
        WAITING_FOR_EXERCISE_NAME, \
        WAITING_FOR_EXERCISE_VIDEO_LINK, \
        WAITING_FOR_MUSCLES_WORKED, \
        WAITING_FOR_SETUP_DONE, \
        WAITING_FOR_REP_COUNT, \
        WAITING_FOR_USER_FEEDBACK, \
        CURRENT_EXERCISE_INDEX, \
        PAST_WORKOUT_DATA, \
        EXERCISE_PATH, \
        RESET_STATE

    WAITING_FOR_INPUT = False

    WORKOUT = None
    WORKOUT_INDEX = None
    WAITING_FOR_WORKOUT_TITLE = False

    CUSTOM_EXERCISE = None
    CATALOGUE_EXERCISE = None
    MOST_RECENTLY_ADDED_EXERCISE = None

    WAITING_FOR_EXERCISE_NAME = False
    WAITING_FOR_EXERCISE_VIDEO_LINK = False
    WAITING_FOR_MUSCLES_WORKED = False
    WAITING_FOR_SETUP_DONE = False
    WAITING_FOR_REP_COUNT = False
    WAITING_FOR_USER_FEEDBACK = False

    CURRENT_EXERCISE_INDEX = 0

    PAST_WORKOUT_DATA = {}
    EXERCISE_PATH = []

    RESET_STATE = False


# ----------------- HANDLERS --------------------
@BOT.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """
    handles all inline keyboard responses
    :param call
    """
    global \
        WORKOUT, \
        WORKOUT_INDEX, \
        RESET_STATE, \
        USER, \
        PAST_WORKOUT_DATA, \
        EXERCISE_PATH, \
        CATALOGUE_EXERCISE

    if not call.data == "add_catalogue_exercise":
        BOT.answer_callback_query(callback_query_id=call.id)  # remove loading spinner

    if call.data == "choose_workouts":
        choose_workout(call=call)

    elif call.data == "exercise_menu:choose_workouts":
        # user had the option to add another exercise, start workout, or go to the main menu.
        # clicking start workout should show the saved workout list, but the back button should not go
        # to the main menu (per usual), but back to to add another exercise option
        choose_workout(call=call, comes_from="add_another_exercise")

    elif call.data == "create_workout":
        get_workout_title_from_input(call)

    elif call.data == "add_exercise":
        add_custom_exercise(call=call)

    elif call.data == "add_catalogue_exercise":
        CATALOGUE_EXERCISE['id'] = str(uuid4())
        add_catalogue_exercise(call, CATALOGUE_EXERCISE)

    elif call.data == "explore_community":
        handle_explore_community()

    elif call.data == "request_community":
        handle_community_request(call)

    elif call.data == "start_menu":
        show_start_options(call=call)

    elif call.data == "exercise_added":
        exercise_added(call=call)

    elif call.data == "list_workouts_for_workout_details":
        handle_view_workout(call)

    elif call.data == "show_exercise_stats":
        show_exercise_stats(call)

    elif call.data == "choose_exercise_from_catalogue":
        choose_exercise_from_catalogue(call)

    elif call.data == "show_add_exercise_options":
        add_exercise_options(call)

    elif call.data.startswith("choose_exercise_from_catalogue:"):
        call.data = call.data.replace("choose_exercise_from_catalogue:", "")
        if call.data == "go_back":
            if EXERCISE_PATH:
                EXERCISE_PATH = EXERCISE_PATH[:-1]
            else:
                # user already was in root level (movement groups) when they clicked go back
                add_exercise_options(call)
                return
        else:
            EXERCISE_PATH.append(call.data)
        choose_exercise_from_catalogue(call, EXERCISE_PATH)

    elif call.data.startswith("START_WORKOUT:"):
        workout_id = call.data.replace("START_WORKOUT:", "")
        temp_workout = {}
        counter = 0
        # get workout data from users saved workouts
        for node_id in USER.get('saved_workouts'):
            if USER.get('saved_workouts').get(node_id).get('id') == workout_id:
                temp_workout = USER.get('saved_workouts').get(node_id)
                break
            counter += 1
        WORKOUT_INDEX = counter

        if USER.get('completed_workouts'):
            # get previous workout data from user's completed workouts that use the saved workout as a template
            PAST_WORKOUT_DATA = {node: workout
                                 for (node, workout) in USER.get('completed_workouts').items()
                                 if USER.get('completed_workouts').get(node).get('template_id') == workout_id}

        if temp_workout.get('exercises'):
            send_edited_message("Let's go! 💪", call.message.id)
            do_workout(workout_id=workout_id)
        else:
            send_edited_message(
                f"{temp_workout.get('title')} has no exercises. Do you want to add some?",
                call.message.id,
                reply_markup=add_exercise_markup(comes_from="start_menu"))

    elif call.data.startswith("DELETE_WORKOUT:"):
        workout_id = call.data.replace("DELETE_WORKOUT:", "")
        delete_workout(call=call, workout_id=workout_id)

    elif call.data.startswith("CONFIRM_DELETE_WORKOUT:"):
        workout_id = call.data.replace("CONFIRM_DELETE_WORKOUT:", "")
        workout = get_saved_workout_from_database(USER.get("id"), workout_id)
        workout_key = list(workout.keys())[0]
        workout_title = workout.get(workout_key).get("title")

        USER = delete_saved_workout_from_database(USER.get("id"), workout_key)
        send_edited_message(f"Done! {workout_title} is gone from your saved workouts.", call.message.id)

    elif call.data.startswith("ABORT_DELETE_WORKOUT:"):
        workout_id = call.data.replace("ABORT_DELETE_WORKOUT:", "")
        workout = get_saved_workout_from_database(USER.get("id"), workout_id)
        workout_key = list(workout.keys())[0]
        workout_title = workout.get(workout_key).get("title")
        send_edited_message(f"Gotcha! Will not delete {workout_title}.", call.message.id)

    elif call.data.startswith("VIEW_WORKOUT:"):
        workout_id = call.data.replace("VIEW_WORKOUT:", "")
        show_workout_details(call, workout_id)

    elif call.data.startswith("RESET_STATE:"):
        answer = call.data.replace("RESET_STATE:", "")
        RESET_STATE = True if answer == "YES" else False
        if RESET_STATE:
            send_edited_message(
                "Done! The running workout has been cancelled.",
                call.message.id)
            send_message("Please resend your command.", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            send_edited_message("Okay, I'll not cancel the running workout.", call.message.id)


# handle /start command
@BOT.message_handler(commands=["start"])
def initialize(message):
    global WORKOUT
    global RESET_STATE
    global USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    set_to_redis("CHAT_ID", str(message.chat.id))

    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    user_id = str(message.from_user.id)

    if bool(USER):
        show_start_options(username=USER.get('first_name'))

    else:
        USER = get_user_from_database(user_id)
        if not USER:
            # new user
            USER = add_user_to_database(
                user_id,
                message.from_user.first_name,
                message.from_user.last_name,
                message.from_user.username)

        show_start_options(username=USER.get('first_name'))


@BOT.message_handler(commands=["begin"])
def begin_workout(message):
    global \
        WORKOUT

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    reset_state()
    choose_workout()


@BOT.message_handler(commands=["create"])
def create_workout(message):
    global \
        WORKOUT, \
        RESET_STATE

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    reset_state()

    get_workout_title_from_input()


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
    global \
        WAITING_FOR_EXERCISE_VIDEO_LINK, \
        WAITING_FOR_MUSCLES_WORKED, \
        WAITING_FOR_REP_COUNT, \
        WORKOUT, \
        CURRENT_EXERCISE_INDEX

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if WAITING_FOR_EXERCISE_VIDEO_LINK:
        # user skipped the video link entry
        add_custom_exercise(message=message, message_type="EXERCISE_VIDEO_LINK", skip_setting=True)

    elif WAITING_FOR_MUSCLES_WORKED:
        # user skipped the muscles worked entry
        add_custom_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED", skip_setting=True)

    elif WAITING_FOR_REP_COUNT and CURRENT_EXERCISE_INDEX != len(WORKOUT.get('exercises')) - 1:
        # display the next exercise in the workout to the user
        # if the user is on their last exercise, this logic is handled by the /finish handler instead
        CURRENT_EXERCISE_INDEX += 1
        do_workout()


# handle /previous command
@BOT.message_handler(commands=["previous"])
def return_to_previous(message):
    global \
        CURRENT_EXERCISE_INDEX, \
        WAITING_FOR_REP_COUNT, \
        WORKOUT

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if WAITING_FOR_REP_COUNT and CURRENT_EXERCISE_INDEX > 0:
        CURRENT_EXERCISE_INDEX -= 1
        do_workout()


# handle /finish command
@BOT.message_handler(commands=["finish"])
def finish(message):
    global \
        WAITING_FOR_REP_COUNT, \
        CURRENT_EXERCISE_INDEX, \
        WORKOUT, \
        WAITING_FOR_INPUT, \
        USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if WAITING_FOR_REP_COUNT and CURRENT_EXERCISE_INDEX == len(WORKOUT.get('exercises')) - 1:
        # user is done with their workout. End workout and add it to their completed workouts
        WORKOUT['duration'] = int(time.time()) - WORKOUT.get('started_at')
        WORKOUT['running'] = False

        USER = add_completed_workout_to_database(USER.get("id"), WORKOUT)
        # reset exercise index
        CURRENT_EXERCISE_INDEX = 0  # reset
        # deactivate user input handling
        WAITING_FOR_REP_COUNT = False
        WAITING_FOR_INPUT = False

        workout_completed()


# handle clear request
@BOT.message_handler(commands=["clear"])
def clear_dialog(message):
    global \
        WORKOUT, \
        RESET_STATE

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    reset_state()

    undeletable_messages = []
    chat_id = get_from_redis("CHAT_ID")
    send_message("Clearing chat...")
    time.sleep(1.5)

    messages = [jsonpickle.loads(x) for x in get_from_redis("MESSAGES")]
    while messages:
        threshold = 86400
        if messages[0].date < int(time.time()) - threshold:
            # telegram doesnt allow bots to delete messages older than 2 days. Use 1 day threshold to play it safe
            undeletable_messages.append(messages[0])
        else:
            BOT.delete_message(chat_id, messages[0].id)

        pop_from_redis("MESSAGES")
        messages = [jsonpickle.loads(x) for x in get_from_redis("MESSAGES")] if exists_in_redis("MESSAGES") else None

    if undeletable_messages:
        send_message(
            "I'm sorry, sadly I am unable to delete messages that are older than a day."
            "Please click 'clear history' in the chat options to remove everything.")


@BOT.message_handler(commands=["delete"])
def handle_delete_workout(message):
    global \
        WORKOUT, \
        RESET_STATE, \
        USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    reset_state()

    if USER.get('saved_workouts'):
        message_text = \
            "Which workout would you like to delete?\n\n" \
            "(Note: this doesn't affect your already completed workouts, so no worries)"

        send_message(message_text, reply_markup=delete_workout_markup(USER.get('saved_workouts')))
    else:
        send_message("You don't have any stored workouts.")


@BOT.message_handler(commands=["view"])
def view_workout(message):
    global WORKOUT, RESET_STATE

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    handle_view_workout()


@BOT.message_handler(commands=["feedback"])
def user_feedback(message):
    global WORKOUT, RESET_STATE

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    handle_user_feedback()


@BOT.message_handler(commands=["stats", "publish"])
def feature_in_progress(message):
    global WORKOUT, RESET_STATE

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    if WORKOUT and WORKOUT.get('running') and not RESET_STATE:
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    send_message(
        "This feature is currently still getting developed. "
        "In the meantime, please send me some /feedback as to what you would like to see!")


# only if bot is expecting user input
# needs to be the very last handler!!
@BOT.message_handler(func=lambda message: message.text)
def handle_user_input(message):
    """
    handles actual user input written to chat.
    similar to func proceed_to_next(), the context is derived from the global variables
    :param message
    """
    global \
        WAITING_FOR_INPUT, \
        WAITING_FOR_WORKOUT_TITLE, \
        WAITING_FOR_EXERCISE_NAME, \
        WAITING_FOR_EXERCISE_VIDEO_LINK, \
        WAITING_FOR_MUSCLES_WORKED, \
        WAITING_FOR_REP_COUNT, \
        WAITING_FOR_USER_FEEDBACK

    # log all message ids
    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    # only handle if the bot is also waiting for user input
    if WAITING_FOR_INPUT:
        # create workout
        if WAITING_FOR_WORKOUT_TITLE:
            get_workout_title_from_input(message=message)
        # create exercise
        elif WAITING_FOR_EXERCISE_NAME:
            add_custom_exercise(message=message, message_type="EXERCISE_NAME")
        elif WAITING_FOR_EXERCISE_VIDEO_LINK:
            add_custom_exercise(message=message, message_type="EXERCISE_VIDEO_LINK")
        elif WAITING_FOR_MUSCLES_WORKED:
            add_custom_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED")
        # add reps to exercise
        elif WAITING_FOR_REP_COUNT:
            if message.text.isnumeric():
                do_workout(True, message)
        elif WAITING_FOR_USER_FEEDBACK:
            handle_user_feedback(message)


# ----------------- FUNCTIONS ------------------

def show_start_options(call=None, username="username"):
    reset_state()
    if call:
        message_text = \
            "What can I help you with?\n\n" \
            "Type '/' to see all commands you can give me."
        send_edited_message(message_text, call.message.id, reply_markup=start_options_markup())
    else:
        message_text = f'''
                Hey, {username}! What would you like to do today?
                \nType '/' to see all commands you can give me.'''

        send_message(message_text.strip(), reply_markup=start_options_markup())


def send_message(message_text, reply_markup=None, parse_mode=""):
    global BOT

    chat_id = get_from_redis("CHAT_ID")
    sent_message = BOT.send_message(
        chat_id,
        message_text,
        reply_markup=reply_markup, disable_web_page_preview=True,
        parse_mode=parse_mode)

    push_to_redis("MESSAGES", jsonpickle.dumps(sent_message))


def send_edited_message(message_text, previous_message_id, reply_markup=None, parse_mode=""):
    global BOT

    message_to_edit = None
    message_index = None
    chat_id = get_from_redis("CHAT_ID")

    messages = [jsonpickle.loads(x) for x in get_from_redis("MESSAGES")]

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

    set_list_index_to_redis("MESSAGES", message_index, jsonpickle.dumps(new_message))


def choose_workout(call=None, comes_from=None):
    global USER

    if USER.get('saved_workouts'):
        message_text = \
            "Which workout routine would you like to start?\n\n" \
            "If you want to view the exercises in each workout, click /view\\."

        if comes_from == "add_another_exercise":
            reply_markup = list_workouts_markup(USER.get('saved_workouts'), comes_from="add_another_exercise")
        else:
            reply_markup = list_workouts_markup(USER.get('saved_workouts'))

        if call:
            send_edited_message(
                message_text,
                call.message.id,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2")
        else:
            send_message(
                message_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2")
    else:
        if call:
            message_text = "You don't have any stored workouts. Would you like to create a new one?"
            send_edited_message(
                message_text,
                call.message.id,
                reply_markup=create_workout_answer_markup())
        else:
            # if the user wants to start a working by sending /begin command
            message_text = "You don't have any stored workouts. Would you like to create a new one?"
            send_message(
                message_text,
                reply_markup=create_workout_answer_markup())


def get_workout_title_from_input(call=None, message=None):
    """
    This function gets called twice. Once upon creating a new workout, and once after the
    user has typed in the workout name. The initial call has no message value, thus the first
    condition gets executed. After user input has been handled by handle_workout_title()
    and this function gets called again, it enters the else block, with the received
    message from the input handler.
    :param call
    :param message:
    :return:
    """
    global \
        WAITING_FOR_INPUT, \
        WAITING_FOR_WORKOUT_TITLE

    if not message:
        message_text = '''*New workout*\n\nWhat would you like to name your workout?'''
        if call:
            send_edited_message(
                message_text,
                call.message.id,
                reply_markup=create_workout_go_back_markup(),
                parse_mode="MarkdownV2")
        else:
            send_message(
                message_text,
                reply_markup=create_workout_go_back_markup(),
                parse_mode="MarkdownV2")

        WAITING_FOR_INPUT = True
        WAITING_FOR_WORKOUT_TITLE = True

    else:
        # received input, set global flags back to false
        remove_inline_replies()
        WAITING_FOR_INPUT = False
        WAITING_FOR_WORKOUT_TITLE = False
        set_workout(message)


def set_workout(message):
    """
    create a new workout
    :param message:
    :return:
    """
    global USER

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
    USER = add_workout_to_database(USER.get("id"), new_workout)

    message_text = \
        f"*New Workout*\n\n*{prepare_for_markdown_v2(workout_title)}* has been created\\! " \
        f"Now let's add some exercises\\.\n\n" \
        f"*Note*: the order in which you add exercises will be the order in " \
        f"which I'll display them during a workout\\."
    send_message(message_text.strip(), reply_markup=add_exercise_markup(), parse_mode="MarkdownV2")


def add_exercise_options(call):
    global WAITING_FOR_INPUT, WAITING_FOR_EXERCISE_NAME

    # in case the user clicked the back button after "add custom exercise", disable input flags
    WAITING_FOR_INPUT = False
    WAITING_FOR_EXERCISE_NAME = False

    send_edited_message(
        "How would you like to add a new exercise?",
        call.message.id,
        reply_markup=add_exercise_markup()
    )


def add_custom_exercise(call=None, message=None, message_type="", skip_setting=False):
    """
    in a similar vein to get_workout_title(), this function gets called multiple times in order to store user input
    :param call
    :param message:
    :param message_type
    :param skip_setting
    :return:
    """

    global \
        CUSTOM_EXERCISE, \
        MOST_RECENTLY_ADDED_EXERCISE, \
        WAITING_FOR_INPUT, \
        WAITING_FOR_EXERCISE_NAME, \
        WAITING_FOR_EXERCISE_VIDEO_LINK, \
        WAITING_FOR_MUSCLES_WORKED, \
        WORKOUT_INDEX, \
        USER

    WAITING_FOR_INPUT = True

    if not message and call:
        message_text = "Please give the exercise a name."
        send_edited_message(message_text, call.message.id, reply_markup=add_custom_exercise_go_back_markup())
        WAITING_FOR_EXERCISE_NAME = True
    else:
        remove_inline_replies()  # remove the "go back" option, as it is clear the user wants to continue

        if message_type == "EXERCISE_NAME":
            CUSTOM_EXERCISE = dict()
            CUSTOM_EXERCISE["id"] = str(uuid4())
            CUSTOM_EXERCISE['name'] = message.text
            WAITING_FOR_EXERCISE_NAME = False
            # retrieved exercise name. Ask for youtube link
            send_message(
                "Great!"
                "\nWould you like to add a Youtube link associated with this exercise? If not, simply click /next.")
            WAITING_FOR_EXERCISE_VIDEO_LINK = True

        elif message_type == "EXERCISE_VIDEO_LINK":
            WAITING_FOR_EXERCISE_VIDEO_LINK = False
            if not skip_setting:
                CUSTOM_EXERCISE['video_link'] = message.text

            # muscles worked here
            send_message(
                "How about a brief description of muscles worked?"
                "\n\n(e.g 'chest, triceps, front delts')\n\nIf not, click /next to continue.")
            WAITING_FOR_MUSCLES_WORKED = True

        elif message_type == "EXERCISE_MUSCLES_WORKED":
            WAITING_FOR_MUSCLES_WORKED = False
            if not skip_setting:
                # handle for empty entries (e.g ", , chest, ,")
                muscles_worked = [x.strip() for x in message.text.split(",")]
                muscles_worked = [x for x in muscles_worked if x]
                muscles_worked = [muscle.strip().title() for muscle in muscles_worked]
                CUSTOM_EXERCISE['muscles_worked'] = muscles_worked

            # done. Add workout to users workouts.
            WAITING_FOR_INPUT = False

            # default location to add exercise is the most recently added workout
            # unless specified (WORKOUT_INDEX not None)
            workout_index = WORKOUT_INDEX if type(WORKOUT_INDEX) is int else -1

            USER = add_exercise_to_database(USER, CUSTOM_EXERCISE, workout_index)

            # the most recently added exercise was this one, so update the global variable
            MOST_RECENTLY_ADDED_EXERCISE = CUSTOM_EXERCISE

            exercise_added()


def choose_exercise_from_catalogue(call, path=None):
    """
    :param call:
    :param path: array containing the keys of the current path. That way this function knows where in the
    dictionary to enter
    :return:
    """
    global CATALOGUE_EXERCISE

    with open("exercises.json", "r") as f:
        exercise_data = json.loads(f.read())

    # list view is used when listing exercises
    # (as opposed to the grid view, which is used for movement groups and progressions)
    list_view = False
    if path:
        if len(path) == 3:
            # user has clicked on an exercise. Show exercise details
            CATALOGUE_EXERCISE = exercise_data.get(path[0]).get(path[1]).get(path[2])
            message_text = stringify_exercise(CATALOGUE_EXERCISE)
            send_edited_message(
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
                message_text,
                call.message.id,
                reply_markup=exercise_selector_markup(current_keys, list_view))
    else:
        movement_groups = exercise_data.keys()
        send_edited_message(
            "Movement Groups",
            call.message.id,
            reply_markup=exercise_selector_markup(movement_groups)
        )


def add_catalogue_exercise(call, catalogue_exercise):
    global \
        WORKOUT_INDEX, \
        MOST_RECENTLY_ADDED_EXERCISE, \
        EXERCISE_PATH, \
        USER

    workout_index = WORKOUT_INDEX if type(WORKOUT_INDEX) is int else -1
    USER = add_exercise_to_database(USER, catalogue_exercise, workout_index)

    # the most recently added exercise was this one, so update the global variable
    MOST_RECENTLY_ADDED_EXERCISE = catalogue_exercise

    # reset the exercise path
    EXERCISE_PATH = []

    exercise_added(call)


def exercise_added(call=None):
    global \
        WORKOUT_INDEX, \
        MOST_RECENTLY_ADDED_EXERCISE, \
        USER

    remove_inline_replies()

    workout_index = WORKOUT_INDEX if type(WORKOUT_INDEX) is int else -1
    workout_node_id = list(USER.get('saved_workouts'))[workout_index]

    exercise_summary_text = \
        f"Exercise summary:\n\n" \
        f"{stringify_exercise(MOST_RECENTLY_ADDED_EXERCISE)}\n"

    confirmation_text = \
        f"Added *{prepare_for_markdown_v2(MOST_RECENTLY_ADDED_EXERCISE.get('name'))}* to " \
        f"*{USER.get('saved_workouts').get(workout_node_id).get('title')}*\\!\n" \
        f"Would you like to add another exercise?"

    message_text = exercise_summary_text + "\n" + confirmation_text

    if call:
        # TODO: answer callback query here for catalogue exercises that have been added
        #  (in order to display loading spinner until confirmation message has been sent)
        BOT.answer_callback_query(callback_query_id=call.id)

        send_edited_message(
            message_text,
            call.message.id,
            parse_mode="MarkdownV2",
            reply_markup=add_another_exercise_markup())
    else:
        send_message(
            message_text,
            parse_mode="MarkdownV2",
            reply_markup=add_another_exercise_markup())


def do_workout(new_rep_entry=False, message=None, workout_id=None):
    """
    start workout
    :param new_rep_entry:
    :param message:
    :param workout_id
    :return:
    """
    global \
        WORKOUT, \
        WAITING_FOR_REP_COUNT, \
        WAITING_FOR_INPUT, \
        CURRENT_EXERCISE_INDEX, \
        PAST_WORKOUT_DATA, \
        USER

    if not WORKOUT:
        # only happens once (when the workout gets started initially)
        WORKOUT = get_saved_workout_from_database(USER.get("id"), workout_id)
        WORKOUT = WORKOUT.get(list(WORKOUT.keys())[0])
        # give the new workout a new id
        WORKOUT['id'] = str(uuid4())
        WORKOUT['template_id'] = workout_id
        WORKOUT['created_at'] = None  # this is only needed for the template
        WORKOUT['running'] = True
        WORKOUT['started_at'] = int(time.time())

    # create a list of exercises. Whenever the user has completed the sets for that exercise, increment index parameter
    exercise_node_ids = list(WORKOUT.get('exercises'))
    current_exercise_node_id = exercise_node_ids[CURRENT_EXERCISE_INDEX]
    current_exercise = WORKOUT.get('exercises').get(current_exercise_node_id)

    if not new_rep_entry:
        about_to_finish = False
        pre_text = "Next up:\n\n"
        next_command = "/next"

        if current_exercise.get('id') == WORKOUT.get('exercises').get(exercise_node_ids[-1]).get('id'):
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
            message_text,
            reply_markup=number_pad_markup(CURRENT_EXERCISE_INDEX != 0, about_to_finish),
            parse_mode="MarkdownV2")

        # view exercise details (such as the rolling average and other stats)
        if PAST_WORKOUT_DATA:
            send_message(
                "Do you want to view your past performance with this exercise?",
                reply_markup=view_exercise_details_markup()
            )

        WAITING_FOR_REP_COUNT = True
        WAITING_FOR_INPUT = True

    else:
        rep_count = int(message.text)
        if not current_exercise.get('reps'):
            current_exercise['reps'] = []

        current_exercise['reps'].append(rep_count)


def show_exercise_stats(call):
    global \
        CURRENT_EXERCISE_INDEX, \
        PAST_WORKOUT_DATA

    exercise_performance_history = []  # e.g: user's past performance on dips: [[8, 8, 7, 6] , [7, 7, 6, 7] , [9, 8, 9]]
    message_text = ""

    for workout_node_id in PAST_WORKOUT_DATA:
        current_exercise_node_id = list(PAST_WORKOUT_DATA.get(workout_node_id).get('exercises'))[CURRENT_EXERCISE_INDEX]
        current_exercise = PAST_WORKOUT_DATA.get(workout_node_id).get('exercises').get(current_exercise_node_id)
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

    send_edited_message(message_text, call.message.id, parse_mode="MarkdownV2")


def workout_completed():
    global WORKOUT

    send_message("Great job 💪 You're done!")

    # send workout report
    # the report consists of: total rep amount | average reps per set for ever exercise.
    report = "📝 *Workout Report*\n\n"
    report += f"_Duration_: \\~ *{round(WORKOUT.get('duration') / 60)}* minutes\n\n"
    for exercise_node_id in WORKOUT.get('exercises'):
        exercise = WORKOUT.get('exercises').get(exercise_node_id)
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
    send_message(report, reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="MarkdownV2")


def delete_workout(call, workout_id):
    global USER
    workout_title = list(get_saved_workout_from_database(USER.get("id"), workout_id).values())[0].get('title')
    send_edited_message(
        f"Are you sure you want to delete {workout_title}?",
        call.message.id, reply_markup=delete_workout_confirmation_markup(workout_id))


def handle_view_workout(call=None):
    global USER

    if USER.get('saved_workouts'):
        if call:
            send_edited_message(
                "Which workout would you like to view?",
                call.message.id,
                reply_markup=view_workout_details_markup(USER.get('saved_workouts')))
        else:
            send_message(
                "Which workout would you like to view?",
                reply_markup=view_workout_details_markup(USER.get('saved_workouts')))
    else:
        send_message("You don't have any stored workouts.")


def show_workout_details(call, workout_id):
    global USER
    workout = get_saved_workout_from_database(USER.get("id"), workout_id)

    send_edited_message(
        stringify_workout(workout),
        call.message.id,
        parse_mode="MarkdownV2",
        reply_markup=return_to_view_workout_details_markup())


def stringify_workout(workout):
    workout = workout.get(list(workout.keys())[0])
    result_string = f"*{prepare_for_markdown_v2(workout.get('title').title())}*\n\n"
    if workout.get('exercises'):
        result_string += "_Exercises:_\n\n"
        for node_id in workout.get('exercises'):
            result_string += stringify_exercise(workout.get('exercises').get(node_id)) + "\n"

    return result_string


def stringify_exercise(exercise):
    result_string = f"*{prepare_for_markdown_v2(exercise.get('name').title())}*\n"
    if exercise.get('video_link'):
        result_string += f"[Video demonstration]({exercise.get('video_link')})\n"
    if exercise.get('muscles_worked'):
        result_string += "_muscles worked_:\n"
        for muscle in exercise.get('muscles_worked'):
            result_string += "• " + prepare_for_markdown_v2(muscle) + "\n"

    return result_string


def prepare_for_markdown_v2(string):
    special_characters = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for character in special_characters:
        string = string.replace(character, f"\\{character}")

    return string


def remove_inline_replies():
    # since user interaction has proceeded, remove any previous inline reply markups.
    for message in get_from_redis("MESSAGES"):
        message = jsonpickle.loads(message)
        if type(message.reply_markup) is telebot.types.InlineKeyboardMarkup:
            send_edited_message(message.text, message.id, reply_markup=None)


def handle_community_request(call):
    message_text = "Would you like to explore workouts created by the bodyweight fitness community?"
    send_edited_message(message_text, call.message.id, reply_markup=explore_community_workouts_answer_markup())


def handle_explore_community():
    pass


def handle_user_feedback(message=None):
    global WAITING_FOR_INPUT, WAITING_FOR_USER_FEEDBACK

    if not message:
        send_message(
            "How are you enjoying my service? "
            "Is there anything you would like to me to include, or improve upon?"
            "\n\nI am constantly trying to get better, so please pour your heart out!"
        )
        WAITING_FOR_INPUT = True
        WAITING_FOR_USER_FEEDBACK = True
    else:
        # received message. post it to feedback node in firebase
        feedback_object = {
            'user_id': message.from_user.id,
            'feedback_text': message.text
        }
        add_feedback_to_database(feedback_object)

        send_message("Thanks a lot for your feedback! 😊")
        WAITING_FOR_INPUT = False
        WAITING_FOR_USER_FEEDBACK = False


def get_digit_as_word(index):
    digits = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eight", "ninth"]
    if index < 9:
        return f"{digits[index]}"
    else:
        return f"{index}th"


def exists_in_redis(key):
    return bool(CONN.exists(key))


def get_from_redis(key):
    if CONN.type(key) == "list":
        return CONN.lrange(key, 0, -1)

    elif CONN.type(key) == int and CONN.get(key) in (0, 1):
        return bool(CONN.get(key))

    return CONN.get(key)


def set_to_redis(key, value):
    if type(value) == bool:
        value = int(value)

    elif type(value) == dict:
        value = json.dumps(value)
    CONN.set(key, value)


def push_to_redis(key, value):
    CONN.rpush(key, value)


def set_list_index_to_redis(key, index, value):
    CONN.lset(key, index, value)


def pop_from_redis(key):
    CONN.lpop(key)


if __name__ == "__main__":
    reset_state()
    BOT.polling()
