
from twisted.web import http
from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.web.http import PotentialDataLoss
from twisted.web._newclient import ResponseDone


class ProxyBodyProtocol(protocol.Protocol):

    def __init__(self, request):
        self.request = request

    def dataReceived(self, data):
        self.request.write(data)

    def connectionLost(self, reason):
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

    ports = {'http': 80}

    def __init__(self, channel, queued, reactor=reactor, socksPort=None):
        http.Request.__init__(self, channel, queued)
        self.reactor = reactor
        self.socksPort = socksPort

    def process(self):

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
        self.requestFactory.agent = agent
        http.HTTPChannel.__init__(self)


class AgentProxyFactory(http.HTTPFactory):

    def __init__(self, agent):
        self.agent = agent
        http.HTTPFactory.__init__(self)

    def buildProtocol(self, addr):
        return AgentProxy(self.agent)
