# Quantum SDS ChatServer

## Technique Stack
```
Tornado, websocket, Vue.js, Redis, Django-Rest framework
```

## Setup
```
1. In Chatserver project, set all required settings in chat/settings.py
2. In Quantum project .env file, set CHAT_SERVER_ADDRESS to be the address of Chatserver
3. In both Quantum proj and Chatserver proj, the redis config should be same
4. Remember to map port 8888 or 8889 to the same port on host machine

```

## Run command
```
python server.py wss (https)
python server.py     (http)
```

## Example settings
### Chatserver chat/setting.py
```
REDIS_CONFIG = {
    'HOST': '192.168.0.107',
    'PORT': 6379,
    'PASSWORD': None,
    'USER': None
}

ALLOWED_HOSTS = ['demo-3.localhost:8001']
QUANTUM_SERVER_URL = 'http://demo-3.localhost:8001'
CERT_FILE = "/Users/chris/server.crt"
KEY_FILE = "/Users/chris/server.key"

SSL_OPTIONS = {
    'certfile': CERT_FILE,
    'keyfile': KEY_FILE
}

```
### Quantum .env file(only chatserver related fields)
```
REDIS_HOST=192.168.0.107
REDIS_PASSWORD=
REDIS_PORT=6379
CHAT_SERVER_ADDRESS=192.168.0.107
```

### Docker run command(8888 port for example)
```
docker build -t t1 .
&& docker run
-p 127.0.0.1:8888:8888
--name ChatServer
```

### Architecture and Authentication
```
 ----------
|  Quantum |       Store Token, user info, company_info in redis(Encrypted)
|  server  |----------------------   
|          |                     |  
|----------|                     |   
 |        ^                      |
 |Socket  |                      V 
 |        |                   ---------
 |        |                  |  Redis  |
 |        | Rest API          ---------
 |        |                       ^
 V        |                       |
|-------------|                   |
| Chat Server |-------------------
|_____________|       When websocket connected, read token from redis and decrypted 
                      to check auth user

0. Create auth token using python manage.py drf_create_token

1. When User login the quantum server, use request session key, company id and user id
as key, encrypted with base64. User info, auth token as value, store in redis.
When use logout or key expires, redis delete key automatically.

2. In chatServer set ALLOWED_HOSTS to filter invalid request sources.

3. When user use the chat, Quantum server opens a websocket connection to the chat server,
chatserver receieves the encrypted token after connection established. If no encrypted token receives, close connection. 
Otherwise decryptes the token and search from redis. If exists,
the user is authenticated, otherwise close the connection.

4. When user sends message/file, chatserver distributes the message to other users in the same room, 
then call the rest api to persist the message/file into quantum db

Notice that we use Redis as message channel publish/subscribe middleware as well as Auth token storage,
be sure in Qunatum settings and Chatserver settings the address of Redis should be same
```
