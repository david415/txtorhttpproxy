
from zope.interface import implementer

from twisted.internet import defer
from twisted.web import http
from twisted.internet import reactor, protocol
from twisted.internet.endpoints import clientFromString
from twisted.protocols.portforward import Proxy, ProxyClient
from twisted.protocols.policies import ProtocolWrapper
from twisted.python import log
from twisted.web.http import PotentialDataLoss
from twisted.web.client import ResponseDone
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


class ShinyProxyClientFactory(protocol.Factory):
    """
    This is essentially the same as the Twisted ProxyClientFactory
    except that it inherits from Factory instead of ClientFactory.

    Twisted endpoint's (IStreamClientEndpoint) connect method expects
    a Factory instance not ClientFactory:
    https://twistedmatrix.com/documents/current/core/howto/endpoints.html
    ...which is why we do not have a `clientConnectionFailed` method.
    """
    protocol = ProxyClient

    def setServer(self, server):
        self.server = server

    def buildProtocol(self, *args, **kw):
        prot = protocol.Factory.buildProtocol(self, *args, **kw)
        prot.setPeer(self.server)
        return prot


class ProxyClientEndpointServer(Proxy):
    """
    Proxy server protocol class for proxying to an endpoint.
    """

    clientProtocolFactory = ShinyProxyClientFactory

    def connectionMade(self):
        # Don't read anything from the connecting client until we have
        # somewhere to send it to.
        self.transport.pauseProducing()

        clientFactory = self.clientProtocolFactory()
        clientFactory.setServer(self)

        clientFactory.connectDeferred = self.factory.clientEndpoint.connect(clientFactory)
        clientFactory.connectDeferred.addErrback(lambda r: self.clientConnectionFailed(r))

    def clientConnectionFailed(self, reason):
        log.err("ProxyClientEndpointServer: clientConnectionFailed: %s" % (reason,))


class ProxyClientEndpointServerFactory(protocol.Factory):
    """
    Factory for proxy server TCP port forwarder
    """

    noisy = True
    protocol = ProxyClientEndpointServer

    def __init__(self, clientEndpoint):
        """
        @param clientEndpoint: An instance of an object implementing
        the IStreamClientEndpoint interface.
        """
        self.clientEndpoint = clientEndpoint



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
            def handleError(ing=None):
                log.err("endpoint proxy fail")

            # XXX todo: sanitize self.path?
            torEndpointDescriptor = "tor:%s" % self.path
            log.msg("proxying CONNECT command to %s" % torEndpointDescriptor)

            proxyPeerEndpoint = clientFromString(reactor, torEndpointDescriptor)

            # XXX todo - send 200 OK via callback after
            # outbound proxy connection is established
            self.parentProtocol.buildProxyProtocol(proxyPeerEndpoint)
            self.parentProtocol.transport.write(b"HTTP/1.1 200 OK\r\n\r\n")
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
        self.portforwardStarted = False

        http.HTTPChannel.__init__(self)

    def buildProxyProtocol(self, endpoint):
        """
        Make this protocol relay received data to our client endpoint
        proxy protocol...
        """
        self.portforwardFactory = ProxyClientEndpointServerFactory(endpoint)
        self.portforwardProtocol = self.portforwardFactory.buildProtocol(None)
        self.portforwardProtocol.makeConnection(self.transport)
        self.portforwardStarted = True

    def dataReceived(self, data):
        if self.portforwardStarted:
            self.portforwardProtocol.dataReceived(data)
        else:
            http.HTTPChannel.dataReceived(self, data)

    def connectionLost(self, reason):
        if self.portforwardStarted:
            self.portforwardProtocol.connectionLost(reason)

        http.HTTPChannel.connectionLost(self, reason)


class AgentProxyFactory(http.HTTPFactory):
    """
    A factory for L{AgentProxy}, used by applications wishing to proxy
    incoming HTTP requests.

    @ivar agent: The IAgent instance used to make outbound HTTP requests
    on behalf of the HTTP client using this proxy
    """

    def __init__(self, agent):
        self.agent = agent
        http.HTTPFactory.__init__(self)

    def buildProtocol(self, addr):
        protocol = AgentProxy(self.agent)
        protocol.factory = self
        return protocol
