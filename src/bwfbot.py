import telebot

from telebot.types import ReplyKeyboardRemove

from models.user import User
from models.exercise import Exercise
from models.workout import Workout
from markups import *

from time import sleep
from copy import deepcopy
from uuid import uuid4
from yaml import load, FullLoader

# configuration
with open("../config.yml", "r") as fp:
	CONFIG = load(fp, FullLoader)

TOKEN = CONFIG["telegram"]["token"]

BOT = telebot.TeleBot(TOKEN)
USER = User()
CHAT_ID = None
MESSAGES = []

global \
	WAITING_FOR_INPUT, \
	WORKOUT, \
	WORKOUT_INDEX, \
	WORKOUT_ID, \
	WAITING_FOR_WORKOUT_TITLE, \
	EXERCISE, \
	WAITING_FOR_EXERCISE_NAME, \
	WAITING_FOR_EXERCISE_VIDEO_LINK, \
	WAITING_FOR_MUSCLES_WORKED, \
	WAITING_FOR_SETUP_DONE, \
	WAITING_FOR_REP_COUNT, \
	CURRENT_EXERCISE_INDEX, \
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
		WORKOUT_ID, \
		WAITING_FOR_WORKOUT_TITLE, \
		EXERCISE, \
		WAITING_FOR_EXERCISE_NAME, \
		WAITING_FOR_EXERCISE_VIDEO_LINK, \
		WAITING_FOR_MUSCLES_WORKED, \
		WAITING_FOR_SETUP_DONE, \
		WAITING_FOR_REP_COUNT, \
		CURRENT_EXERCISE_INDEX, \
		RESET_STATE

	WAITING_FOR_INPUT = False

	WORKOUT = Workout()
	WORKOUT_INDEX = None
	WORKOUT_ID = -1
	WAITING_FOR_WORKOUT_TITLE = False

	EXERCISE = Exercise()
	WAITING_FOR_EXERCISE_NAME = False
	WAITING_FOR_EXERCISE_VIDEO_LINK = False
	WAITING_FOR_MUSCLES_WORKED = False
	WAITING_FOR_SETUP_DONE = False

	WAITING_FOR_REP_COUNT = False
	CURRENT_EXERCISE_INDEX = 0

	RESET_STATE = False


# ----------------- HANDLERS --------------------
@BOT.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
	"""
	handles all inline keyboard responses
	:param call
	"""
	global \
		WORKOUT_INDEX, \
		WORKOUT_ID, \
		RESET_STATE

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
		add_exercise(call=call)

	elif call.data == "explore_community":
		handle_explore_community()

	elif call.data == "request_community":
		handle_community_request(call)

	elif call.data == "start_menu":
		show_start_options(call=call)

	elif call.data == "exercise_added":
		exercise_added(call)

	elif call.data == "list_workouts_for_workout_details":
		handle_view_workout(call)

	elif call.data.startswith("START_WORKOUT:"):
		WORKOUT_ID = call.data.replace("START_WORKOUT:", "")
		temp_workout = [w for w in USER.saved_workouts if w.id == WORKOUT_ID][0]
		WORKOUT_INDEX = USER.saved_workouts.index(temp_workout)

		if temp_workout.exercises:
			send_edited_message("Let's go! 💪", call.message.id)
			do_workout()
		else:
			send_edited_message(
				f"{temp_workout.title} has no exercises. Do you want to add some?",
				call.message.id,
				reply_markup=add_exercise_markup())

	elif call.data.startswith("DELETE_WORKOUT:"):
		WORKOUT_ID = call.data.replace("DELETE_WORKOUT:", "")
		delete_workout(call=call, workout_id=WORKOUT_ID)

	elif call.data.startswith("CONFIRM_DELETE_WORKOUT:"):
		WORKOUT_ID = call.data.replace("CONFIRM_DELETE_WORKOUT:", "")
		workout_title = [w.title for w in USER.saved_workouts if w.id == WORKOUT_ID][0]
		if len(USER.saved_workouts) == 1:
			USER.saved_workouts = []
		else:
			USER.saved_workouts = [w for w in USER.saved_workouts if w.id != WORKOUT_ID]
		send_edited_message(f"Done! {workout_title} is gone from your saved workouts.", call.message.id)

	elif call.data.startswith("ABORT_DELETE_WORKOUT:"):
		workout_id = call.data.replace("ABORT_DELETE_WORKOUT:", "")
		workout_title = [w.title for w in USER.saved_workouts if w.id == workout_id][0]
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
			send_message("Please resend your command.", reply_markup=ReplyKeyboardRemove())
		else:
			send_edited_message("Okay, I'll not cancel the running workout.", call.message.id)


