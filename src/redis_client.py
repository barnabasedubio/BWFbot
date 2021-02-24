# this file contains all functions pertaining to redis

import redis
import jsonpickle


CONN = redis.Redis(decode_responses=True)


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


def delete_from_redis(*args):
    CONN.delete(*args)


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
