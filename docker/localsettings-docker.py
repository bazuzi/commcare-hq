from .dockersettings import *

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ADMINS = (('Admin', 'admin@example.com'),)

AUDIT_ADMIN_VIEWS=False

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True

LESS_DEBUG = True
LESS_WATCH = False
COMPRESS_OFFLINE = False

BITLY_LOGIN = None

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'

BASE_ADDRESS = '{}:8000'.format(os.environ.get('BASE_HOST', 'localhost'))

CCHQ_API_THROTTLE_REQUESTS = 200
CCHQ_API_THROTTLE_TIMEFRAME = 10

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

RESTORE_PAYLOAD_DIR_NAME = 'restore'
SHARED_TEMP_DIR_NAME = 'temp'

ENABLE_PRELOGIN_SITE = True