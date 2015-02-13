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
Defined Qpid broker objects.
"""

from logging import getLogger

from qpid.messaging import Connection as RealConnection
from qpid.messaging.transports import TRANSPORTS

from gofer.common import ThreadSingleton
from gofer.messaging.adapter.model import Broker, BaseConnection


log = getLogger(__name__)

# qpid transports
AMQP = 'amqp'
AMQPS = 'amqps'
TCP = 'tcp'
SSL = 'ssl'


class Connection(BaseConnection):
    """
    Represents a Qpid connection.
    """

    __metaclass__ = ThreadSingleton

    @staticmethod
    def add_transports():
        """
        Ensure that well-known AMQP services are mapped.
        """
        key = AMQP
        if key not in TRANSPORTS:
            TRANSPORTS[key] = TRANSPORTS[TCP]
        key = AMQPS
        if key not in TRANSPORTS:
            TRANSPORTS[key] = TRANSPORTS[SSL]

    @staticmethod
    def ssl_domain(broker):
        """
        Get SSL properties
        :param broker: A broker object.
        :type broker: gofer.messaging.adapter.model.Broker
        :return: The SSL properties
        :rtype: dict
        :raise: ValueError
        """
        domain = {}
        if broker.use_ssl():
            broker.ssl.validate()
            domain.update(
                ssl_trustfile=broker.ssl.ca_certificate,
                ssl_keyfile=broker.ssl.client_key,
                ssl_certfile=broker.ssl.client_certificate,
                ssl_skip_hostname_check=(not broker.ssl.host_validation))
        return domain

    def __init__(self, url):
        """
        :param url: The broker url.
        :type url: str
        """
        BaseConnection.__init__(self, url)
        self._impl = None

    def is_open(self):
        """
        Get whether the connection has been opened.
        :return: True if open.
        :rtype bool
        """
        return self._impl is not None

    def open(self):
        """
        Open the connection.
        """
        if self.is_open():
            # already open
            return
        broker = Broker.find(self.url)
        Connection.add_transports()
        domain = self.ssl_domain(broker)
        log.info('connecting: %s', broker)
        impl = RealConnection(
            host=broker.host,
            port=broker.port,
            tcp_nodelay=True,
            reconnect=True,
            transport=broker.url.scheme,
            username=broker.userid,
            password=broker.password,
            heartbeat=10,
            **domain)
        impl.attach()
        self._impl = impl
        log.info('connected: %s', broker.url)

    def session(self):
        """
        Open a session.
        :return The *real* channel.
        :rtype qpid.session.Session
        """
        return self._impl.session()

    def close(self):
        """
        Close the connection.
        """
        connection = self._impl
        self._impl = None

        try:
            connection.close()
        except Exception:
            pass
