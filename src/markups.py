from telebot.types import \
    KeyboardButton, \
    InlineKeyboardMarkup, \
    InlineKeyboardButton, \
    ReplyKeyboardMarkup


def start_options_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💪 Start one of my workouts", callback_data="choose_workouts"))
    markup.add(InlineKeyboardButton("✳️ Create a new workout", callback_data="create_workout"))
    markup.add(InlineKeyboardButton("👥 Explore community workouts", callback_data="explore_community"))
    return markup


def reset_state_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data="RESET_STATE:YES"),
        InlineKeyboardButton("❌ No", callback_data="RESET_STATE:NO"),
    )
    return markup


def add_exercise_markup(comes_from=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✍️ Add custom exercise", callback_data="add_exercise"))
    markup.add(InlineKeyboardButton("🔎 Browse catalogue", callback_data="choose_exercise_from_catalogue"))
    if comes_from == "start_menu":
        # user selected to start a workout that doesn't have any exercises
        markup.add(InlineKeyboardButton("↩️ Go back", callback_data="choose_workouts"))
    else:
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="start_menu"))
    return markup


def add_another_exercise_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✍️ Add custom exercise", callback_data="add_exercise"))
    markup.add(InlineKeyboardButton("🔎 Browse catalogue", callback_data="choose_exercise_from_catalogue"))
    markup.add(InlineKeyboardButton("💪 Start workout", callback_data="exercise_menu:choose_workouts"))
    markup.add(InlineKeyboardButton("Go to main menu", callback_data="start_menu"))
    return markup


def create_workout_go_back_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def create_workout_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data="create_workout"),
        InlineKeyboardButton("❌ No", callback_data="request_community"),
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
        markup.add(InlineKeyboardButton("↩️ Go back", callback_data="exercise_added"))
    else:
        markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def view_workout_details_markup(workouts, comes_from=None):
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"VIEW_WORKOUT:{workout['id']}"))
    if comes_from == "explore_community":
        markup.add(InlineKeyboardButton("↩️ Go back", callback_data="explore_community"))
    else:
        markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def publish_workout_markup(workouts):
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"PUBLISH_WORKOUT:{workout['id']}"))
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def confirm_publish_workout_markup(workout_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"CONFIRM_PUBLISH_WORKOUT:{workout_id}"),
        InlineKeyboardButton("❌ No", callback_data=f"ABORT_PUBLISH_WORKOUT:{workout_id}")
    )
    return markup


def return_to_view_workout_details_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="list_workouts_for_workout_details"))
    return markup


def delete_workout_markup(workouts):
    markup = InlineKeyboardMarkup()
    for node_id in workouts:
        workout = workouts[node_id]
        markup.add(InlineKeyboardButton(workout['title'], callback_data=f"DELETE_WORKOUT:{workout['id']}"))
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def delete_workout_confirmation_markup(workout_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"CONFIRM_DELETE_WORKOUT:{workout_id}"),
        InlineKeyboardButton("❌ No", callback_data=f"ABORT_DELETE_WORKOUT:{workout_id}")
    )
    return markup


def explore_community_workouts_answer_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data="explore_community"),
        InlineKeyboardButton("❌ No", callback_data="start_menu"),
    )
    return markup


def view_exercise_details_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔎 View Details", callback_data="show_exercise_stats")
    )
    return markup


def number_pad_markup(show_previous=False, show_finish=False):
    # User uses this keyboard to store their reps after each set
    number_pad = ReplyKeyboardMarkup(
        resize_keyboard=False,
        one_time_keyboard=False
    )
    # * operator: spread the entries
    number_pad.add(*[str(x) for x in range(4, 16)])
    if show_previous:
        number_pad.add(
            KeyboardButton("/previous"),
            KeyboardButton("/finish" if show_finish else "/next")
        )
    else:
        number_pad.add(
            KeyboardButton("/finish" if show_finish else "/next")
        )
    return number_pad


def exercise_selector_markup(values, list_view=False):
    markup = InlineKeyboardMarkup()
    if list_view:
        for value in values:
            markup.add(InlineKeyboardButton(value, callback_data=f"choose_exercise_from_catalogue:{value}"))
    else:
        # grid view
        inline_values = [
            InlineKeyboardButton(value, callback_data=f"choose_exercise_from_catalogue:{value}") for value in values
        ]
        markup.add(*inline_values)
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="choose_exercise_from_catalogue:go_back"))
    return markup


def add_catalogue_exercise_markup():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Add", callback_data="add_catalogue_exercise"),
        InlineKeyboardButton("↩️ Go back", callback_data="choose_exercise_from_catalogue:go_back")
    )
    return markup


def add_custom_exercise_go_back_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="show_add_exercise_options"))
    return markup


def choose_community_workout_type_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Recommended Routine", callback_data="SHOW_RECOMMENDED_ROUTINES"))
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="start_menu"))
    return markup


def show_recommended_routine_progressions_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Beginner", callback_data="RECOMMENDED_ROUTINE:BEGINNER"))
    markup.add(InlineKeyboardButton("Intermediate", callback_data="RECOMMENDED_ROUTINE:INTERMEDIATE"))
    markup.add(InlineKeyboardButton("Advanced", callback_data="RECOMMENDED_ROUTINE:ADVANCED"))
    markup.add(InlineKeyboardButton("↩️ Go back", callback_data="explore_community"))
    return markup
