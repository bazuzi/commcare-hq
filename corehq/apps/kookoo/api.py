from django.http import HttpResponse
from django.conf import settings
from urllib import urlencode
from urllib2 import urlopen
from xml.etree.ElementTree import XML

class InvalidPhoneNumberException(Exception):
    pass

API_ID = "KOOKOO"

def get_http_response_string(gateway_session_id, ivr_responses, collect_input=False, hang_up=True):
    xml_string = ""
    for response in ivr_responses:
        text_to_say = response["text_to_say"]
        audio_file_url = response["audio_file_url"]
        
        if audio_file_url is not None:
            xml_string += "<playaudio>%s</playaudio>" % audio_file_url
        elif text_to_say is not None:
            xml_string += "<playtext>%s</playtext>" % text_to_say
    
    if collect_input:
        xml_string = '<collectdtmf o="5000">' + xml_string + '</collectdtmf>'
    
    if hang_up:
        xml_string += "<hangup/>"
    
    return '<response sid="%s">%s</response>' % (gateway_session_id[7:], xml_string)

"""
Expected kwargs:
    api_key
"""
def initiate_outbound_call(call_log_entry, *args, **kwargs):
    phone_number = call_log_entry.phone_number
    if phone_number.startswith("+"):
        phone_number = phone_number[1:]
    
    if phone_number.startswith("91"):
        phone_number = "0" + phone_number[2:]
    else:
        raise InvalidPhoneNumberException("Kookoo can only send to Indian phone numbers.")
    
    params = urlencode({
        "phone_no" : phone_number,
        "api_key" : kwargs["api_key"],
        "outbound_version" : "2",
        "url" : settings.BASE_URL + "/kookoo/ivr/",
        "callback_url" : settings.BASE_URL + "/kookoo/ivr_finished/",
    })
    url = "http://www.kookoo.in/outbound/outbound.php?%s" % params
    response = urlopen(url).read()
    
    root = XML(response)
    for child in root:
        if child.tag.endswith("status"):
            status = child.text
        elif child.tag.endswith("message"):
            message = child.text
    
    if status == "queued":
        call_log_entry.gateway_session_id = "KOOKOO-" + message
    elif status == "error":
        call_log_entry.error = True
        call_log_entry.error_message = message
    else:
        call_log_entry.error = True
        call_log_entry.error_message = "Unknown status received from Kookoo."
    
    call_log_entry.save()


