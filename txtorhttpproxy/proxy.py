
from zope.interface import implementer, directlyProvides

from twisted.internet import defer
from twisted.web import http
from twisted.internet import reactor, protocol
from twisted.internet.endpoints import clientFromString
from twisted.protocols.portforward import Proxy
from twisted.protocols.policies import ProtocolWrapper, WrappingFactory
from twisted.python import log
from twisted.web.http import PotentialDataLoss
from twisted.web._newclient import ResponseDone
from twisted.web.iweb import IBodyProducer



class ProxyBodyProtocol(protocol.Protocol):
    """
    Protocol that proxies data sent to it.

    This is a helper for L{AgentProxyRequest}, which proxies the body and
    notifies the requesting AgentProxyRequest instance when data proxying
    is finished.
    """
    def __init__(self, request):
        """
        @param request: An instance of L{AgentProxyRequest}
        """
        self.request = request

    def dataReceived(self, data):
        """
        Immediately write the received that to our companion
        request class, an instance of L{AgentProxyRequest}
        """
        self.request.write(data)

    def connectionLost(self, reason):
        """
        Notify our companion request that data proxying is finished.
        """
        # XXX
        # do we care why a connection was lost?
        # i should probably rewrite this method

        if reason.check(ResponseDone):
            self.request.finish()
        elif reason.check(PotentialDataLoss):
            log.err("ProxyBodyProtocol connectionLost: PotentialDataLoss: %s" % (reason,))
            self.request.finish()
        else:
            log.err("ProxyBodyProtocol connectionLost: unknown reason: %s" % (reason,))


@implementer(IBodyProducer)
class StringProducer(object):

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class ShinyProxyClient(Proxy):
    def connectionMade(self):
        self.peer.setPeer(self)

        # Wire this and the peer transport together to enable
        # flow control (this stops connections from filling
        # this proxy memory when one side produces data at a
        # higher rate than the other can consume).

        # XXX does one of these not belong here for our purposes
        # of using the servers transport after it has already
        # received an http connection?
        ###self.transport.registerProducer(self.peer.transport, True)
        self.peer.transport.registerProducer(self.transport, True)

        # We're connected, everybody can read to their hearts content.
        self.peer.transport.resumeProducing()

class ShinyProxyClientFactory(protocol.Factory):
    noisey = True
    protocol = ShinyProxyClient

    def setServer(self, server):
        self.server = server

    def buildProtocol(self, *args, **kw):
        prot = protocol.Factory.buildProtocol(self, *args, **kw)
        prot.setPeer(self.server)
        return prot

class ProxyServerWithClientEndpoint(Proxy):

    clientProtocolFactory = ShinyProxyClientFactory

    def proxyConnectError(self, reason):
        log.err("ProxyServerWithClientEndpoint: proxyConnectError: reason: %s" % reason)

    def connectionMade(self):
        # Don't read anything from the connecting client until we have
        # somewhere to send it to.
        self.transport.pauseProducing()

        clientFactory = self.clientProtocolFactory()
        clientFactory.setServer(self)

        clientFactory.connectDeferred = self.factory.clientEndpoint.connect(clientFactory)
        clientFactory.connectDeferred.addErrback(self.proxyConnectError)

class ProxyServerFactoryWithClientEndpoint(protocol.Factory):
    """Factory for port forwarder."""

    noisey = True
    protocol = ProxyServerWithClientEndpoint

    def __init__(self, clientEndpoint):
        self.clientEndpoint = clientEndpoint


# XXX todo - replace wrapper style with proxyForInterface?
class PortforwardSwitchProtocol(ProtocolWrapper):
    """
    This class can wrap Twisted protocols to add support for switching to a
    TCP port-forwarding proxy.
    """

    def __init__(self, factory, wrappedProtocol):
        self.factory = factory
        self.wrappedProtocol = wrappedProtocol
        self.wrappedProtocol.wrapperProtocol = self
        self.portforwardStarted = False

    def buildProxyProtocol(self, endpoint):
        # XXX
        self.proxyFactory = ProxyServerFactoryWithClientEndpoint(endpoint)
        self.proxyProtocol = self.proxyFactory.buildProtocol(None)
        self.proxyProtocol.makeConnection(self.transport)

        # XXX
        self.portforwardStarted = True


    # Protocol relaying

    def dataReceived(self, data):
        if self.portforwardStarted:
            self.proxyProtocol.dataReceived(data)
        else:
            self.wrappedProtocol.dataReceived(data)

    def connectionLost(self, reason):
        self.factory.unregisterProtocol(self)
        self.wrappedProtocol.connectionLost(reason)

    # Transport relaying
    # XXX needs rewrite?



