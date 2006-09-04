"""
Copyright (C) Richard Lewis 2006

This software is licensed under the terms of the GNU GPL.

The server module contains the server_config class and the class for parsing server
configuration files.
"""

import string, os
from xml.sax import parse, SAXException
from xml.sax.handler import ContentHandler
from pycoon import apache
from interpolation import *
from pycoon.helpers import attributes2options
from pycoon.pipeline import pipeline, build_pipeline
from pycoon.components import register_component

class server_config(object):
    """
    server_config holds the configuration information for Pycoon server instances.
    """
    
    def __init__(self):
        self.set_root("")
        
        # the logging level:
        self.log_up_down = True        # just startup and shutdown;
        self.log_errors = False        # all errors; (might not work: need to specify how raised exceptions are reported)
        self.log_requests = False      # all requests;
        self.log_debug = False         # debugging;

        self.EXCEPTION = None          # this will hold the exception info and traceback whenever an exception occurs

        self.use_requests_cache = False # flag indicates whether request caching should be used
        self.MAX_REQUESTS_CACHE = 20   # the maximum number of cached requests
        self.MAX_REQUEST_SIZE = 1024 * 1024 # the maximum size (in bytes) of requests that can be cached

        self.use_files_cache = False   # flag indicates whether file caching should be used
        self.MAX_FILES_CACHE = 10      # the maximum number of cached files
        self.MAX_CACHE_FILE_SIZE = 512 * 1024 # the maximum size (in bytes) of files that can be cached

        self.component_types = ["component", "selector", "source", "transformer", "serializer"]
        self.components = {}           # dictionary of available components (indexed by tuple: (function, type value))
        self.component_enames = []     # a list of available element names used by components

        self.component_syntaxes = {}   # dictionary of available component invokation element syntaxes
                                       # (indexed by (element name, type value)

        self.interpolation_syntaxes = {} # dictionary of available interpolation_syntax object (indexed by name)

        self.ds_initialisers = {}      # dictionary of available source component data-source initialisation methods
                                       # (indexed by source name)

        self.error_pipelines = {}      # a dictionary of pipeline objects indexed by error code, used as error handlers

        self.access_log = None
        self.error_log = None

        # register built-in interpolation syntaxes
        register_interpolation_syntax(self, interpolate_pattern_match_number(), "pattern-match-number")
        register_interpolation_syntax(self, interpolate_uri(), "uri")
        register_interpolation_syntax(self, interpolate_pipeline(), "pipeline")
        register_interpolation_syntax(self, interpolate_traceback(), "traceback")

    # config_root and document_root should always contains the same value
    # using document_root as an alias for config_root allows a server_config instance to be used polymorphicly
    # in place of a sitemap_config instance.
    def get_root(self): return self._config_root
    def set_root(self, r):
        self._config_root = r
        self._document_root = r

    config_root = property(get_root, set_root)
    document_root = property(get_root, set_root)

    def get_new_component(self, el_name, parent, attrs, root_path):
        """
        Returns a new componet instance. Component is specified by a valid sitemap XML invokation
        syntax given in el_name and attrs (xml.sax.Attributes) parameters.

        @el_name: component element's tag name
        @parent_name: parent element's tag name
        @attrs: xml.sax.Attributes instance containing component configuration
        @root_path: either sitemap document root or server config_root
        """

        try:
            component_id = (el_name, attrs['type'])
        except KeyError:
            component_id = (el_name, None)
        
        if component_id in self.component_syntaxes.keys() and\
               self.component_syntaxes[component_id].validate(parent.function, el_name, attrs):
            (component_type, attrs_dict) = attributes2options(attrs)
            attrs_dict['parent'] = parent
            attrs_dict['root_path'] = root_path

            return self.components[component_id](**attrs_dict)

    def handle_error(self, req, error_code):
        """
        Attempt to use the error_pipelines to handle the given error code.

        @req: an Apache request object
        @error_code: an Apache error code
        """
        
        if error_code in self.error_pipelines.keys():
            # and if there is an error pipeline in the sitemap to handle the error code
            # then execute it.
            req.status = error_code

            if self.log_errors:
                self.error_log.write("Server handling error %s; request: \"%s\"" % (error_code, req.unparsed_uri))
            self.error_pipelines[error_code].execute(req)

            (success, result) = self.error_pipelines[error_code].execute(req)

            if success:
                req.content_type = self.error_pipelines[error_code].mime
                req.set_content_length(len(result))
                req.write(result)

                return (True, apache.DONE)

            else:
                req.status = apache.HTTP_INTERNAL_SERVER_ERROR
                if self.log_errors:
                    self.error_log.write("Unhandled error %s; request: \"%s\"; returning status 500" % (error_code, req.unparsed_uri))

                return (False, apache.DONE)

        else:
            req.status = apache.HTTP_INTERNAL_SERVER_ERROR
            if self.log_errors:
                self.error_log.write("Unhandled error %s; request: \"%s\"; returning status 500" % (error_code, req.unparsed_uri))

            return (False, apache.DONE)