# handle /start command
@BOT.message_handler(commands=["start"])
def initialize(message):
	global USER
	global CHAT_ID
	global RESET_STATE
	global WORKOUT

	MESSAGES.append(message)
	remove_inline_replies()

	if WORKOUT.running and not RESET_STATE:
		confirm_reset_state()
		return

	# reset application state for every new session
	reset_state()

	CHAT_ID = message.chat.id
	# TODO: USER = get_user_from_id(message.from_user.id)
	is_new_user = False
	if not USER.id:
		# new account. create new user profile
		is_new_user = True
		USER = User(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
	show_start_options(is_new_user)


@BOT.message_handler(commands=["begin"])
def begin_workout(message):
	MESSAGES.append(message)
	remove_inline_replies()

	if WORKOUT.running and not RESET_STATE:
		confirm_reset_state()
		return

	reset_state()
	choose_workout()


@BOT.message_handler(commands=["create"])
def create_workout(message):
	MESSAGES.append(message)
	remove_inline_replies()

	if WORKOUT.running and not RESET_STATE:
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
	global CURRENT_EXERCISE_INDEX

	MESSAGES.append(message)

	if WAITING_FOR_EXERCISE_VIDEO_LINK:
		# user skipped the video link entry
		add_exercise(message=message, message_type="EXERCISE_VIDEO_LINK", skip_setting=True)

	elif WAITING_FOR_MUSCLES_WORKED:
		# user skipped the muscles worked entry
		add_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED", skip_setting=True)

	elif WAITING_FOR_REP_COUNT and CURRENT_EXERCISE_INDEX != len(WORKOUT.exercises) - 1:
		# display the next exercise in the workout to the user
		# if the user is on their last exercise, this logic is handled by the /done handler instead
		CURRENT_EXERCISE_INDEX += 1
		do_workout()


# handle /done command
@BOT.message_handler(commands=["done"])
def finish(message):
	global \
		WAITING_FOR_INPUT, \
		WAITING_FOR_REP_COUNT, \
		CURRENT_EXERCISE_INDEX

	MESSAGES.append(message)

	if WAITING_FOR_REP_COUNT and CURRENT_EXERCISE_INDEX == len(WORKOUT.exercises) - 1:
		# user is done with their workout. End workout and add it to their completed workouts
		WORKOUT.running = False
		USER.completed_workouts.append(WORKOUT)

		# reset exercise index
		CURRENT_EXERCISE_INDEX = 0  # reset

		# deactivate user input handling
		WAITING_FOR_REP_COUNT = False
		WAITING_FOR_INPUT = False

		workout_completed()


# handle clear request
@BOT.message_handler(commands=["clear"])
def clear_dialog(message):
	global MESSAGES

	MESSAGES.append(message)

	if WORKOUT.running and not RESET_STATE:
		confirm_reset_state()
		return

	reset_state()

	send_message("Clearing chat...")
	sleep(1.5)
	while MESSAGES:
		BOT.delete_message(CHAT_ID, MESSAGES[0].id)
		MESSAGES = MESSAGES[1:]


@BOT.message_handler(commands=["delete"])
def handle_delete_workout(message):
	MESSAGES.append(message)
	remove_inline_replies()

	if WORKOUT.running and not RESET_STATE:
		confirm_reset_state()
		return

	reset_state()

	if USER.saved_workouts:
		message_text = \
			"Which workout would you like to delete?\n\n" \
			"(Note: this doesn't affect your already completed workouts, so no worries)"

		send_message(message_text, reply_markup=delete_workout_markup(USER.saved_workouts))
	else:
		send_message("You don't have any stored workouts.")


@BOT.message_handler(commands=["view"])
def view_workout(message):
	MESSAGES.append(message)
	remove_inline_replies()

	handle_view_workout()


# only if bot is expecting user input
# needs to be the very last handler!!
@BOT.message_handler(func=lambda message: message.text)
def handle_user_input(message):
	"""
	handles actual user input written to chat.
	similar to func proceed_to_next(), the context is derived from the global variables
	:param message:
	:return:
	"""
	# log all message ids
	MESSAGES.append(message)

	# only handle if the bot is also waiting for user input
	if WAITING_FOR_INPUT:
		# create workout
		if WAITING_FOR_WORKOUT_TITLE:
			get_workout_title_from_input(message=message)
		# create exercise
		elif WAITING_FOR_EXERCISE_NAME:
			add_exercise(message=message, message_type="EXERCISE_NAME")
		elif WAITING_FOR_EXERCISE_VIDEO_LINK:
			add_exercise(message=message, message_type="EXERCISE_VIDEO_LINK")
		elif WAITING_FOR_MUSCLES_WORKED:
			add_exercise(message=message, message_type="EXERCISE_MUSCLES_WORKED")
		# add reps to exercise
		elif WAITING_FOR_REP_COUNT:
			if message.text.isnumeric():
				do_workout(True, message)


# ----------------- FUNCTIONS ------------------

def show_start_options(is_new_user=False, call=None):
	if call:
		message_text = \
			"What can I help you with?\n\n" \
			"Type '/' to see all commands you can give me."
		send_edited_message(message_text, call.message.id, reply_markup=start_options_markup())
	else:
		message_text = f'''
				{"Welcome" if is_new_user else "Welcome back"}, {USER.first_name}. What would you like to do today?
				\nType '/' to see all commands you can give me.'''

		send_message(message_text.strip(), reply_markup=start_options_markup())


def send_message(message_text, reply_markup=None, parse_mode=""):
	global MESSAGES

	sent_message = BOT.send_message(
					CHAT_ID,
					message_text,
					reply_markup=reply_markup, disable_web_page_preview=True,
					parse_mode=parse_mode)

	MESSAGES.append(sent_message)


def send_edited_message(message_text, previous_message_id, reply_markup=None, parse_mode=""):
	global MESSAGES

	message_to_edit = None
	message_index = None

	for ix, message in enumerate(MESSAGES):
		if message.id == previous_message_id:
			message_to_edit = message
			message_index = ix
			break

	MESSAGES[message_index] = BOT.edit_message_text(
								message_text,
								CHAT_ID,
								message_to_edit.id,
								reply_markup=reply_markup,
								disable_web_page_preview=True,
								parse_mode=parse_mode)


def choose_workout(call=None, comes_from=None):
	if USER.saved_workouts:
		message_text = "Which workout routine would you like to start?"

		if comes_from == "add_another_exercise":
			reply_markup = list_workouts_markup(USER.saved_workouts, comes_from="add_another_exercise")
		else:
			reply_markup = list_workouts_markup(USER.saved_workouts)

		if call:
			send_edited_message(
				message_text,
				call.message.id,
				reply_markup=reply_markup)
		else:
			send_message(
				message_text,
				reply_markup=reply_markup
			)
	else:
		if call:
			message_text = "You don't have any stored workouts. Would you like to create a new one?"
			send_edited_message(
				message_text,
				call.message.id,
				reply_markup=create_workout_answer_markup())
		else:
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
	global WAITING_FOR_INPUT, WAITING_FOR_WORKOUT_TITLE

	if not message:
		message_text = '''New workout\n\nWhat would you like to name your workout?'''
		if call:
			send_edited_message(message_text, call.message.id)
		else:
			send_message(message_text)

		WAITING_FOR_INPUT = True
		WAITING_FOR_WORKOUT_TITLE = True

	else:
		# received input, set global flags back to false
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
	new_workout = Workout(workout_title, message.from_user.id)
	USER.saved_workouts.append(new_workout)
	message_text = f'''New workout\n\n{workout_title} has been created! Now let's add some exercises.'''
	send_message(message_text, reply_markup=add_exercise_markup())


def add_exercise(call=None, message=None, message_type="", skip_setting=False):
	"""
	in a similar vein to get_workout_title(), this function gets called multiple times in order to store user input
	:param call
	:param message:
	:param message_type
	:param skip_setting
	:return:
	"""

	global \
		EXERCISE, \
		WAITING_FOR_INPUT

	# flags that direct the conversation. Only one of them should be True at a time!
	global \
		WAITING_FOR_EXERCISE_NAME, \
		WAITING_FOR_EXERCISE_VIDEO_LINK, \
		WAITING_FOR_MUSCLES_WORKED

	WAITING_FOR_INPUT = True

	if not message and call:
		message_text = "Please give the exercise a name."
		send_edited_message(message_text, call.message.id)
		WAITING_FOR_EXERCISE_NAME = True
	else:
		if message_type == "EXERCISE_NAME":
			EXERCISE = Exercise()
			EXERCISE.name = message.text
			WAITING_FOR_EXERCISE_NAME = False
			# retrieved exercise name. Ask for youtube link
			send_message(
				"Great!"
				"\nWould you like to add a Youtube link associated with this exercise? If not, simply click /next.")
			WAITING_FOR_EXERCISE_VIDEO_LINK = True

		elif message_type == "EXERCISE_VIDEO_LINK":
			WAITING_FOR_EXERCISE_VIDEO_LINK = False
			if not skip_setting:
				EXERCISE.video_link = message.text

			# muscles worked here
			send_message(
				"How about a brief description of muscles worked, "
				"like this: 'chest, triceps, front delts'?\n(Or click /next to continue)")
			WAITING_FOR_MUSCLES_WORKED = True

		elif message_type == "EXERCISE_MUSCLES_WORKED":
			WAITING_FOR_MUSCLES_WORKED = False
			if not skip_setting:
				muscles_worked = [muscle.strip().capitalize() for muscle in message.text.split(",")]
				EXERCISE.muscles_worked = muscles_worked

			# done. Add workout to users workouts.
			WAITING_FOR_INPUT = False

			# default location to add exercise is the most recently added workout
			# unless specified (WORKOUT_INDEX not None)
			workout_index = WORKOUT_INDEX if type(WORKOUT_INDEX) is int else -1
			USER.saved_workouts[workout_index].exercises.append(EXERCISE)

			exercise_added()


def exercise_added(call=None):
	workout_index = WORKOUT_INDEX if type(WORKOUT_INDEX) is int else -1
	message_text = \
		f"Exercise summary:\n\n" \
		f"{str(EXERCISE)}\n"
	if call:
		send_edited_message(message_text, call.message.id, parse_mode="MarkdownV2")
	else:
		send_message(message_text, parse_mode="MarkdownV2")

	confirmation = \
		f"Added {EXERCISE.name} to {USER.saved_workouts[workout_index].title}!\n" \
		f"Would you like to add another exercise?"

	send_message(confirmation, reply_markup=add_another_exercise_markup())


def do_workout(new_rep_entry=False, message=None):
	"""
	start workout
	:param new_rep_entry:
	:param message:
	:return:
	"""
	global \
		WORKOUT, \
		WAITING_FOR_REP_COUNT, \
		WAITING_FOR_INPUT

	if not WORKOUT.running:
		# only happens once (when the workout gets started initially)
		WORKOUT = deepcopy([w for w in USER.saved_workouts if w.id == WORKOUT_ID][0])
		# give the new workout a new id
		WORKOUT.id = str(uuid4())
		WORKOUT.running = True

	# create a list of exercises. Whenever the user has completed the sets for that exercise, increment index parameter
	exercises_in_workout = WORKOUT.exercises
	current_exercise = exercises_in_workout[CURRENT_EXERCISE_INDEX]

	if not new_rep_entry:
		if current_exercise == WORKOUT.exercises[-1]:
			# user is performing the last exercise
			message_text = \
				f"Almost done\\!\n" \
				f"{str(current_exercise)}\n" \
				f"Send me the rep count for each set\\. Once you're done, click /done\\."

		else:
			# the user is beginning the exercise. Show the exercise info
			message_text = \
				f"{str(current_exercise)}\n" \
				f"Send me the rep count for each set\\. Once you're done, click /next\\."

		send_message(message_text, reply_markup=number_pad_markup(), parse_mode="MarkdownV2")

		WAITING_FOR_REP_COUNT = True
		WAITING_FOR_INPUT = True

	else:
		rep_count = int(message.text)
		WORKOUT.exercises[CURRENT_EXERCISE_INDEX].reps.append(rep_count)


def workout_completed():
	send_message("Great job 💪 You're done!")

	# send workout report
	# the report consists of: total rep amount | average reps per set for ever exercise.
	report = "📊 *Workout Report*\n\n"
	for exercise in WORKOUT.exercises:
		total = sum(exercise.reps)
		sets = str(len(exercise.reps))
		average = "0" if total == 0 else str(round(total / len(exercise.reps), 2)).replace(".", "\\.")
		print(total, sets, average)
		report += f"*{exercise.name}*\nTotal: {total}\nNo\\. of sets: {sets}\nAverage per set: {average}\n\n"

	# number pad custom keyboard is not needed anymore
	send_message(report, reply_markup=ReplyKeyboardRemove(), parse_mode="MarkdownV2")


def delete_workout(call, workout_id):
	workout_title = [w.title for w in USER.saved_workouts if w.id == workout_id][0]
	send_edited_message(
		f"Are you sure you want to delete {workout_title}?",
		call.message.id, reply_markup=delete_workout_confirmation_markup(workout_id))


def handle_view_workout(call=None):
	if USER.saved_workouts:
		if call:
			send_edited_message(
				"Which workout would you like to view?",
				call.message.id,
				reply_markup=view_workout_details_markup(USER.saved_workouts))
		else:
			send_message(
				"Which workout would you like to view?",
				reply_markup=view_workout_details_markup(USER.saved_workouts))
	else:
		send_message("You don't have any stored workouts.")


def show_workout_details(call, workout_id):
	workout = [w for w in USER.saved_workouts if w.id == workout_id][0]
	send_edited_message(
		str(workout),
		call.message.id,
		parse_mode="MarkdownV2",
		reply_markup=return_to_view_workout_details_markup())


def remove_inline_replies():
	# since user interaction has proceeded, remove any previous inline reply markups.
	for ix, message in enumerate(MESSAGES):
		if type(message.reply_markup) is telebot.types.InlineKeyboardMarkup:
			send_edited_message(message.text, message.id, reply_markup=None)


def handle_explore_community():
	pass


def handle_community_request(call):
	# would you like to explore the community?
	# yes -> explore community
	# no -> what can I help you with? show commands
	message_text = "Would you like to explore workouts created by the bodyweight fitness community?"
	send_edited_message(message_text, call.message.id, reply_markup=explore_community_workouts_answer_markup())


def send_report():
	pass


if __name__ == "__main__":
	reset_state()
	BOT.polling()
