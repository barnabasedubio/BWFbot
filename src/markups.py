from telebot.types import \
    InlineKeyboardMarkup, \
    InlineKeyboardButton, \
    ReplyKeyboardMarkup


def start_options_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Start one of my workouts", callback_data="choose_workouts"))
    markup.add(InlineKeyboardButton("Create a new workout", callback_data="create_workout"))
    markup.add(InlineKeyboardButton("Explore the community", callback_data="explore_community"))
    return markup


def reset_state_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Yes", callback_data="RESET_STATE:YES"),
        InlineKeyboardButton("No", callback_data="RESET_STATE:NO"),
    )
    return markup


def add_exercise_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Add exercise", callback_data="add_exercise"))
    markup.add(InlineKeyboardButton("Go back", callback_data="choose_workouts"))
    return markup


def add_another_exercise_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Add another exercise", callback_data="add_exercise"))
    markup.add(InlineKeyboardButton("Start workout", callback_data="exercise_menu:choose_workouts"))
    markup.add(InlineKeyboardButton("Go to main menu", callback_data="start_menu"))
    return markup


def create_workout_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Yes", callback_data="create_workout"),
        InlineKeyboardButton("No", callback_data="request_community"),
    )
    return markup


def list_workouts_markup(workouts, comes_from=None):
    """
    workouts is a dict containing firebase node ids which in turn contain a workout object
    :param workouts:
    :param comes_from:
    :return:
    """
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"START_WORKOUT:{workout['id']}"))
    if comes_from == "add_another_exercise":
        markup.add(InlineKeyboardButton("Go back", callback_data="exercise_added"))
    else:
        markup.add(InlineKeyboardButton("Go back", callback_data="start_menu"))
    return markup


def view_workout_details_markup(workouts):
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"VIEW_WORKOUT:{workout['id']}"))
    return markup


def return_to_view_workout_details_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Go back", callback_data="list_workouts_for_workout_details"))
    return markup


def delete_workout_markup(workouts):
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"DELETE_WORKOUT:{workout['id']}"))
    return markup


def delete_workout_confirmation_markup(workout_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Yes", callback_data=f"CONFIRM_DELETE_WORKOUT:{workout_id}"),
        InlineKeyboardButton("No", callback_data=f"ABORT_DELETE_WORKOUT:{workout_id}")
    )
    return markup


def explore_community_workouts_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Yes", callback_data="explore_community"),
        InlineKeyboardButton("No", callback_data="start_menu"),
    )
    return markup


def number_pad_markup():
    # User uses this keyboard to store their reps after each set
    number_pad = ReplyKeyboardMarkup(
        resize_keyboard=False,
        one_time_keyboard=False
    )
    # * operator: spread the entries
    number_pad.add(*[str(x) for x in range(1, 16)])
    return number_pad
