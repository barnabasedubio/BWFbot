from firebase_admin import \
    auth as AUTH, \
    db as DB

from firebase_admin.exceptions import FirebaseError


def get_user_from_database(user_id):

    try:
        AUTH.get_user(user_id)

    except AUTH.UserNotFoundError:
        return None

    # get database data for user
    user_data = DB.reference("/users").order_by_child("id").equal_to(user_id).get()
    user_data = dict(user_data)
    user_data = user_data.get(list(user_data.keys())[0])
    return user_data


def get_user_node_key_from_database(user_id):
    user_data = DB.reference("/users").order_by_child("id").equal_to(user_id).get()
    user_data = dict(user_data)
    return list(user_data.keys())[0]


def add_user_to_database(user_id, first_name, last_name, username):

    try:
        AUTH.create_user(
            uid=str(user_id),
            display_name=first_name
        )
    except FirebaseError:
        return False

    # create user node in database
    DB.reference("/users").push({
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name
    })
    # return created user
    return get_user_from_database(user_id)


def get_saved_workout_from_database(user_id, workout_id):
    user_node_id = get_user_node_key_from_database(user_id)
    workout = DB.reference(f"/users/{user_node_id}/saved_workouts/").order_by_child("id").equal_to(workout_id).get()
    workout = dict(workout)
    return workout


def add_workout_to_database(user_id, workout):
    user_node_id = get_user_node_key_from_database(user_id)
    DB.reference(f"/users/{user_node_id}/saved_workouts").push(workout)
    # return updated user
    return get_user_from_database(user_id)


def delete_saved_workout_from_database(user_id, workout_key):
    user_node_id = get_user_node_key_from_database(user_id)
    DB.reference(f"/users/{user_node_id}/saved_workouts/{workout_key}").delete()
    # return updated user
    return get_user_from_database(user_id)


def add_exercise_to_database(user_id, exercise, workout_index):
    user = get_user_from_database(user_id)  # TODO: no DB call needed here if you use global var
    user_node_id = get_user_node_key_from_database(user_id)
    workout_node_id = list(user.get('saved_workouts'))[workout_index]
    DB.reference(f"/users/{user_node_id}/saved_workouts/{workout_node_id}/exercises/").push(exercise)
    # return updated user
    return get_user_from_database(user_id)


def add_completed_workout_to_database(user_id, workout):
    user_node_id = get_user_node_key_from_database(user_id)
    DB.reference(f"/users/{user_node_id}/completed_workouts/").push(workout)
    # return updated user
    return get_user_from_database(user_id)


def add_feedback_to_database(feedback_object):
    DB.reference("/feedback/").push(feedback_object)


def main():
    print("Don't run me!")


if __name__ == "__main__":
    main()
