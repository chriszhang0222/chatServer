import base64
from datetime import datetime

import pytz

TIME_ZONE = 'America/Los_Angeles'


def decode_token(token: str):
    return base64.b64decode(token).decode('utf-8')


def get_time_zone(time_zone):
    if time_zone and time_zone is not None:
        return time_zone
    return TIME_ZONE


def convert_from_db_time(date: datetime, user_timezone):
    if not date:
        return None
    user_timezone = get_time_zone(user_timezone)
    if date.tzinfo:
        return date.astimezone(pytz.timezone(user_timezone))
    else:
        aware_time = pytz.timezone('UTC').localize(date, is_dst=None)
        return aware_time.astimezone(pytz.timezone(user_timezone))


