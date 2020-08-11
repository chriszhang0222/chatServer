import base64
from datetime import datetime
import sys
from binascii import b2a_hex, a2b_hex

import pytz
import hmac, hashlib
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


def db_date_to_string(date, date_format, time_zone=None):
    if not date:
        return ''
    date = convert_from_db_time(date, time_zone)
    return datetime.strftime(date, date_format)


def hashencrypt():
    h = hmac.new(key='key',msg='hello')
    h.update('world!')
    ret = h.hexdigest()
    return ret

