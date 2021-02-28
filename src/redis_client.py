# this file contains all functions pertaining to redis

import redis
import jsonpickle


# since the redis container is listening on 0.0.0.0 this should work
CONN = redis.Redis(decode_responses=True)


# --------- BASIC OPERATIONS ---------

def exists_in_redis(uid, key):
    key = f"{uid}_{key}"
    return bool(CONN.exists(key))


def get_from_redis(uid, key):
    key = f"{uid}_{key}"
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


def delete_from_redis(uid, *args):
    new_args = [f"{uid}_{arg}" for arg in args]
    CONN.delete(*new_args)


def set_to_redis(uid, key, value):
    key = f"{uid}_{key}"
    if type(value) == dict:
        value = jsonpickle.dumps(value)

    elif type(value) == bool:
        value = str(value)

    elif value is None:
        value = "None"

    CONN.set(key, value)


# --------- LIST OPERATIONS ---------

def push_to_redis(uid, key, value):
    key = f"{uid}_{key}"
    CONN.rpush(key, value)


def pop_from_redis(uid, key, pop_type):
    key = f"{uid}_{key}"
    if pop_type == "left":
        CONN.lpop(key)
    if pop_type == "right":
        CONN.rpop(key)


def set_list_index_to_redis(uid, key, index, value):
    key = f"{uid}_{key}"
    CONN.lset(key, index, value)


# --------- ARITHMETIC OPERATIONS ---------

def increment_in_redis(uid, key):
    key = f"{uid}_{key}"
    CONN.incr(key)


def decrement_in_redis(uid, key):
    key = f"{uid}_{key}"
    CONN.decr(key)
