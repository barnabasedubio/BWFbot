import telebot
import time

from user import User
from exercise import Exercise
from workout import Workout

# configuration
TOKEN = "1595750252:AAGXPcRE-4TkdtV8YKpG1CRyQwYNjghzA4c"
bot = telebot.TeleBot(TOKEN)

current_workout_index = 0
chat_id = None
message_ids = []
done = False
user_first_name = ""

number_pad = telebot.types.ReplyKeyboardMarkup(
	resize_keyboard=False,
	one_time_keyboard=False
)
number_pad.add(*[str(x) for x in range(1,16)])

def generate_inline_keyboard_markup():
	markup = telebot.types.InlineKeyboardMarkup()
	markup.add(telebot.types.InlineKeyboardButton("Start one of my workouts", callback_data="start")
	markup.add(telebot.types.InlineKeyboardButton("Create a new workout", callback_data="create"))
	markup.add(telebot.types.InlineKeyboardButton("Explore the community", callback_data="explore"),)
	return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
	bot.answer_callback_query(call.id, "Okay!")

# handle /start command
@bot.message_handler(commands=["start"])
def start(message):

	user = None # TODO: user = get_user_from_id(message.from_user.id)
	is_new_user = False
	if not user:
		# new account. create new user profile
		is_new_user = True
		new_user = User(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
		user = new_user

	welcome_text = f'''{"Welcome" if is_new_user else "Welcome back"}, {user.first_name}. What would you like to do today?
	\n
	If you want, you can click /commands to get a comprehensive view of all possible commands you can give me'''

	start_options_keyboard = telebot.types.InlineKeyboardMarkup()
	start_options_keyboard.add("Test1, Test2, Test3")

	bot.reply_to(message, welcome_text, reply_markup=generate_inline_keyboard_markup())
	



	# --------------------- previous stuff -----------------------
	# global chat_id
	# global user_first_name

	# chat_id = message.chat.id
	# message_ids.append(message.id)
	# user_first_name = message.from_user.first_name
	# reply_message = f"Alright, {user_first_name}, lets begin!"
	# reply = bot.reply_to(message, reply_message)
	# message_ids.append(reply.id)

	# do_workout(current_workout_index)
	

def do_workout(index):
	exercise_state = "first" if current_workout_index == 0 else "last" if current_workout_index == len(workouts) - 1 else "next"
	message_content = f"Our {exercise_state} exercise is {workouts[current_workout_index]}. \n\n Please use the number pad " \
					"To record your reps for each set. Once done, click /next for the next exercise."
	sent_message = bot.send_message(chat_id, message_content, reply_markup=number_pad)
	message_ids.append(sent_message.id)


# handle /next command
@bot.message_handler(commands=["next"])
def send_next_workout(message):
	global current_workout_index
	message_ids.append(message.id)
	if (current_workout_index == len(workouts) -1):
		send_report()
	else:
		current_workout_index += 1
		do_workout(current_workout_index)

# handle rep messages
@bot.message_handler(func=lambda message: message.text.isnumeric())
def handle_rep(message):
	message_ids.append(message.id)
	current_workout = workouts[current_workout_index]
	if not current_workout in reps:
		reps[current_workout] = []
	reps[current_workout].append(int(message.text))


def send_report():
	global done
	if (not done):
		message_content = f''' Congrats! You did it!
						You did a total of {sum(reps["Push ups"])} push ups, {sum(reps["Dips"])} dips, {sum(reps["Rows"])} rows, and {sum(reps["Squats"])} Squats!!
						'''
		
		sent_message = bot.send_message(chat_id, message_content)
		message_ids.append(sent_message.id)
		done = True

	else:
		 sent_message = bot.send_message(chat_id, f"I'm sorry {user_first_name}, I'm afraid I cannot do that.")
		 message_ids.append(sent_message.id)


# handle clear request
@bot.message_handler(commands=["clear"])
def clear_dialog(message):
	sent_message = bot.send_message(chat_id, "Clearing chat...")
	message_ids.append(sent_message.id)
	time.sleep(1.5)
	for message_id in message_ids:
		bot.delete_message(chat_id, message_id)


bot.polling()