class server_config_parse(ContentHandler):
    """
    server_config_parse parses the server configuration XML file (using SAX) and populates the given server_config
    instance.
    """
    
    def __init__(self, filename, server):
        """
        server_config_parse constructor. Parses server XML configuation file automatically upon object instantiation.
        """
        
        self.server = server
        self.chars = u""        # SAX characters buffer
        self.col_chars = False  # SAX save characters flag
        self.done_components = False # flag set to True when the <components> element is completed
        self.server.config_root = os.path.split(filename)[0].replace("file://", "")

        self.proc_comp_stack = []  # a stack for components being constructed

        # call xml.sax.parse with the given server config file name
        parse(filename, self)

    def startElement(self, name, attrs):
        if name in ["admin-email", "max-files-cache", "max-file-size",\
                    "max-requests-cache", "max-request-size"]:
            # these are the text-only configuration details
            # instruct the parser to collect the textual content of the elements
            self.chars = u""
            self.col_chars = True

        elif name == "files-cache" and attrs['use'] == "yes":
            # boolean option "files-cache": specifies whether <read> component files should be cached
            self.server.use_files_cache = True
            if self.server.log_debug: self.server.error_log.write("Using files cache is True.")

        elif name == "requests-cache" and attrs['use'] == "yes":
            # boolean option "requests-cache": specifies whether pipeline results should be cached
            self.server.use_requests_cache = True
            if self.server.log_debug: self.server.error_log.write("Using requests cache is True.")

        elif name == "log-up-down" and attrs['use'] == "yes":
            # boolean logging level option "log-up-down": specifies whether the server startup and shutdown events should be logged
            self.server.log_up_down = True
            if self.server.log_debug: self.server.error_log.write("Log level server up/down is True.")

        elif name == "log-errors" and attrs['use'] == "yes":
            # boolean logging level option "log-errors": specifies whether handled errors should be logged
            self.server.log_errors = True
            if self.server.log_debug: self.server.error_log.write("Log level errors is True.")

        elif name == "log-requests" and attrs['use'] == "yes":
            # boolean logging level option "log-requests": specifies whether all handled requests should be logged
            self.server.log_requests = True
            if self.server.log_debug: self.server.error_log.write("Log level requests is True.")

        elif name == "log-debug-info" and attrs['use'] == "yes":
            # boolean logging level option "log-debug": specifies whether debugging information should be logged
            self.server.log_debug = True
            if self.server.log_debug: self.server.error_log.write("Log level debug is True.")

        elif name in self.server.component_types and attrs.has_key('name'):
            # register a component
            register_component(self.server, str(attrs['name']), attrs)
            
        elif name == "pipeline" and attrs.has_key('on-error-code'):
            if not self.done_components:
                # ensure that all the component classes have been registered before processing any server pipelines
                raise SAXException("<pipeline> elements must follow the <components> element.")

            self.proc_comp_stack = [build_pipeline(self.server, sitemap=None, attrs=attrs)]

        elif name in self.server.component_enames and self.done_components:
            # process a pipeline component

            self.proc_comp_stack.append(self.proc_comp_stack[-1].add_component(\
                self.server.get_new_component(name, self.proc_comp_stack[-1], attrs, self.server.document_root)))

    def characters(self, data):
        if self.col_chars:
            self.chars += data

    def endElement(self, name):
        if name in ["admin-email"]:
            try:
                self.server.__dict__[str(name.replace("-", "_"))] = str(self.chars)
                self.col_chars = False
                self.chars = u""
                if self.server.log_debug:
                    self.server.error_log.write("Set server property: \"%s\": \"%s\"." %\
                                           (str(name.replace("-", "_")), self.server.__dict__[str(name.replace("-", "_"))]))
            except KeyError: raise KeyError("Unknown server property: %s" % name)
            
        elif name in ["max-files-cache", "max-file-size",\
                    "max-requests-cache", "max-request-size"]:
            try:
                self.server.__dict__[name.replace("-", "_")] = eval(str(self.chars))
                self.col_chars = False
                self.chars = u""
                if self.server.log_debug:
                    self.server.error_log.write("Set server property: \"%s\": \"%s\"." %\
                                           (str(name.replace("-", "_")), self.server.__dict__[str(name.replace("-", "_"))]))
            except KeyError: raise KeyError("Unknown server property: %s" % name)
            except SyntaxError: raise ValueError("Invalid value for %s: %s" % (name, self.chars))

        elif name == "components":
            self.done_components = True

        elif name == "pipeline":
            if self.server.log_debug:
                self.server.error_log.write("Added server pipeline: \"%s\"" % self.proc_comp_stack[-1].name)

        elif name in self.server.component_enames and self.done_components:
            self.proc_comp_stack.pop()
