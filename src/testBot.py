import telebot

bot = telebot.TeleBot("TOKEN COMES HERE")


# handle /start command
@bot.message_handler(commands=["start", "help"])
def handle_command(message):
	user = message.from_user.first_name
	bot.reply_to(message, f"Hello, {user}. I am your bot. Please treat me nicely.")

RKM = telebot.types.ReplyKeyboardMarkup(
	resize_keyboard=False,
	one_time_keyboard=False
)

RKM.add(*[str(x) for x in range(1,16)])

# handle all messages, echo message back to users
@bot.message_handler(commands=["star"])
def return_numpad(message):
	bot.reply_to(message,"Write down your reps per set, click /star to try again", reply_markup=RKM)

bot.polling()