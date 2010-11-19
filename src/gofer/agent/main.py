#
# Copyright (c) 2010 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#

import sys
import os
from getopt import getopt
from gofer import *
from gofer.agent import *
from gofer.agent.action import Action
from gofer.agent.plugin import PluginLoader
from gofer.agent.lock import Lock, LockFailed
from gofer.agent.config import Config
from gofer.agent.identity import Identity
from gofer.agent.logutil import getLogger
from gofer.messaging import Queue
from gofer.messaging.broker import Broker
from gofer.messaging.base import Agent as Base
from gofer.messaging.consumer import RequestConsumer
from time import sleep
from threading import Thread

log = getLogger(__name__)


class ActionThread(Thread):
    """
    Run actions independantly of main thread.
    @ivar actions: A list of actions to run.
    @type actions: [L{Action},..]
    """
    
    def __init__(self, actions):
        """
        @param actions: A list of actions to run.
        @type actions: [L{Action},..]
        """
        self.actions = actions
        Thread.__init__(self, name='Actions')
   
    def run(self):
        """
        Run actions.
        """
        while True:
            for action in self.actions:
                action()
            sleep(10)
            

class Agent(Base):
    """
    Pulp agent.
    """

    def __init__(self, actions=[]):
        uuid = self.uuid()
        actionThread = ActionThread(actions)
        actionThread.start()
        queue = Queue(uuid)
        cfg = Config()
        url = cfg.messaging.url
        if url and isinstance(url, str):
            broker = Broker.get(url)
            broker.cacert = cfg.messaging.cacert
            broker.clientcert = cfg.messaging.clientcert
            consumer = RequestConsumer(queue, url=url)
            Base.__init__(self, consumer)
        else:
            log.warn('agent {%s} has messaging disabled.', uuid)
        log.info('agent {%s} - started.', uuid)
        actionThread.join()

    def uuid(self):
        """
        Get agent uuid.
        @return: The agent UUID.
        """
        ident = Identity()
        while True:
            uuid = ident.getuuid()
            if uuid:
                return uuid
            log.info('Not associated.')
            sleep(90)


class AgentLock(Lock):
    """
    Agent lock ensure that agent only has single instance running.
    @cvar PATH: The lock file absolute path.
    @type PATH: str
    """

    PATH = '/var/run/goferd.pid'

    def __init__(self):
        Lock.__init__(self, self.PATH)


def start(daemon=True):
    """
    Agent main.
    Add recurring, time-based actions here.
    All actions must be subclass of L{action.Action}.
    """
    lock = AgentLock()
    try:
        lock.acquire(wait=False)
    except LockFailed, e:
        raise Exception('Agent already running')
    if daemon:
        daemonize(lock)
    try:
        pl = PluginLoader()
        pl.load()
        actions = []
        for cls, interval in Action.actions:
            action = cls(**interval)
            actions.append(action)
        agent = Agent(actions)
        agent.close()
    finally:
        lock.release()

def usage():
    """
    Show usage.
    """
    s = []
    s.append('\ngoferd <optoins>')
    s.append('  -h, --help')
    s.append('      Show help')
    s.append('  -c, --console')
    s.append('      Run in the foreground and not as a daemon.')
    s.append('      default: 0')
    s.append('\n')
    print '\n'.join(s)

def daemonize(lock):
    """
    Daemon configuration.
    """
    pid = os.fork()
    if pid == 0: # child
        os.setsid()
        os.chdir('/')
        os.close(0)
        os.close(1)
        os.close(2)
        dn = os.open('/dev/null', os.O_RDWR)
        os.dup(dn)
        os.dup(dn)
        os.dup(dn)
    else: # parent
        lock.update(pid)
        os.waitpid(pid, os.WNOHANG)
        os._exit(0)

def main():
    daemon = True
    opts, args = getopt(sys.argv[1:], 'hc', ['help','console'])
    for opt,arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        if opt in ('-c', '--console'):
            daemon = False
            continue
    start(daemon)

if __name__ == '__main__':
    main()