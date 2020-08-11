import asyncio
import base64
import datetime
import json
import logging
import os
import re
import sys
import urllib
from typing import Union, Optional, Awaitable

import dateutil.parser
import redis
import tornado.options
import tornado.websocket
import urllib3
from redis import Redis
from tornado import gen

import settings
from tornado.httpserver import HTTPServer
from tornado.web import RequestHandler, Application
from tornado.httpclient import HTTPClient, HTTPError, HTTPRequest, AsyncHTTPClient

from utils import decode_token, convert_from_db_time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

REDIS_SERVER = settings.REDIS_CONFIG
LOGGER = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    level=logging.INFO)
EXPIRE_TIME = 60 * 60 * 24
TIME_ZONE = 'America/Los_Angeles'


def get_redis_connection() -> Redis:
    pool = redis.ConnectionPool(
        host=REDIS_SERVER['HOST'], port=REDIS_SERVER['PORT'], password=REDIS_SERVER['PASSWORD'], decode_responses=True
    )
    r = redis.StrictRedis(connection_pool=pool)
    return r


class ChatSocketServerHandler(tornado.websocket.WebSocketHandler):
    client = get_redis_connection()
    user_id = None
    company_id = None
    channels = set()
    subscribed = False
    auth_token = None

    def get_auth_token(self, token):
        token_first, token_second = token.split("_")
        token_second = decode_token(token_second)
        token = token_first + '_' + token_second
        token_obj = json.loads(self.client.get(token))
        return 'Token ' + token_obj.get('token_key')

    def check_origin(self, origin: str) -> bool:
        domain = self.request.headers.get('Origin')
        domain = domain.replace('http://', '').replace('https://', '').rstrip('/')
        if domain in settings.ALLOWED_HOSTS:
            return True
        return False

    def check_permission(self, user_id, company_id, token):
        token_first, token_second = token.split("_")
        token_second = decode_token(token_second)
        token = token_first + '_' + token_second

        token_obj = self.client.get(token)
        if token_obj is None:
            return False
            if self.client.get('user_{}_company_{}'.format(user_id, company_id)) is not None:
                self.client.remove('user_{}_company_{}'.format(user_id, company_id))
        self.client.set('user_{}_company_{}'.format(user_id, company_id), json.loads(token_obj).get('token_key', None), EXPIRE_TIME)
        return True

    def get_redis_channel(self, user_id):
        return 'user_{}'.format(user_id)

    @gen.coroutine
    def open(self, user_id, company_id, token):
        if not user_id or not company_id or not token:
            self.close()
            return
        user_id = int(user_id)
        company_id = int(company_id)
        if not self.check_permission(user_id, company_id, token):
            self.close()
            return
        self.user_id = user_id
        self.company_id = company_id
        current_channel = self.get_redis_channel(user_id)
        self.channels.add(current_channel)
        subscribe = self.client.pubsub()
        subscribe.subscribe(**{current_channel: self.on_message_pub})
        subscribe.run_in_thread(sleep_time=0.001)
        logging.info('Redis Subscribe channel %s' % current_channel)
        self.subscribed = True
        logging.info('New user %i connected.' % user_id)

    def on_message_pub(self, message):
        message_body = message.get('data')
        message_body = tornado.escape.json_decode(message_body)
        asyncio.set_event_loop(asyncio.new_event_loop())
        if message_body.get('type') == 'chat':
            self.send_chat_message(message_body)
        else:
            raise ValueError('Message type %s is not supported' % message_body.get('type'))

    def send_chat_message(self, message):
        """
        Send message to websocket when on_message_published receives data
        """
        message_date, message_time, date = self.get_converted_datetime(
            dateutil.parser.parse(message['timestamp']), TIME_ZONE
        )
        message['discussion_date'] = message_date
        message['discussion_time'] = message_time
        try:
            self.write_message({'type': 'chat', 'success': True, 'messages': [message]})
        except tornado.websocket.WebSocketClosedError:
            logging.error('closed')

    def get_converted_datetime(self, date, time_zone):
        date = convert_from_db_time(date, time_zone)
        now = convert_from_db_time(datetime.datetime.utcnow(), time_zone)
        formatted_date = self.format_date(date, now)
        return formatted_date[0], formatted_date[1], date

    def format_date(self, date_object, now):
        time = datetime.datetime.strftime(date_object, '%I:%M %p')
        if date_object.date() == now.date():
            date = 'Today'
        elif date_object.year != now.year:
            date = datetime.datetime.strftime(date_object, '%B %e, %Y')
        else:
            date = datetime.datetime.strftime(date_object, '%B %e')
        return date, time

    @gen.coroutine
    async def on_message(self, message: Union[str, bytes]) -> Optional[Awaitable[None]]:
        logging.info('Received new message %r' % message)
        message = message.replace(u'\xa0', ' ')
        message_encoded = tornado.escape.json_decode(message)
        message_type = message_encoded['type']
        if message_type == 'chat':
            await self.publish_message(message_encoded)
        else:
            raise ValueError('Message type %s is not supported' % message_type)

    async def publish_message(self, message_encoded: dict):
        user_id = int(message_encoded['user_id'])
        company_id = int(message_encoded['company_id'])
        message_body = tornado.escape.linkify(message_encoded['body'])
        identifier = message_encoded['identifier']
        room_id = message_encoded['room_id']
        if user_id != self.user_id or company_id != self.company_id:
            logging.warning('Error: company or user is not correct')
            self.write_message({'type': 'info', 'success': False, 'message': 'User or Company id is not correct'})
            return
        request = self.get_request('/chat/save_message_to_db/', 'POST', {
            'room_id': room_id,
            'user_id': user_id,
            'company_id': company_id,
            'identifier': identifier,
            'message_content': message_body
        })
        client = AsyncHTTPClient()
        try:
            response = await client.fetch(request=request)
        except Exception:
            self.write_message({
                'type': 'info',
                'success': False,
                'message': 'Error when persisit into db'
            })
            client.close()
            return
        else:
            data = json.loads(response.body.decode('utf-8'))
            if data['success'] is False:
                self.write_message({
                    'type': 'info',
                    'success': False,
                    'message': data['message']
                })
                return
            else:
                message = data.get('message')
                self.write_message({
                    'type': 'info_chat',
                    'success': 'True',
                    'message': 'Message sent out successfully',
                    'id': message['id'],
                    'identifier': identifier,
                    'timestamp': message['timestamp'],
                    'discussion_date': data.get('message_date'),
                    'discussion_time': data.get('message_time')
                })
                message['type'] = 'chat'
                message['identifier'] = identifier
                self.publish_message_to_all_users(data['user_ids'], message, company_id)

    def publish_message_to_all_users(self, user_ids, message, company_id):
        for user_id in user_ids:
            self.publish_message_to_one(user_id, message, company_id)

    def publish_message_to_one(self, user_id, message, company_id):
        user_message = self.build_message(user_id, message)
        if user_message is None or len(user_message) == 0:
            return
        self.publish_message_to_redis(user_id, user_message)

    def publish_message_to_redis(self, user_id: int, message: dict):
        channel = self.get_redis_channel(user_id)
        try:
            self.application.client.publish(channel, tornado.escape.json_encode(message))
        except Exception as e:
            LOGGER.error(e)

    def build_message(self, user_id, message):
        new_message = dict(message)
        new_message['read'] = True if user_id == message['from_user_id'] else message['read']
        new_message['body'] = self.highlight_full_name(new_message['body'], user_id)
        new_message["mc"] = self.build_class(new_message['read'])
        return new_message

    def build_class(self, read) -> str:
        message_class = 'fade-message'
        message_class += ' unread' if not read else ''
        return message_class

    def highlight_full_name(self, discussion_html, user_id=None):
        if not user_id:
            return discussion_html
        discussion_html = re.sub('class="!%i"' % user_id, 'class="text-danger"', discussion_html)
        discussion_html = re.sub('class="@%i"' % user_id, 'class="text-success"', discussion_html)
        return discussion_html

    def handle_request(self, response):
        print(response)

    def get_request(self, url, method, params):
        if 'user_id' not in params or 'company_id' not in params:
            raise ValueError('User Id and Company Id can not be null')
        user_id = params['user_id']
        company_id = params['company_id']
        token = self.client.get('user_{}_company_{}'.format(user_id, company_id))
        url = settings.QUANTUM_SERVER_URL + url
        return HTTPRequest(url=url, method=method, headers={
            'Authorization': 'Token ' + token
        }, body=urllib.parse.urlencode(params))

    def on_close(self):
        logging.info("socket closed, cleaning up resources now")
        if hasattr(self, 'client'):
            if self.subscribed and self.channels:
                subscribe = self.client.pubsub()
                for channel in self.channels:
                    subscribe.unsubscribe(channel)
                    logging.info('Unsubscribe channel %s' % channel)
                self.subscribed = False


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/chat/(\d+)/(\d+)/([a-zA-Z0-9/_/-/=]*)', ChatSocketServerHandler)
        ]
        tornado.web.Application.__init__(self, handlers)
        self.client = get_redis_connection()


def main(secure):
    app = Application()
    if secure:
        logging.info('Init Socket Server port: 8889')
        app.listen(8889, ssl_options=settings.SSL_OPTIONS)
    else:
        logging.info('Init Socket Server port: 8888')
        app.listen(8888)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    logging.info('Init Tornado Server')
    try:
        secure = (sys.argv[1] == 'wss')
    except IndexError:
        secure = False
    main(secure)


