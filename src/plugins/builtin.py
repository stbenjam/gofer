#
# Copyright (c) 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU Lesser General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (LGPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of LGPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt.
#
# Jeff Ortel <jortel@redhat.com>
#

"""
Demo plugin.
"""
import os
import socket
from uuid import uuid4
from gofer.decorators import *
from gofer.collator import Collator
from gofer.rmi.decorators import Remote
from gofer.agent.plugin import Plugin
from gofer.agent.action import Actions
from gofer.agent.config import Config
from logging import getLogger

log = getLogger(__name__)
plugin = Plugin.find(__name__)


class TestAction:

    @action(hours=36)
    def hello(self):
        plugin = Plugin.find(__name__)
        log.info('Hello:\n%s', plugin.cfg())


class Admin:

    @remote
    def hello(self):
        s = []
        cfg = Config()
        s.append('Hello, I am gofer agent "%s"' % plugin.getuuid())
        s.append('Here is my configuration:\n%s' % cfg)
        s.append('Status: ready')
        return '\n'.join(s)
    
    @remote
    def help(self):
        s = []
        s.append('Plugins:')
        for p in Plugin.all():
            if p.synonyms:
                s.append('  %s %s' % (p.name, p.synonyms))
            else:
                s.append('  %s' % p.name)
        s.append('Actions:')
        for a in self.__actions():
            s.append('  %s %s' % a)
        methods, functions = self.__remote()
        s.append('Methods:')
        for m in methods:
            s.append('  %s.%s()' % m)
        s.append('Functions:')
        for m in functions:
            s.append('  %s.%s()' % m)
        return '\n'.join(s)
    
    def __actions(self):
        actions = []
        for a in Actions().collated():
            actions.append((a.name(), a.interval))
        return actions
    
    def __remote(self):
        methods = []
        funclist = []
        c = Collator()
        classes, functions = c.collate(Remote.functions)
        for n,v in classes.items():
            for m,d in v:
                methods.append((n.__name__, m.__name__))
        for n,v in functions.items():
            for f,d in v:
                funclist.append((n.__name__, f.__name__))
        methods.sort()
        funclist.sort()
        return (methods, funclist)


class Shell:

    @remote
    def run(self, cmd):
        """
        Run a shell command.
        @param cmd: The command & arguments.
        @type cmd: str
        @return: The command output.
        @rtype: str
        """
        f = os.popen(cmd)
        try:
            return f.read()
        finally:
            f.close()
            
            
@remote
def echo(something):
    return something

#
# Set the uuid to the hostname when not
# specified in the config.
#
if not plugin.getuuid():
    hostname = socket.gethostname()
    uuid = str(uuid4())
    if not hostname.startswith('localhost'):
        uuid = 'admin@%s' % hostname
    plugin.setuuid(uuid)
