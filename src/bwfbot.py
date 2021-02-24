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

"""
global variables stored in REDIS:
session:
    MESSAGE
    CHAT_ID
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


def confirm_reset_state():
    send_message(
        "Performing this action will cancel the running workout. Are you sure you want to continue?",
        reply_markup=reset_state_answer_markup()
    )


def reset_state():
    # reset the global state

    # TODO: pipe this
    set_to_redis("WAITING_FOR_INPUT", False)
    set_to_redis("WAITING_FOR_WORKOUT_TITLE", False)
    set_to_redis("WAITING_FOR_EXERCISE_NAME", False)
    set_to_redis("WAITING_FOR_EXERCISE_VIDEO_LINK", False)
    set_to_redis("WAITING_FOR_MUSCLES_WORKED", False)
    set_to_redis("WAITING_FOR_REP_COUNT", False)
    set_to_redis("WAITING_FOR_USER_FEEDBACK", False)
    set_to_redis("WORKOUT", None)
    set_to_redis("WORKOUT_INDEX", None)
    set_to_redis("PAST_WORKOUT_DATA", None)
    set_to_redis("CURRENT_EXERCISE_INDEX", 0)
    set_to_redis("CUSTOM_EXERCISE", None)
    set_to_redis("CATALOGUE_EXERCISE", None)
    set_to_redis("MOST_RECENTLY_ADDED_EXERCISE", None)
    delete_from_redis("EXERCISE_PATH")
    set_to_redis("RESET_STATE", False)


# ----------------- HANDLERS --------------------
@BOT.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """
    handles all inline keyboard responses
    :param call
    """
    global \
        USER

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
        catalogue_exercise = get_from_redis("CATALOGUE_EXERCISE")
        add_catalogue_exercise(call, catalogue_exercise)

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
            if get_from_redis("EXERCISE_PATH"):
                pop_from_redis("EXERCISE_PATH", "right")
            else:
                # user already was in root level (movement groups) when they clicked go back
                add_exercise_options(call)
                return
        else:
            push_to_redis("EXERCISE_PATH", call.data)
        choose_exercise_from_catalogue(call, get_from_redis("EXERCISE_PATH"))

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
        set_to_redis("WORKOUT_INDEX", counter)

        if USER.get('completed_workouts'):
            # get previous workout data from user's completed workouts that use the saved workout as a template
            past_workout_data = {node: workout
                                 for (node, workout) in USER.get('completed_workouts').items()
                                 if USER.get('completed_workouts').get(node).get('template_id') == workout_id}
            set_to_redis("PAST_WORKOUT_DATA", past_workout_data)

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
        reset_state_flag = True if answer == "YES" else False
        set_to_redis("RESET_STATE", reset_state_flag)
        if reset_state_flag:
            send_edited_message(
                "Done! The running workout has been cancelled.",
                call.message.id)
            send_message("Please resend your command.", reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            send_edited_message("Okay, I'll not cancel the running workout.", call.message.id)


# handle /start command
@BOT.message_handler(commands=["start"])
def initialize(message):
    global USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    set_to_redis("CHAT_ID", str(message.chat.id))

    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
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

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
        confirm_reset_state()
        return

    reset_state()
    choose_workout()


@BOT.message_handler(commands=["create"])
def create_workout(message):

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
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

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if get_from_redis("WAITING_FOR_EXERCISE_VIDEO_LINK"):
        # user skipped the video link entry
        add_custom_exercise(message=message, message_type="EXERCISE_VIDEO_LINK", skip_setting=True)

    elif get_from_redis("WAITING_FOR_MUSCLES_WORKED"):
        # user skipped the muscles worked entry
        add_custom_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED", skip_setting=True)

    elif get_from_redis("WAITING_FOR_REP_COUNT") and \
            get_from_redis("CURRENT_EXERCISE_INDEX") != len(get_from_redis("WORKOUT").get('exercises')) - 1:
        # display the next exercise in the workout to the user
        # if the user is on their last exercise, this logic is handled by the /finish handler instead
        increment_in_redis("CURRENT_EXERCISE_INDEX")
        do_workout()


# handle /previous command
@BOT.message_handler(commands=["previous"])
def return_to_previous(message):

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    if get_from_redis("WAITING_FOR_REP_COUNT") and get_from_redis("CURRENT_EXERCISE_INDEX") > 0:
        decrement_in_redis("CURRENT_EXERCISE_INDEX")
        do_workout()


# handle /finish command
@BOT.message_handler(commands=["finish"])
def finish(message):
    global \
        USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    workout = get_from_redis("WORKOUT")
    if get_from_redis("WAITING_FOR_REP_COUNT") and \
            get_from_redis("CURRENT_EXERCISE_INDEX") == len(workout.get('exercises')) - 1:
        # user is done with their workout. End workout and add it to their completed workouts
        workout['duration'] = int(time.time()) - workout.get('started_at')
        workout['running'] = False

        set_to_redis("WORKOUT", workout)
        USER = add_completed_workout_to_database(USER.get("id"), workout)

        # reset exercise index
        set_to_redis("CURRENT_EXERCISE_INDEX", 0)  # reset
        # deactivate user input handling
        set_to_redis("WAITING_FOR_REP_COUNT", False)
        set_to_redis("WAITING_FOR_INPUT", False)

        workout_completed()


# handle clear request
@BOT.message_handler(commands=["clear"])
def clear_dialog(message):

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
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

        pop_from_redis("MESSAGES", "right")
        messages = [jsonpickle.loads(x) for x in get_from_redis("MESSAGES")] if exists_in_redis("MESSAGES") else None

    if undeletable_messages:
        send_message(
            "I'm sorry, sadly I am unable to delete messages that are older than a day."
            "Please click 'clear history' in the chat options to remove everything.")


@BOT.message_handler(commands=["delete"])
def handle_delete_workout(message):
    global \
        USER

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
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

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    handle_view_workout()


@BOT.message_handler(commands=["feedback"])
def user_feedback(message):

    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
        confirm_reset_state()
        return

    # reset application state for every new session
    reset_state()

    handle_user_feedback()


@BOT.message_handler(commands=["stats", "publish"])
def feature_in_progress(message):

    push_to_redis("MESSAGES", jsonpickle.dumps(message))
    remove_inline_replies()

    workout = get_from_redis("WORKOUT")
    if workout and workout.get('running') and not get_from_redis("RESET_STATE"):
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

    # log all message ids
    push_to_redis("MESSAGES", jsonpickle.dumps(message))

    # only handle if the bot is also waiting for user input
    if get_from_redis("WAITING_FOR_INPUT"):
        # create workout
        if get_from_redis("WAITING_FOR_WORKOUT_TITLE"):
            get_workout_title_from_input(message=message)
        # create exercise
        elif get_from_redis("WAITING_FOR_EXERCISE_NAME"):
            add_custom_exercise(message=message, message_type="EXERCISE_NAME")
        elif get_from_redis("WAITING_FOR_EXERCISE_VIDEO_LINK"):
            add_custom_exercise(message=message, message_type="EXERCISE_VIDEO_LINK")
        elif get_from_redis("WAITING_FOR_MUSCLES_WORKED"):
            add_custom_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED")
        # add reps to exercise
        elif get_from_redis("WAITING_FOR_REP_COUNT"):
            if message.text.isnumeric():
                do_workout(True, message)
        elif get_from_redis("WAITING_FOR_USER_FEEDBACK"):
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

        set_to_redis("WAITING_FOR_INPUT", True)
        set_to_redis("WAITING_FOR_WORKOUT_TITLE", True)

    else:
        # received input, set global flags back to false
        remove_inline_replies()
        set_to_redis("WAITING_FOR_INPUT", False)
        set_to_redis("WAITING_FOR_WORKOUT_TITLE", False)
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

    # in case the user clicked the back button after "add custom exercise", disable input flags
    set_to_redis("WAITING_FOR_INPUT", False)
    set_to_redis("WAITING_FOR_EXERCISE_NAME", False)

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
        USER

    set_to_redis("WAITING_FOR_INPUT", True)

    if not message and call:
        message_text = "Please give the exercise a name."
        send_edited_message(message_text, call.message.id, reply_markup=add_custom_exercise_go_back_markup())
        set_to_redis("WAITING_FOR_EXERCISE_NAME", True)
    else:
        remove_inline_replies()  # remove the "go back" option, as it is clear the user wants to continue

        if message_type == "EXERCISE_NAME":
            custom_exercise = dict()
            custom_exercise["id"] = str(uuid4())
            custom_exercise['name'] = message.text
            set_to_redis("CUSTOM_EXERCISE", custom_exercise)
            set_to_redis("WAITING_FOR_EXERCISE_NAME", False)
            # retrieved exercise name. Ask for youtube link
            send_message(
                "Great!"
                "\nWould you like to add a Youtube link associated with this exercise? If not, simply click /next.")
            set_to_redis("WAITING_FOR_EXERCISE_VIDEO_LINK", True)

        elif message_type == "EXERCISE_VIDEO_LINK":
            set_to_redis("WAITING_FOR_EXERCISE_VIDEO_LINK", False)
            if not skip_setting:
                custom_exercise = get_from_redis("CUSTOM_EXERCISE")
                custom_exercise['video_link'] = message.text
                set_to_redis("CUSTOM_EXERCISE", custom_exercise)

            # muscles worked here
            send_message(
                "How about a brief description of muscles worked?"
                "\n\n(e.g 'chest, triceps, front delts')\n\nIf not, click /next to continue.")
            set_to_redis("WAITING_FOR_MUSCLES_WORKED", True)

        elif message_type == "EXERCISE_MUSCLES_WORKED":
            set_to_redis("WAITING_FOR_MUSCLES_WORKED", False)
            if not skip_setting:
                # handle for empty entries (e.g ", , chest, ,")
                muscles_worked = [x.strip() for x in message.text.split(",")]
                muscles_worked = [x for x in muscles_worked if x]
                muscles_worked = [muscle.strip().title() for muscle in muscles_worked]
                custom_exercise = get_from_redis("CUSTOM_EXERCISE")
                custom_exercise['muscles_worked'] = muscles_worked
                set_to_redis("CUSTOM_EXERCISE", custom_exercise)

            # done. Add workout to users workouts.
            set_to_redis("WAITING_FOR_INPUT", False)

            # default location to add exercise is the most recently added workout
            # unless specified (workout index in redis is not None)
            workout_index_from_redis = get_from_redis("WORKOUT_INDEX")
            workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1

            custom_exercise = get_from_redis("CUSTOM_EXERCISE")
            USER = add_exercise_to_database(USER, custom_exercise, workout_index)
            # the most recently added exercise was this one, so update the global variable
            set_to_redis("MOST_RECENTLY_ADDED_EXERCISE", custom_exercise)

            exercise_added()


def choose_exercise_from_catalogue(call, path=None):
    """
    :param call:
    :param path: array containing the keys of the current path. That way this function knows where in the
    dictionary to enter
    :return:
    """

    with open("exercises.json", "r") as f:
        exercise_data = json.loads(f.read())

    # list view is used when listing exercises
    # (as opposed to the grid view, which is used for movement groups and progressions)
    list_view = False
    if path:
        if len(path) == 3:
            # user has clicked on an exercise. Show exercise details
            catalogue_exercise = exercise_data.get(path[0]).get(path[1]).get(path[2])
            set_to_redis("CATALOGUE_EXERCISE", catalogue_exercise)
            message_text = stringify_exercise(catalogue_exercise)
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
        USER

    workout_index_from_redis = get_from_redis("WORKOUT_INDEX")
    workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1
    catalogue_exercise["id"] = str(uuid4())
    set_to_redis("CATALOGUE_EXERCISE", catalogue_exercise)
    USER = add_exercise_to_database(USER, catalogue_exercise, workout_index)

    # the most recently added exercise was this one, so update the global variable
    set_to_redis("MOST_RECENTLY_ADDED_EXERCISE", catalogue_exercise)

    # reset the exercise path
    delete_from_redis("EXERCISE_PATH")

    exercise_added(call)


def exercise_added(call=None):
    global \
        USER

    remove_inline_replies()

    workout_index_from_redis = get_from_redis("WORKOUT_INDEX")
    workout_index = workout_index_from_redis if type(workout_index_from_redis) is int else -1
    workout_node_id = list(USER.get('saved_workouts'))[workout_index]
    most_recently_added_exercise = get_from_redis("MOST_RECENTLY_ADDED_EXERCISE")

    exercise_summary_text = \
        f"Exercise summary:\n\n" \
        f"{stringify_exercise(most_recently_added_exercise)}\n"

    confirmation_text = \
        f"Added *{prepare_for_markdown_v2(most_recently_added_exercise.get('name'))}* to " \
        f"*{USER.get('saved_workouts').get(workout_node_id).get('title')}*\\!\n" \
        f"Would you like to add another exercise?"

    message_text = exercise_summary_text + "\n" + confirmation_text

    if call:
        # answer callback query here for catalogue exercises that have been added
        # (in order to display loading spinner until confirmation message has been sent)
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
        USER

    if not get_from_redis("WORKOUT"):
        # only happens once (when the workout gets started initially)
        new_workout = get_saved_workout_from_database(USER.get("id"), workout_id)
        new_workout = new_workout.get(list(new_workout.keys())[0])
        # give the new workout a new id
        new_workout['id'] = str(uuid4())
        new_workout['template_id'] = workout_id
        new_workout['created_at'] = None  # this is only needed for the template
        new_workout['running'] = True
        new_workout['started_at'] = int(time.time())

        set_to_redis("WORKOUT", new_workout)

    # create a list of exercises. Whenever the user has completed the sets for that exercise, increment index parameter
    exercise_node_ids = list(get_from_redis("WORKOUT").get('exercises'))
    current_exercise_node_id = exercise_node_ids[get_from_redis("CURRENT_EXERCISE_INDEX")]
    workout = get_from_redis("WORKOUT")
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
            message_text,
            reply_markup=number_pad_markup(get_from_redis("CURRENT_EXERCISE_INDEX") != 0, about_to_finish),
            parse_mode="MarkdownV2")

        # view exercise details (such as the rolling average and other stats)
        if get_from_redis("PAST_WORKOUT_DATA"):
            send_message(
                "Do you want to view your past performance with this exercise?",
                reply_markup=view_exercise_details_markup()
            )

        set_to_redis("WAITING_FOR_REP_COUNT", True)
        set_to_redis("WAITING_FOR_INPUT", True)

    else:
        rep_count = int(message.text)
        if not current_exercise.get('reps'):
            current_exercise['reps'] = []

        current_exercise['reps'].append(rep_count)
        set_to_redis("WORKOUT", workout)


def show_exercise_stats(call):

    exercise_performance_history = []  # e.g: user's past performance on dips: [[8, 8, 7, 6] , [7, 7, 6, 7] , [9, 8, 9]]
    message_text = ""

    past_workout_data = get_from_redis("PAST_WORKOUT_DATA")
    for workout_node_id in past_workout_data:
        current_exercise_node_id = \
            list(past_workout_data.get(workout_node_id).get('exercises'))[get_from_redis("CURRENT_EXERCISE_INDEX")]
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

    send_edited_message(message_text, call.message.id, parse_mode="MarkdownV2")


def workout_completed():

    send_message("Great job 💪 You're done!")

    # send workout report
    # the report consists of: total rep amount | average reps per set for ever exercise.
    report = "📝 *Workout Report*\n\n"
    workout = get_from_redis("WORKOUT")
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

    if not message:
        send_message(
            "How are you enjoying my service? "
            "Is there anything you would like to me to include, or improve upon?"
            "\n\nI am constantly trying to get better, so please pour your heart out!"
        )
        set_to_redis("WAITING_FOR_INPUT", True)
        set_to_redis("WAITING_FOR_USER_FEEDBACK", True)
    else:
        # received message. post it to feedback node in firebase
        feedback_object = {
            'user_id': message.from_user.id,
            'feedback_text': message.text
        }
        add_feedback_to_database(feedback_object)

        send_message("Thanks a lot for your feedback! 😊")
        set_to_redis("WAITING_FOR_INPUT", False)
        set_to_redis("WAITING_FOR_USER_FEEDBACK", False)


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

    retrieved_key = CONN.get(key)

    if retrieved_key in ("True", "False"):
        return retrieved_key == "True"

    if retrieved_key == "None" or retrieved_key is None:
        return None

    if retrieved_key.isnumeric():
        return int(retrieved_key)

    if retrieved_key.startswith("{") and retrieved_key.endswith("}"):
        return jsonpickle.loads(retrieved_key)

    return retrieved_key


def delete_from_redis(key):
    CONN.delete(key)


def set_to_redis(key, value):
    if type(value) == dict:
        value = jsonpickle.dumps(value)

    elif type(value) == bool:
        value = str(value)

    elif value is None:
        value = "None"

    CONN.set(key, value)


def push_to_redis(key, value):
    CONN.rpush(key, value)


def set_list_index_to_redis(key, index, value):
    CONN.lset(key, index, value)


def pop_from_redis(key, pop_type):
    if pop_type == "left":
        CONN.lpop(key)
    if pop_type == "right":
        CONN.rpop(key)


def increment_in_redis(key):
    CONN.incr(key)


def decrement_in_redis(key):
    CONN.decr(key)


if __name__ == "__main__":
    reset_state()
    BOT.polling()
