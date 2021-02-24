# this file contains state agnostic QoL functions

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


def get_digit_as_word(index):
    digits = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eight", "ninth"]
    if index < 9:
        return f"{digits[index]}"
    else:
        return f"{index}th"