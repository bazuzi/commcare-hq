import logging
import os
import datetime
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth.views import logout as django_logout

from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache

from dimagi.utils.parsing import json_format_datetime, string_to_utc_datetime

try:
    import psutil
except ImportError:
    psutil = None


# this isn't OR specific, but we like it to be included
OPENROSA_ACCEPT_LANGUAGE = "HTTP_ACCEPT_LANGUAGE"
OPENROSA_VERSION_HEADER = "HTTP_X_OPENROSA_VERSION"
OPENROSA_DATE_HEADER = "HTTP_DATE"
OPENROSA_HEADERS = [OPENROSA_VERSION_HEADER, OPENROSA_DATE_HEADER, OPENROSA_ACCEPT_LANGUAGE]


class OpenRosaMiddleware(object):
    """
    Middleware to support OpenRosa request/response standards compliance 
    https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest
    """
    
    def __init__(self):        
        pass

    def process_request(self, request):
        # if there's a date header specified add that to the request
        # as a first class property
        or_headers = {}
        for header in OPENROSA_HEADERS:
            if header in request.META:
                or_headers[header] = request.META[header]
        request.openrosa_headers = or_headers

    def process_response(self, request, response):
        response[OPENROSA_VERSION_HEADER] = settings.OPENROSA_VERSION
        return response


profile_logger = logging.getLogger('profile_middleware')


class MemoryUsageMiddleware(object):
    """
    Stolen and modified from http://stackoverflow.com/a/12254394/8207

    This is a pretty poor, blunt tool and is not recommended to be treated as definitive truth.
    """
    _psutil_installed = None

    def _check_psutil(self):
        if self._psutil_installed is None:
            if psutil is None:
                profile_logger.warning('Install dev-requirements (psutil) in order to use MemoryUsageMiddleware')
                self._psutil_installed = False
            else:
                self._psutil_installed = True
        return self._psutil_installed

    def process_request(self, request):
        if self._check_psutil():
            request._profile_memory = psutil.Process(os.getpid()).get_memory_info()

    def process_response(self, request, response):
        if self._check_psutil() and hasattr(request, '_profile_memory'):
            mem = psutil.Process(os.getpid()).get_memory_info()
            diff = (mem.rss - request._profile_memory.rss) / 1024
            profile_logger.info('{} memory usage {} KB'.format(request.path, diff))
        return response


class TimingMiddleware(object):

    def process_request(self, request):
        request._profile_starttime = datetime.datetime.utcnow()

    def process_response(self, request, response):
        if hasattr(request, '_profile_starttime'):
            duration = datetime.datetime.utcnow() - request._profile_starttime
            profile_logger.info('{} time {}'.format(request.path, duration), extra={'duration': duration})
        return response


class TimeoutMiddleware(object):

    @staticmethod
    def _session_expired(timeout, activity, time):
        if activity is None:
            return False
        if time - string_to_utc_datetime(activity) > datetime.timedelta(minutes=timeout):
            return True
        else:
            return False

    @staticmethod
    @quickcache(['domain_name', 'secure_session'], timeout=10 * 60)
    def _session_insecure_and_domain_requires_secure_session(secure_session, domain_name):
        if secure_session:
            return False
        else:
            domain = Domain.get_by_name(domain_name)
            return domain and domain.secure_sessions

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated():
            return

        secure_session = request.session.get('secure_session')
        now = datetime.datetime.utcnow()

        if hasattr(request, 'domain') and \
                self._session_insecure_and_domain_requires_secure_session(secure_session, request.domain):
            if self._session_expired(settings.SECURE_TIMEOUT, request.user.last_login, now):
                django_logout(request, template_name=settings.BASE_TEMPLATE)
                # this must be after logout so it is attached to the new session
                request.session['secure_session'] = True
                return HttpResponseRedirect(reverse('login') + '?next=' + request.path)
            else:
                request.session['secure_session'] = True
                request.session['last_request'] = json_format_datetime(now)
                return
        else:
            last_request = request.session.get('last_request')
            timeout = settings.SECURE_TIMEOUT if secure_session else settings.INACTIVITY_TIMEOUT
            if self._session_expired(timeout, last_request, now):
                django_logout(request, template_name=settings.BASE_TEMPLATE)
                return HttpResponseRedirect(reverse('login') + '?next=' + request.path)
            request.session['last_request'] = json_format_datetime(now)


class NoCacheMiddleware(object):

    def process_response(self, request, response):
        response['Cache-Control'] = "no-cache, no-store, must-revalidate"
        response['Expires'] = "-1"
        response['Pragma'] = "no-cache"
        return response
