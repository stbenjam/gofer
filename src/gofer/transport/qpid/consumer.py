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
Provides AMQP message consumer classes.
"""

from time import sleep
from logging import getLogger

from qpid.messaging import Empty

from gofer.messaging import auth
from gofer.messaging import model
from gofer.messaging.model import Envelope, search
from gofer.transport.consumer import Ack
from gofer.transport.qpid.endpoint import Endpoint


log = getLogger(__name__)


# --- utils ------------------------------------------------------------------


def subject(message):
    """
    Extract the message subject.
    :param message: The received message.
    :type message: qpid.messaging.Message
    :return: The message subject
    :rtype: str
    """
    return message.properties.get('qpid.subject')


# --- consumers --------------------------------------------------------------


class Reader(Endpoint):
    """
    An AMQP message reader.
    :ivar __opened: Indicates that open() has been called.
    :type __opened: bool
    :ivar __receiver: An AMQP receiver to read.
    :type __receiver: Receiver
    """
    
    def __init__(self, queue, **options):
        """
        :param queue: The queue to consumer.
        :type queue: gofer.transport.qpid.model.Queue
        :param options: Options passed to Endpoint.
        :type options: dict
        """
        Endpoint.__init__(self, **options)
        self.queue = queue
        self.__opened = False
        self.__receiver = None

    def open(self):
        """
        Open the reader.
        """
        Endpoint.open(self)
        self._lock()
        try:
            if self.__opened:
                return
            session = self.session()
            address = str(self.queue)
            self.__receiver = session.receiver(address)
            self.__opened = True
        finally:
            self._unlock()
    
    def close(self):
        """
        Close the reader.
        """
        self._lock()
        try:
            if not self.__opened:
                return
            self.__receiver.close()
            self.__opened = False
        finally:
            self._unlock()
        Endpoint.close(self)

    def get(self, timeout):
        """
        Get the next message.
        :param timeout: The read timeout.
        :type timeout: int
        :return: The next message, or (None).
        :rtype: qpid.messaging.Message
        :raises: auth.ValidationFailed
        """
        try:
            self.open()
            message = self.__receiver.fetch(timeout=timeout)
            try:
                auth.validate(self.authenticator, message.content)
            except auth.ValidationFailed:
                self.ack(message)
                raise
            return message
        except Empty:
            pass
        except auth.ValidationFailed:
            raise
        except Exception:
            log.error(self.id(), exc_info=1)
            sleep(10)

    def next(self, timeout=90):
        """
        Get the next envelope from the queue.
        :param timeout: The read timeout.
        :type timeout: int
        :return: A tuple of: (envelope, ack())
        :rtype: (Envelope, callable)
        :raises: model.InvalidRequest
        """
        message = self.get(timeout)
        if message:
            request = Envelope()
            request.load(message.content)
            request.subject = subject(message)
            request.ttl = message.ttl
            try:
                model.validate(request)
            except model.InvalidRequest:
                self.ack(message)
                raise
            log.debug('{%s} read next:\n%s', self.id(), request)
            return request, Ack(self, message)
        return None, None

    def search(self, sn, timeout=90):
        """
        Search the reply queue for the envelope with the matching serial #.
        :param sn: The expected serial number.
        :type sn: str
        :param timeout: The read timeout.
        :type timeout: int
        :return: The next envelope.
        :rtype: Envelope
        """
        return search(self, sn, timeout)
