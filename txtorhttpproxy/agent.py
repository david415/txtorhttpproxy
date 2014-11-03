
from zope.interface import implementer

from twisted.web.client import Agent, _URI
from twisted.web.iweb import IAgent
from twisted.web.error import SchemeNotSupported
from twisted.python import log
from twisted.internet.endpoints import clientFromString


@implementer(IAgent)
class TorAgent(Agent):
    """L{TorAgent} is a very basic Torified HTTP client. Currently it supports
    I{HTTP} but hopefully soon will also support I{HTTPS} scheme URIs.

    This class was inspired by the core Twisted HTTP Agent class
    (twisted.web.client.Agent)... and is thus a drop-in replacement
    for the Agent class.

    @ivar _pool: An L{HTTPConnectionPool} instance.

    @ivar _connectTimeout: If not C{None}, the timeout passed to
    L{TCP4ClientEndpoint} or C{SSL4ClientEndpoint} for specifying the
    connection timeout.

    @ivar _bindAddress: If not C{None}, the address passed to
    L{TCP4ClientEndpoint} or C{SSL4ClientEndpoint} for specifying the local
    address to bind to.
    """
    def __init__(self, reactor,
                 connectTimeout=None, bindAddress=None,
                 pool=None, torSocksHostname=None, torSocksPort=None):
        """
        Create a L{TorAgent}.

        @param reactor: A provider of
            L{twisted.internet.interfaces.IReactorTCP}
            to place outgoing connections.
        @type reactor: L{twisted.internet.interfaces.IReactorTCP}.

        @param connectTimeout: The amount of time that this L{Agent} will wait
            for the peer to accept a connection.
        @type connectTimeout: L{float}

        @param bindAddress: The local address for client sockets to bind to.
        @type bindAddress: L{bytes}

        @param pool: An L{HTTPConnectionPool} instance, or C{None}, in which
            case a non-persistent L{HTTPConnectionPool} instance will be
            created.
        @type pool: L{HTTPConnectionPool}

        @param torSocksHostname: A C{str} giving the tor SOCKS hostname
            that this TorAgent will use for outbound Tor connections.

        @param torSocksPort: An C{int} giving the SOCKS port number that will be used
            for outbound Tor connections.
        """
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
            return clientFromString(self._reactor, self.endpointDescriptor)
        else:
            raise SchemeNotSupported("Unsupported scheme: %r" % (scheme,))


    def request(self, method, uri, headers=None, bodyProducer=None):
        """
        Issue a request to the server indicated by the given C{uri}.

        An existing connection from the connection pool may be used or a new one may be created.
        Without additional modifications this connection pool may not be very useful because
        each connection in the pool will use the same Tor circuit.

        Currently only the I{HTTP} scheme is supported in C{uri}.

        @see: L{twisted.web.iweb.IAgent.request}
        """
        parsedURI = _URI.fromBytes(uri)
        endpoint = self._getEndpoint(parsedURI.scheme, parsedURI.host,
                                         parsedURI.port)
        key = (parsedURI.scheme, parsedURI.host, parsedURI.port)
        return self._requestWithEndpoint(key, endpoint, method, parsedURI,
                                         headers, bodyProducer, parsedURI.originForm)
