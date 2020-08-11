# Quantum SDS ChatServer

## Technique Stack
```
Tornado, websocket, Vue.js, Redis, Django-Rest framework
```

## Setup
```
1. In Chatserver project, set all required settings in settings.py
2. In Quantum project .env file, set CHAT_SERVER_ADDRESS to be the address of Chatserver
3. In both Quantum proj and Chatserver proj, the redis config should be same

```

## Run command
```
python server.py wss (https)
python server.py     (http)
```

## example settings
### Chatserver setting.py
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
