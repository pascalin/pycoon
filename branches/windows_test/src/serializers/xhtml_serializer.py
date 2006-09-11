"""
Copyright (C) Richard Lewis 2006

This software is licensed under the terms of the GNU GPL.
"""

import pycoon.serializers
from pycoon.components import invokation_syntax
from pycoon.helpers import correct_script_chars
from lxml.etree import tounicode
import tidy

def register_invokation_syntax(server):
    """
    Allows the component to register the required XML element syntax for it's invokation
    in sitemap files with the sitemap_config_parse class.
    """
        
    invk_syn = invokation_syntax()
    invk_syn.element_name = "serialize"
    invk_syn.allowed_parent_components = ["pipeline"]
    invk_syn.required_attribs = ["type"]
    invk_syn.required_attrib_values = {"type": "xhtml"}
    invk_syn.optional_attribs = []
    invk_syn.allowed_child_components = []

    server.component_syntaxes[("serialize", "xhtml")] = invk_syn
    return invk_syn

class xhtml_serializer(pycoon.serializers.serializer):
    """
    xhtml_serializer class encapsulates the uTidyLib class.
    """

    def __init__(self, parent, root_path=""):
        """
        xhtml_serializer constructor.
        """

        pycoon.serializers.serializer.__init__(self, parent, root_path)
        self.mime_str = "text/html"
        self.description = "xhtml_serializer()"

    def _descend(self, req, uri_pattern, p_sibling_result=None):
        return False

    def _result(self, req, uri_pattern, p_sibling_result=None, child_results=[]):
        """
        Executes tidy.parseString on the p_sibling_result and returns the resultant XHTML.
        """

        options = dict(output_xhtml=1, add_xml_decl=1, doctype="strict", indent=1, wrap=120, tidy_mark=0,\
                       input_encoding="utf8", output_encoding="utf8")
        
        return (True, correct_script_chars(str(tidy.parseString(tounicode(p_sibling_result).encode("utf-8"), **options))))