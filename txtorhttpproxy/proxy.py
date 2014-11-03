
from twisted.web import http
from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.web.http import PotentialDataLoss
from twisted.web._newclient import ResponseDone


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

        self.request.finish()
        if reason.check(ResponseDone):
            # XXX
            pass
        elif reason.check(PotentialDataLoss):
            log.err("ProxyBodyProtocol connectionLost: PotentialDataLoss: %s" % (reason,))
        else:
            log.err("ProxyBodyProtocol connectionLost: unknown reason: %s" % (reason,))


class AgentProxyRequest(http.Request):
    """
    A HTTP Request that proxies.

    This class uses the ProxyBodyProtocol helper class to retrieve
    the response data.
    """
    ports = {'http': 80}

    def __init__(self, channel, queued):
        """
        @param channel: the channel we're connected to.
        @param queued: are we in the request queue, or can we start writing to
            the transport?
        """
        http.Request.__init__(self, channel, queued)

    def process(self):
        """
        Our parent class calls this method when our helper class
        ProxyBodyProtocol has signaled that the data retrieval is finished.
        We then set our response attributes such as response code, phrase
        and then send the data to the requestor.
        """

        log.msg("AgentProxyRequest: requested uri %s from %s" % (self.uri, self.getClientIP()))

        # XXX TODO proxy POST requests

        d = self.agent.request(self.method, self.uri, self.requestHeaders, None)

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
        return AgentProxy(self.agent)
