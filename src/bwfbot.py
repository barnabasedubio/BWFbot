import telebot
import time

from user import User
from exercise import Exercise
from workout import Workout

# configuration
with open("../token.txt", "r", encoding="utf8") as fp:
	TOKEN = fp.read()

# global variables
BOT = telebot.TeleBot(TOKEN)
USER = None
CHAT_ID = None
MESSAGE_IDS = []

WAITING_FOR_INPUT = False

WAITING_FOR_WORKOUT_TITLE = False
WORKOUT_TITLE = ""
WORKOUT = Workout(None, None)
EXERCISE = None

WAITING_FOR_EXERCISE_NAME = False
WAITING_FOR_EXERCISE_VIDEO_LINK = False
WAITING_FOR_MUSCLES_WORKED = False
WAITING_FOR_REP_RANGE = False
WAITING_FOR_SETUP_DONE = False


# ----------------- MARKUPS --------------------

def add_exercise_markup():
	markup = telebot.types.InlineKeyboardMarkup()
	markup.add(
		telebot.types.InlineKeyboardButton("Add Exercise", callback_data="add_exercise")
	)
	return markup


def explore_community_workouts_answer_markup():
	markup = telebot.types.InlineKeyboardMarkup()
	markup.add(
		telebot.types.InlineKeyboardButton("Yes", callback_data="explore_community"),
		telebot.types.InlineKeyboardButton("No", callback_data="display_commands"),
	)
	return markup


def create_workout_answer_markup():
	markup = telebot.types.InlineKeyboardMarkup()
	markup.add(
		telebot.types.InlineKeyboardButton("Yes", callback_data="create_workout"),
		telebot.types.InlineKeyboardButton("No", callback_data="request_community"),
	)
	return markup


def list_workouts_markup(workout_titles):
	markup = telebot.types.InlineKeyboardMarkup()
	for workout_title in workout_titles:
		markup.add(telebot.types.InlineKeyboardButton(workout_title, callback_data=workout_title))
	return markup


# number pad used to record reps
def number_pad_markup():
	number_pad = telebot.types.ReplyKeyboardMarkup(
		resize_keyboard=False,
		one_time_keyboard=False
	)
	# * operator: spread the entries
	number_pad.add(*[str(x) for x in range(1, 16)])
	return number_pad


def start_options_markup():
	markup = telebot.types.InlineKeyboardMarkup()
	markup.add(telebot.types.InlineKeyboardButton("Start one of my workouts", callback_data="start_workout"))
	markup.add(telebot.types.InlineKeyboardButton("Create a new workout", callback_data="create_workout"))
	markup.add(telebot.types.InlineKeyboardButton("Explore the community", callback_data="explore_community"))
	markup.add(telebot.types.InlineKeyboardButton("Something else", callback_data="display_commands"))
	return markup


# ----------------- HANDLERS --------------------