class ProtocolSwitcherWrappingFactory(WrappingFactory):

    noisey = True

    def __init__(self, wrappedFactory):
        self.wrappedFactory = wrappedFactory
        self.protocols = {}

    def proxyError(ignore=None):
        log.err('ProtocolSwitcherWrappingFactory: proxyError')

    def buildProtocol(self, addr):
        return self.protocol(self, self.wrappedFactory.buildProtocol(addr))


class AgentProxyRequest(http.Request):
    """
    A HTTP Request that proxies.

    This class uses the ProxyBodyProtocol helper class to retrieve
    the response data.
    """

    def __init__(self, channel, queued):
        """
        @param channel: the channel we're connected to.
        @param queued: are we in the request queue, or can we start writing to
            the transport?
        """
        http.Request.__init__(self, channel, queued)


    def requestReceived(self, command, path, version):
        log.msg("AgentProxyRequest: requestReceived: %s %s %s" % (command, path, version))

        self.command = command
        http.Request.requestReceived(self, command, path, version)


    def process(self):
        """
        Our parent class calls this method when our helper class
        ProxyBodyProtocol has signaled that the data retrieval is finished.
        We then set our response attributes such as response code, phrase
        and then send the data to the requestor.
        """

        if self.command == 'CONNECT':
            log.msg("CONNECT command received")

            def handleError(ing=None):
                log.err("endpoint proxy fail")

            # XXX todo: sanitize self.path?
            torEndpointDescriptor = "tor:%s" % self.path
            proxyPeerEndpoint = clientFromString(reactor, torEndpointDescriptor)


            # XXX
            self.parentProtocol.wrapperProtocol.buildProxyProtocol(proxyPeerEndpoint)

            return

        log.msg("AgentProxyRequest: requested uri %s from %s" % (self.uri, self.getClientIP()))

        # XXX proxy all requests with a bodyProducer
        self.content.seek(0,0)
        content = self.content.read()
        bodyProducer = StringProducer(content)
        self.content.seek(0,0)

        d = self.agent.request(self.method, self.uri, self.requestHeaders, bodyProducer)

        def agentCallback(response):
            log.msg(response)
            self.setResponseCode(response.code, response.phrase)

            for name, values in response.headers.getAllRawHeaders():
                self.responseHeaders.setRawHeaders(name, values)

            response.deliverBody(ProxyBodyProtocol(self))

        def agentErrback(failure):
            log.err("AgentProxyRequest: proxied response failure: %s" % (failure,))
            return failure

        d.addCallbacks(agentCallback, agentErrback)



class AgentProxy(http.HTTPChannel):
    """
    A HTTP proxy which uses the helper class AgentProxyRequest
    to proxy outgoing requests.
    """
    requestFactory = AgentProxyRequest

    # XXX can we get rid of these class attributes and make
    # this code work with the parent's class attributes?
    maxHeaders = 500 # max number of headers allowed per request
    length = 0
    persistent = 1
    __header = ''
    __first_line = 1
    __content = None

    def __init__(self, agent):
        """
        Create an L{AgentProxy}.

        @param agent: an IAgent instance used by our helper class AgentProxyRequest
            to send outbound HTTP requests
        """
        self.requestFactory.agent = agent
        self.requestFactory.parentProtocol = self
        http.HTTPChannel.__init__(self)



class AgentProxyFactory(http.HTTPFactory):
    """
    A factory for L{AgentProxy}, used by applications wishing to proxy
    incoming HTTP requests.

    @ivar agent: The IAgent instance used to make outbound HTTP requests
    on behalf of the HTTP client using this proxy
    """

    noisey = True

    def __init__(self, agent):
        self.agent = agent
        http.HTTPFactory.__init__(self)

    def buildProtocol(self, addr):
        return AgentProxy(self.agent)
