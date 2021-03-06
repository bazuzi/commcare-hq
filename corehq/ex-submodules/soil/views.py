from datetime import datetime
import json
import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseServerError
from django.shortcuts import render_to_response, render
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _

from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.heartbeat import get_file_heartbeat, get_cache_heartbeat, last_heartbeat
from soil.tasks import demo_sleep
from soil.util import get_download_context


def _parse_date(string):
    if isinstance(string, basestring):
        return datetime.strptime(string, "%Y-%m-%d").date()
    else:
        return string


@login_required
def demo(request):
    download_id = uuid.uuid4().hex
    howlong = int(request.GET.get('secs', 5))
    demo_sleep.delay(download_id, howlong)
    return HttpResponseRedirect(reverse('retrieve_download', kwargs={'download_id': download_id}))

@login_required
def heartbeat_status(request):
    return HttpResponse(json.dumps({"last_timestamp": str(last_heartbeat()),
                                    "last_from_file": get_file_heartbeat(),
                                    "last_from_cache": get_cache_heartbeat()}))
    

@login_required
def ajax_job_poll(request, download_id, template="soil/partials/dl_status.html"):
    message = request.GET['message'] if 'message' in request.GET else None
    try:
        context = get_download_context(download_id, check_state=True, message=message)
    except TaskFailedError as e:
        context = {'error': list(e.errors) if e.errors else [_("An error occurred during the download.")]}
        return HttpResponseServerError(render(request, template, context))
    return render(request, template, context)


@login_required
def retrieve_download(request, download_id, template="soil/file_download.html"):
    """
    Retrieve a download that's waiting to be generated. If it is the get_file, 
    then download it, else, let the ajax on the page poll.
    """
    context = RequestContext(request)
    context['download_id'] = download_id
    do_download = request.GET.has_key('get_file')
    if do_download:
        download = DownloadBase.get(download_id)
        if download is None:
            logging.error("Download file request for expired/nonexistent file requested")
            raise Http404
        else:
            return download.toHttpResponse()

    return render_to_response(template, context_instance=context)
