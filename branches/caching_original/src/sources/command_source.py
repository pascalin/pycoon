"""
Copyright (C) Richard Lewis 2006

This software is licensed under the terms of the GNU GPL.
"""

import pycoon.sources
from pycoon import apache
from pycoon.interpolation import interpolate
from pycoon.components import invokation_syntax
import os
import lxml.etree
from StringIO import StringIO

def register_invokation_syntax(server):
    """
    Allows the component to register the required XML element syntax for it's invokation
    in sitemap files with the sitemap_config_parse class.
    """
        
    invk_syn = invokation_syntax()
    invk_syn.element_name = "source"
    invk_syn.allowed_parent_components = ["pipeline", "aggregate"]
    invk_syn.required_attribs = ["type", "src"]
    invk_syn.required_attrib_values = {"type": "command"}
    invk_syn.optional_attribs = []
    invk_syn.allowed_child_components = ["parameter"]

    server.component_syntaxes[("source", "command")] = invk_syn
    return invk_syn

class command_source(pycoon.sources.source):
    """
    command_source encapsulates a shell command which must return a well-formed XML document
    string. It implements the source interface and can be used as the source component in a pipeline.
    """

    def __init__(self, parent, src, root_path=""):
        """
        command_source constructor. Requires 'pwd' (present working directory) and command string. Commands
        may use named string formatting to integrate request parameters when executed.
        """

        self.command = src
        pycoon.sources.source.__init__(self, parent, root_path)
        self.description = "command_source(\"%s\")" % self.command

    def _descend(self, req, uri_pattern, p_sibling_result=None):
        return True

    def _result(self, req, uri_pattern, p_sibling_result=None, child_results=[]):
        """
        Execute the command and parse the output stream as an lxml.etree.
        """

        parameters = {}
        for c in child_results:
            parameters.update(c)

        try:
            ostream = os.popen(self.command % parameters)
        
            # for some reason it won't accept the ostream file object here,
            # so convert it to a StringIO instead
            ret_tree = lxml.etree.parse(StringIO(ostream.read())).getroot()
            ostream.close()
            
            return (True, ret_tree)
        except OSError:
            return (False, apache.HTTP_NOT_FOUND)