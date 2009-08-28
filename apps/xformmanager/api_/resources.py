from datetime import datetime
from django.core import serializers
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.template import RequestContext
from django_rest_interface.resource import Resource
from transformers.csv import get_csv_from_django_query, format_csv
from transformers.zip import get_zipfile, get_tarfile
from xformmanager.xformdef import FormDef
from xformmanager.models import *
from hq.models import *

""" changes to the API need to occur in 
* api/urls.py (redirection)
* api/xforms.py (implementation)
* api/templates/api.xml (documentation)
"""

# TODO - come back and clean this up to use more of the django-rest-interface
# goodness (i.e. reduce duplicate 'serialize' calls by using Collections)
# TODO - pull out authentication stuff into some generic wrapper
# if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
#    return HttpResponse("You do not have permissions to use this API.")

# api/
class XFormApi(Resource):
    def read(self, request, template='api.xml'):
        """ lists all api calls """
        context = {}
        return render_to_response(template, context, context_instance=RequestContext(request) )

# api/xforms
class XFormSchemata(Resource):
    def read(self, request, template= 'api_/xforms.xml'):
        xforms = FormDefModel.objects.order_by('id')
        if not request.REQUEST.has_key('format') or request.GET['format'].lower() != 'sync':
            # temporary measure until we get server-server authentication working
            # TODO - remove
            try:
                extuser = ExtUser.objects.get(id=request.user.id)
            except ExtUser.DoesNotExist:
                return HttpResponseBadRequest("You do not have permission to use this API.")
            xforms = xforms.filter(domain=extuser.domain)
        # using django's lazy queryset evaluation awesomeness
        if request.REQUEST.has_key('start-id'):
            xforms = xforms.filter(pk__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            xforms = xforms.filter(pk__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            xforms = xforms.filter(submit_time__gte=date)
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            xforms = xforms.filter(submit_time__lte=date)
        if not xforms:
            return HttpResponseBadRequest("No schemas have been registered.")
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'sync':
                # this is a special case: used for server synchronization
                # so we pass *all* data (not just a subset)
                if 'export_path' not in settings.RAPIDSMS_APPS['xformmanager']:
                    return HttpResponseBadRequest("Please set 'export_path' " + \
                                                  "in your cchq xformmanager settings.")
                file_list = []
                for schema in xforms:
                    exported_file = self._full_schema_to_file(schema)
                    if exported_file: file_list.append( exported_file )
                export_path = settings.RAPIDSMS_APPS['xformmanager']['export_path']
                export_file = os.path.join(export_path, "commcarehq-schemata.tar")
                return get_tarfile(file_list, export_file)
        for xform in xforms:
            # do NOT save this!!! This is just for display
            xform.xsd_file_location = "http://%s/xforms/show/%s?show_schema=yes" % \
                                      (request.get_host(), xform.pk)
        fields = ('form_name','form_display_name','target_namespace','submit_time','xsd_file_location')
        if request.REQUEST.has_key('format'):
            response = HttpResponse()
            if request.GET['format'].lower() == 'json':
                json_serializer = serializers.get_serializer("json")()
                json_serializer.serialize(xforms, ensure_ascii=False, stream=response, fields = \
                    fields)
                response['mimetype'] = 'text/json'
                return response
            elif request.GET['format'].lower() == 'xml': 
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(xforms, stream=response, fields = \
                    fields)
                response['mimetype'] = 'text/xml'
                return response
        # default to CSV
        return get_csv_from_django_query(xforms, fields)
        
    def _full_schema_to_file(self, schema):
        """ exports schema to file and returns full path to exported file """
        file_loc = schema.xsd_file_location
        if not file_loc:
            return
        headers = {
            "original-submit-time" : str(schema.submit_time),
            "original-submit-ip" : str(schema.submit_ip),
            "bytes-received" : schema.bytes_received,
            "form-name" : schema.form_name,
            "form-display-name" : schema.form_display_name,
            "target-namespace" : schema.target_namespace,
            "date-created" : str(schema.date_created),
            "domain" : str(schema.get_domain)
            }
        dir, filename = os.path.split(file_loc)
        export_path = settings.RAPIDSMS_APPS['xformmanager']['export_path']
        write_file = os.path.join(export_path, \
                                  filename.replace(".xml", ".xsdexport"))
        fout = open(write_file, 'w')
        fout.write( simplejson.dumps(headers) + "\n\n" )
        xsd_file = open(file_loc, "r")
        payload = xsd_file.read()
        xsd_file.close()
        fout.write(payload)
        fout.close()
        return write_file

# api/xforms/(?P<formdef_id>\d+)/schema 
class XFormSchema(Resource):
    def read(self, request, formdef_id):
        """ returns the schema for the given form """
        # currently we only support text and xml
        # to support json and csv, we need to query formdef+elementdef recursively
        # note that to do this, we need to build out functionality in storageutility
        # to actually make an element def for each element
        try:
            xsd = FormDefModel.objects.get(pk=formdef_id )
        except FormDefModel.DoesNotExist:
            return HttpResponseBadRequest("Schema with primary key %s was not found." % formdef_id)
        fin = open( xsd.xsd_file_location ,"r")
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'text': 
                formdef = unicode( FormDef(fin) )
                response = HttpResponse(formdef, mimetype='text/plain')
                fin.close()
                return response    
        # default to XML                    
        response = HttpResponse(fin.read(), mimetype='text/xml')
        fin.close()
        return response

# api/xforms/(?P<schema_id>\d+)
class XFormSubmissionsData(Resource):
    def read(self, request, formdef_id):
        """ list all submitted instance data for a particular schema """
        try:
            formdef = FormDefModel.objects.get(pk=formdef_id)
        except FormDefModel.DoesNotExist:
            return HttpResponseBadRequest("Schema with id %s could not found." % formdef_id)            
        metadata = Metadata.objects.filter(formdefmodel=formdef).order_by('id')
        if not metadata:
            return HttpResponseBadRequest("Metadata of schema with id %s not found." % formdef_id)
        filter = []
        if request.REQUEST.has_key('start-id'):
            if filter: filter = filter + " AND "
            filter = filter + "id >= " + request.GET['start-id']
            metadata = metadata.filter(raw_data__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            if filter: filter = filter + " AND "
            filter = filter + "id <= " + request.GET['end-id']
            metadata = metadata.filter(raw_data__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-submit-date'):
            date = datetime.strptime(request.GET['start-submit-date'],"%Y-%m-%d")
            # not the most efficient way of doing this 
            # but it keeps our django orm reference and sql work separate
            metadata = metadata.filter(submission__submission__submit_time__gte=date)
            raw_ids = [int(m.raw_data) for m in metadata]
            filter.append( ['id','IN',tuple(raw_ids)] )
        if request.REQUEST.has_key('end-submit-date'):
            date = datetime.strptime(request.GET['end-submit-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__lte=date)
            raw_ids = [int(m.raw_data) for m in metadata]
            filter.append( ['id','IN',tuple(raw_ids)] )
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml' or \
               request.GET['format'].lower() == 'zip':
                file_list = []
                for datum in metadata:
                    file_list.append( datum.submission.filepath )
                return get_zipfile(file_list)
        # default to csv export
        rows = formdef.get_rows( column_filters=filter )
        column = formdef.get_column_names()
        return format_csv(rows, column, formdef.form_name)

# api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)
class XFormSubmissionData(Resource):
    def read(self, request, formdef_id, form_id):
        """ return data from a specific submission """
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                formdef = FormDefModel.objects.get(pk=formdef_id)
                if not formdef: return HttpResponseBadRequest(\
                    "Schema with primary key %s was not found." % formdef_id)
                try:
                    meta = Metadata.objects.get(raw_data=form_id, formdefmodel=formdef)
                except Metadata.DoesNotExist:
                    return HttpResponseBadRequest(\
                        "Instance with id %s and schema %s was not found." % form_id, formdef.id)
                fin = open( meta.xml_file_location() ,"r")
                response = HttpResponse(fin.read(), mimetype='text/xml')
                fin.close()
                return response
        #default to CSV
        try:
            formdef = FormDefModel.objects.get(pk=formdef_id )
        except FormDefModel.DoesNotExist:
            return HttpResponseBadRequest("Schema with primary key %s was not found." % formdef_id)
        row = formdef.get_row(form_id)
        if row is None:
            return HttpResponseBadRequest("Instance matching %s of schema %s was not found." % (form_id,formdef_id) )
        columns = formdef.get_column_names()
        return format_csv(row, columns, formdef.form_name, form_id!=0)

# api/xforms/(?P<formdef_id>\d+)/metadata/
class XFormMetadata(Resource):
    
    def read(self, request, formdef_id):
        """  lists all metadata associated with all instances submitted 
        to a particular schema
        
        """
        # CSV
        metadata = Metadata.objects.filter(formdefmodel=formdef_id).order_by('id')
        if not metadata:
            return HttpResponseBadRequest("Metadata of schema with id %s not found." % formdef_id)
        if request.REQUEST.has_key('start-id'):
            metadata = metadata.filter(pk__gte=request.GET['start-id'])
        if request.REQUEST.has_key('end-id'):
            metadata = metadata.filter(pk__lte=request.GET['end-id'])
        if request.REQUEST.has_key('start-date'):
            date = datetime.strptime(request.GET['start-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__gte=date)
        if request.REQUEST.has_key('end-date'):
            date = datetime.strptime(request.GET['end-date'],"%Y-%m-%d")
            metadata = metadata.filter(submission__submission__submit_time__lte=date)
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                response = HttpResponse(mimetype='text/xml')
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(metadata, stream=response, fields = \
                    ('formname','formversion','deviceid','timestart','timeend',\
                     'username','chw_id','uid','raw_data') )
                return response
        return get_csv_from_django_query(metadata)

# api/xforms/(?P<formdef_id>\d+)/(?P<form_id>\d+)/metadata/ 
class XFormMetadatum(Resource):
    def read(self, request, formdef_id, form_id):
        """ lists metadata associated with a partiocular instance """
        # CSV
        metadatum = Metadata.objects.filter(formdefmodel=formdef_id, raw_data=form_id)
        if not metadatum:
            return HttpResponseBadRequest(\
                "Metadatum of form (id=%s) with schema (id=%s) not found." % (form_id, formdef_id) )
        if request.REQUEST.has_key('format'):
            if request.GET['format'].lower() == 'xml':
                response = HttpResponse(mimetype='text/xml')
                xml_serializer = serializers.get_serializer("xml")()
                xml_serializer.serialize(metadatum, stream=response, fields = \
                    ('formname','formversion','deviceid','timestart','timeend',\
                     'username','chw_id','uid','raw_data') )
                return response
        return get_csv_from_django_query(metadatum)

