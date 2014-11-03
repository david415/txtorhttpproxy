
from zope.interface import implementer

from twisted.web.client import Agent, _URI
from twisted.web.iweb import IAgent
from twisted.web.error import SchemeNotSupported
from twisted.python import log
from twisted.internet.endpoints import clientFromString


@implementer(IAgent)
class TorAgent(Agent):
    """copied from twisted.web.client.Agent and modified"""
    def __init__(self, reactor,
                 connectTimeout=None, bindAddress=None,
                 pool=None, torSocksHostname=None, torSocksPort=None):

        Agent.__init__(self, reactor,connectTimeout=None, bindAddress=None, pool=None)

        self.torSocksHostname = torSocksHostname
        self.torSocksPort = torSocksPort

        self._connectTimeout = connectTimeout
        self._bindAddress = bindAddress


    def _getEndpoint(self, scheme, host, port):
        """
        Get Tor endpoint for the given host and port, using a transport
        selected based on scheme. Currently only supports http... but
        perhaps we'll fix https later.

        @param scheme: The string C{'http'} (currently the only two supported value)
            to use to determine how to establish the connection.

        @param host: A C{str} giving the hostname which will be connected to in
            order to issue a request.

        @param port: An C{int} giving the port number the connection will be
            on.

        @return: An endpoint which can be used to connect to given address.
        """
        kwargs = {}
        if self._connectTimeout is not None:
            kwargs['timeout'] = self._connectTimeout
        kwargs['bindAddress'] = self._bindAddress

        self.endpointDescriptor = "tor:host=%s:port=%s" % (host, port)
        if self.torSocksHostname:
            self.endpointDescriptor += ":socksHostname=%s" % (self.torSocksHostname,)
        if self.torSocksPort:
            self.endpointDescriptor += ":socksPort=%s" % (self.torSocksPort,)

        if scheme == 'http':
            log.msg("tor connect %s" % (self.endpointDescriptor,))
            return clientFromString(self._reactor, self.endpointDescriptor)
        else:
            raise SchemeNotSupported("Unsupported scheme: %r" % (scheme,))


    def request(self, method, uri, headers=None, bodyProducer=None):
        parsedURI = _URI.fromBytes(uri)
        endpoint = self._getEndpoint(parsedURI.scheme, parsedURI.host,
                                         parsedURI.port)
        key = (parsedURI.scheme, parsedURI.host, parsedURI.port)
        return self._requestWithEndpoint(key, endpoint, method, parsedURI,
                                         headers, bodyProducer, parsedURI.originForm)
