
import sys
from zope.interface import implementer

from twisted.internet import reactor
from twisted.web.client import Agent, BrowserLikePolicyForHTTPS, _AgentBase, _URI
from twisted.web.iweb import IAgent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS
from twisted.web.error import SchemeNotSupported
from twisted.python import log
from twisted.internet.endpoints import clientFromString

from txsocksx.tls import TLSWrapClientEndpoint


@implementer(IAgent)
class TorAgent(Agent):
    """copied from twisted.web.client.Agent and modified"""
    def __init__(self, reactor,
                 contextFactory=BrowserLikePolicyForHTTPS(),
                 connectTimeout=None, bindAddress=None,
                 pool=None, torSocksPort=None, newCircuit=None):

        _AgentBase.__init__(self, reactor, pool)
        if not IPolicyForHTTPS.providedBy(contextFactory):
            warnings.warn(
                repr(contextFactory) +
                " was passed as the HTTPS policy for an Agent, but it does "
                "not provide IPolicyForHTTPS.  Since Twisted 14.0, you must "
                "pass a provider of IPolicyForHTTPS.",
                stacklevel=2, category=DeprecationWarning
            )
            contextFactory = _DeprecatedToCurrentPolicyForHTTPS(contextFactory)

        self._policyForHTTPS = contextFactory
        self._connectTimeout = connectTimeout
        self._bindAddress = bindAddress

        Agent.__init__(self, reactor, contextFactory=BrowserLikePolicyForHTTPS(),
                 connectTimeout=None, bindAddress=None,
                 pool=None)

        self.torSocksPort = torSocksPort
        if newCircuit is None:
            self.newCircuit = False
        else:
            self.newCircuit = True

    def _getEndpoint(self, scheme, host, port):
        """
        Get an endpoint for the given host and port, using a transport
        selected based on scheme. Either Tor with TLS or Tor without TLS.

        @param scheme: A string like C{'http'} or C{'https'} (the only two
            supported values) to use to determine how to establish the
            connection.

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
        if self.torSocksPort:
            self.endpointDescriptor += ":socksPort=%s" % (self.torSocksPort,)
        if self.newCircuit:
            self.endpointDescriptor += ":newCircuit=Yes"

        if scheme == 'http':
            log.msg("tor connect %s" % (self.endpointDescriptor,))
            return clientFromString(self._reactor, self.endpointDescriptor)
        elif scheme == 'https':
            log.msg("tor connect with tls %s" % (self.endpointDescriptor,))
            return TLSWrapClientEndpoint(clientFromString(self._reactor, self.endpointDescriptor))
        else:
            raise SchemeNotSupported("Unsupported scheme: %r" % (scheme,))


    def request(self, method, uri, headers=None, bodyProducer=None):
        parsedURI = _URI.fromBytes(uri)
        try:
            endpoint = self._getEndpoint(parsedURI.scheme, parsedURI.host,
                                         parsedURI.port)
        except SchemeNotSupported:
            return defer.fail(Failure())
        key = (parsedURI.scheme, parsedURI.host, parsedURI.port)
        return self._requestWithEndpoint(key, endpoint, method, parsedURI,
                                         headers, bodyProducer,
                                         parsedURI.originForm)
