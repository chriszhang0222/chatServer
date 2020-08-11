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