# handle /start command
@BOT.message_handler(commands=["start"])
def start(message):
	global USER
	global CHAT_ID

	CHAT_ID = message.chat.id
	# TODO: user = get_user_from_id(message.from_user.id)
	is_new_user = False
	if not USER:
		# new account. create new user profile
		is_new_user = True
		new_user = User(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
		USER = new_user

	welcome_text = f'''\n\n{"Welcome" if is_new_user else "Welcome back"}, {USER.first_name}. What would you like to do today?
	\n
	Click /commands to get a comprehensive view of all possible commands you can give me.'''

	BOT.reply_to(message, welcome_text, reply_markup=start_options_markup())
	

@BOT.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
	if call.data == "start_workout":
		handle_start_workout(call)

	elif call.data == "create_workout":
		get_workout_title()

	elif call.data == "add_exercise":
		add_exercise()

	elif call.data == "explore_community":
		handle_explore_community(call)

	elif call.data == "request_community":
		handle_community_request(call)

	elif call.data == "display_commands":
		handle_commands_request(call)


# handle /next command
@BOT.message_handler(commands=["next"])
def proceed_to_next(message):
	if WAITING_FOR_EXERCISE_VIDEO_LINK:
		add_exercise(message, "EXERCISE_VIDEO_LINK", True)

	elif WAITING_FOR_MUSCLES_WORKED:
		add_exercise(message, "EXERCISE_MUSCLES_WORKED", True)


# handle /done command
@BOT.message_handler(commands=["done"])
def finish(message):
	if WAITING_FOR_REP_RANGE:
		add_exercise(message, "EXERCISE_TARGET_REP_RANGE", True)


# handle rep messages
@BOT.message_handler(func=lambda message: message.text.isnumeric())
def handle_rep(message):
	pass  # TODO: add rep to exercise


# handle clear request
@BOT.message_handler(commands=["clear"])
def clear_dialog(message):
	pass  # TODO


# only if bot is expecting user input
@BOT.message_handler(func=lambda message: message.text and WAITING_FOR_INPUT)
def handle_user_input(message):
	if WAITING_FOR_WORKOUT_TITLE:
		get_workout_title(message)
	elif WAITING_FOR_EXERCISE_NAME:
		add_exercise(message, "EXERCISE_NAME")
	elif WAITING_FOR_EXERCISE_VIDEO_LINK:
		add_exercise(message, "EXERCISE_VIDEO_LINK")
	elif WAITING_FOR_MUSCLES_WORKED:
		add_exercise(message, "EXERCISE_MUSCLES_WORKED")
	elif WAITING_FOR_REP_RANGE:
		add_exercise(message, "EXERCISE_TARGET_REP_RANGE")


# ----------------- FUNCTIONS ------------------


def handle_start_workout(call):
	# check if user has any saved workouts
	if USER.created_workouts:
		# display a list of all stored user workouts
		workout_titles = [workout.title for workout in USER.created_workouts]
		message_text = "Which workout routine would you like to start?"
		BOT.send_message(CHAT_ID, message_text, reply_markup=list_workouts_markup(workout_titles))

	else:
		# user has no saved workouts. ask if user wants to create one
		# yes -> create workout
		# no -> back to start options
		message_text = "You don't have any stored workouts. Would you like to create a new one?"
		BOT.send_message(CHAT_ID, message_text, reply_markup=create_workout_answer_markup())


def get_workout_title(message=None):
	"""
	This function gets called twice. Once upon creating a new workout, and once after the
	user has typed in the workout name. The initial call has no message value, thus the first
	condition gets executed. After user input has been handled by handle_workout_title()
	and this function gets called again, it enters the else block, with the received
	message from the input handler.
	This method allows the bot to imitate waiting for user input.
	:param message:
	:return:
	"""
	global WAITING_FOR_INPUT, WAITING_FOR_WORKOUT_TITLE

	if not message:
		message_text = '''New workout\n\nWhat would you like to name your workout?'''
		BOT.send_message(CHAT_ID, message_text)
		WAITING_FOR_INPUT = True
		WAITING_FOR_WORKOUT_TITLE = True
	else:
		# received input, set global flags back to false
		WAITING_FOR_INPUT = False
		WAITING_FOR_WORKOUT_TITLE = False
		set_workout(message)


def set_workout(message):
	workout_title = message.text
	new_workout = Workout(workout_title, message.from_user.id)
	USER.created_workouts.append(new_workout)
	message_text = f'''New workout\n\n{workout_title} has been created! Now let's add some exercises.'''
	BOT.send_message(CHAT_ID, message_text, reply_markup=add_exercise_markup())


def add_exercise(message=None, message_type="", skip_setting=False):
	"""
	in a similar vein to get_workout_title(), this function gets called multiple times in order to store user input
	:param message:
	:param message_type
	:param skip_setting
	:return:
	"""

	global EXERCISE

	# global flag that allows the bot to listen to user input
	global WAITING_FOR_INPUT
	# global flags that direct the conversation. Only one of them should be True at a time!
	global WAITING_FOR_EXERCISE_NAME, \
		WAITING_FOR_EXERCISE_VIDEO_LINK, \
		WAITING_FOR_MUSCLES_WORKED, \
		WAITING_FOR_REP_RANGE, \
		WAITING_FOR_SETUP_DONE

	WAITING_FOR_INPUT = True

	if not message:
		message_text = "Please give the exercise a name."
		BOT.send_message(CHAT_ID, message_text)
		WAITING_FOR_EXERCISE_NAME = True
	else:
		if message_type == "EXERCISE_NAME":
			EXERCISE = Exercise()
			EXERCISE.name = message.text
			WAITING_FOR_EXERCISE_NAME = False
			# retrieved exercise name. Ask for youtube link
			BOT.send_message(CHAT_ID, "Great! \nWould you like to add a Youtube link associated with this exercise? If not, simply click /next.")
			WAITING_FOR_EXERCISE_VIDEO_LINK = True

		elif message_type == "EXERCISE_VIDEO_LINK":
			WAITING_FOR_EXERCISE_VIDEO_LINK = False
			if not skip_setting:
				EXERCISE.video_link = message.text

			# muscles worked here
			BOT.send_message(CHAT_ID, "How about a brief description of muscles worked, for example  'chest, triceps, front delts'?\n(Or click /next to continue)")
			WAITING_FOR_MUSCLES_WORKED = True

		elif message_type == "EXERCISE_MUSCLES_WORKED":
			WAITING_FOR_MUSCLES_WORKED = False
			if not skip_setting:
				EXERCISE.muscles_worked = message.text.split(",")

			# rep range here
			BOT.send_message(CHAT_ID, "Almost done! If you would like to add the target rep range (e.g '5-7') here, go ahead! \nIf not, click /done.")
			WAITING_FOR_REP_RANGE = True

		elif message_type == "EXERCISE_TARGET_REP_RANGE":
			WAITING_FOR_REP_RANGE = False
			if not skip_setting:
				rep_range = [x.strip() for x in message.text.split("-")]
				EXERCISE.target_rep_range = rep_range

			# done. Add workout to users workouts.
			message_text = f'''
				\n\nExercise summary:\n
				Name: {EXERCISE.name}\n\n
				Video: {EXERCISE.video_link if EXERCISE.video_link else "empty"}\n\n
				Muscles worked: {EXERCISE.muscles_worked if EXERCISE.muscles_worked else "empty"}\n\n
				Target rep range: {EXERCISE.target_rep_range if EXERCISE.target_rep_range else "empty"}\n
			'''
			# if user.created_workouts is only 1, add automatically
			# else
			# add {name} to {last workout in user.created_workouts} ?
			# yes -> add
			# choose another workout -> display list of workout to add
			BOT.send_message(CHAT_ID, message_text)

			if len(USER.created_workouts) == 1:
				USER.created_workouts[0].exercises.append(EXERCISE)
				BOT.send_message(CHAT_ID, "Added exercise to workout!")

			else:
				pass

			WAITING_FOR_INPUT = False

def handle_explore_community(call):
	pass


def handle_community_request(call):
	# would you like to explore the community?
	# yes -> explore community
	# no -> what can I help you with? show commands
	message_text = "Would you like to explore workouts created by the bodyweight fitness community?"
	BOT.send_message(CHAT_ID, message_text, reply_markup=explore_community_workouts_answer_markup())


def handle_commands_request(call):
	# display a chat saying 'What can I help you with?' Followed by the list of possible commands.
	BOT.send_message(CHAT_ID, "What can I help you with?")
	BOT.send_message(CHAT_ID, "commands list is currently being worked on.")
	pass


def do_workout(index):
	pass


def send_report():
	pass


BOT.polling()
