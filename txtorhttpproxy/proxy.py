
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



class ProxyEndpointProtocol(Proxy):

    def connectionMade(self):
        log.msg("ProxyEndpointProtocol connectionMade")
        if self.factory.peerFactory.protocolInstance is None:
            log.msg("before pauseProducing")
            self.transport.pauseProducing()
        else:
            log.msg("before registerProducer")
            self.peer.setPeer(self)
            self.transport.registerProducer(self.peer.transport, True)
            self.peer.transport.registerProducer(self.transport, True)
            self.peer.transport.resumeProducing()

    def connectionLost(self, reason):
        log.msg("ProxyEndpointProtocol connectionLost: %s" % reason)
        self.transport.loseConnection()
        if self.factory.handleLostConnection is not None:
            self.factory.handleLostConnection()



class ProxyEndpointProtocolFactory(protocol.Factory):

    protocol = ProxyEndpointProtocol

    def __init__(self, handleLostConnection=None):
        log.msg("ProxyEndpointProtocolFactory __init__")
        self.peerFactory = None
        self.protocolInstance = None
        self.handleLostConnection = handleLostConnection

    def setPeerFactory(self, peerFactory):
        log.msg("ProxyEndpointProtocolFactory setPeerFactory")
        self.peerFactory = peerFactory

    def buildProtocol(self, *args, **kw):
        log.msg("ProxyEndpointProtocolFactory buildProtocol")
        self.protocolInstance = protocol.Factory.buildProtocol(self, *args, **kw)

        if self.peerFactory.protocolInstance is not None:
            log.msg("before factory call to protocol's setPeer")
            self.protocolInstance.setPeer(self.peerFactory.protocolInstance)
        return self.protocolInstance



class ProtocolSwitcherWrappingFactory(WrappingFactory, ProxyEndpointProtocolFactory):

    def __init__(self, wrappedFactory):
        self.wrappedFactory = wrappedFactory
        self.protocols = {}

    def buildProtocol(self, addr):
        protocol = self.protocol(self, self.wrappedFactory.buildProtocol(addr))
        protocol.wrappedProtocol.wrapperProtocol = protocol
        return protocol



class PortforwardSwitchProtocol(ProtocolWrapper, ProxyEndpointProtocol):
    """
    This class can wrap Twisted protocols to add support for switching to a
    TCP port-forwarding proxy.
    """
    portforwardStarted = False

    def dataReceived(self, data):
        if self.portforwardStarted:
            ProxyEndpointProtocol.dataReceived(self, data)
        else:
            ProtocolWrapper.dataReceived(self, data)

    def write(self, data):
        if self.portforwardStarted:
            ProxyEndpointProtocol.write(self, data)
        else:
            ProtocolWrapper.write(self, data)

    def connectionMade(self):
        if self.portforwardStarted:
            ProxyEndpointProtocol.connectionMade(self)
        else:
            ProtocolWrapper.connectionMade(self)

    def connectionLost(self, reason):
        if self.portforwardStarted:
            ProxyEndpointProtocol.connectionLost(self, reason)
        else:
            ProtocolWrapper.connectionLost(self, reason)

    def loseConnection(self):
        if self.portforwardStarted:
            ProxyEndpointProtocol.loseConnection(self)
        else:
            ProtocolWrapper.loseConnection(self)

    def writeSequence(self, seq):
        if self.portforwardStarted:
            ProxyEndpointProtocol.writeSequence(self, seq)
        else:
            ProtocolWrapper.writeSequence(self, seq)



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
                log.err("proxy fail")

            proxyClientFactory = ProxyEndpointProtocolFactory(handleLostConnection=handleError)
            proxyClientFactory.setPeerFactory(self.parentProtocol.wrapperProtocol.factory)

            # XXX todo --> *must* sanitize!
            torEndpointDescriptor = "tor:%s" % self.path
            proxyPeerEndpoint = clientFromString(reactor, torEndpointDescriptor)
            log.msg("proxyPeerEndpoint: %s" % proxyPeerEndpoint)

            log.msg("<<------------------------------------------------------------------------------")
            self.parentProtocol.wrapperProtocol.portforwardStarted = True

            ProtocolSwitcherWrappingFactory.setPeerFactory(self.parentProtocol.wrapperProtocol.factory, proxyClientFactory)
            self.parentProtocol.wrapperProtocol.factory.handleLostConnection = handleError
            #ProxyEndpointProtocol.makeConnection(self.parentProtocol.wrapperProtocol, self.parentProtocol.wrapperProtocol)


            # connect client endpoint
            proxyPeerConnectDeferred = proxyPeerEndpoint.connect(proxyClientFactory)
            proxyPeerConnectDeferred.addErrback(handleError)

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

    def __init__(self, agent, factory=None):
        """
        Create an L{AgentProxy}.

        @param agent: an IAgent instance used by our helper class AgentProxyRequest
            to send outbound HTTP requests
        """
        self.requestFactory.agent = agent
        self.requestFactory.parentFactory = factory
        self.requestFactory.parentProtocol = self
        http.HTTPChannel.__init__(self)



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
        return AgentProxy(self.agent, factory=self)
