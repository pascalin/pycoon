#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Andrey Nordin <http://claimid.com/anrienord>"

import sys
import os
from mod_python import apache
sys.path.append(os.path.join(os.path.dirname(sys.modules[__name__].__file__), "..", "..", ".."))
from pycoon.wsgi.servers.paste.modpython import Handler
from pycoon import wsgi

def handler(req):
    options = req.get_options()
    pycoon = wsgi.pycoonFactory({"server-xconf": options["config"]})
    Handler(req).run(pycoon)
    return apache.OK

