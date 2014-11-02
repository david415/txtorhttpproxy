
import urlparse

from twisted.web import proxy, http
from twisted.internet import reactor, protocol, defer
from twisted.internet.endpoints import clientFromString
from twisted.python import log
from twisted.web.client import PartialDownloadError
from twisted.web.http import PotentialDataLoss
from twisted.web._newclient import ResponseDone

from .agent import TorAgent

# yay debugging
#defer.setDebugging(True)

class ProxyBodyProtocol(protocol.Protocol):

    def __init__(self, request):
        log.msg("proxybodyprotocol init")
        self.request = request

    def dataReceived(self, data):
        log.msg(data)
        self.request.write(data)

    def connectionLost(self, reason):
        """
        Deliver the accumulated response bytes to the waiting L{Deferred}, if
        the response body has been completely received without error.
        """
        log.msg("connection lost")
        if reason.check(ResponseDone):
            self.request.finish()

        elif reason.check(PotentialDataLoss):
            log.err("connectionLost")
            log.err(reason)


class TorProxyRequest(http.Request):
    """copied from twisted.web.proxy.ProxyRequest... and modified"""

    ports = {'http': 80}

    def __init__(self, channel, queued, reactor=reactor, socksPort=None):
        http.Request.__init__(self, channel, queued)
        self.reactor = reactor
        self.socksPort = socksPort

    def process(self):

        log.msg("Request %s from %s" % (self.uri, self.getClientIP()))

        headers = self.getAllHeaders().copy()
        if 'host' not in headers:
            headers['host'] = host

        # XXX
        #self.content.seek(0, 0)
        #s = self.content.read()

        log.msg("URI %s" % self.uri)

        self.content.seek(0, 0)
        s = self.content.read()

        log.msg("request content %s" % s)

        agent = TorAgent(reactor)
        d = agent.request(self.method, self.uri, self.requestHeaders, None)

        def agentCallback(response):
            log.msg(response)
            self.setResponseCode(response.code, response.phrase)

            for name, values in response.headers.getAllRawHeaders():
                log.msg("YOOYO name %s values %s" % (name, values))
                self.responseHeaders.setRawHeaders(name, values)

            log.msg("before deliverBody")
            response.deliverBody(ProxyBodyProtocol(self))
            log.msg("after deliverBody")

        def agentErrback(failure):
            log.err(failure)
            return failure

        d.addCallbacks(agentCallback, agentErrback)


class TorProxy(http.HTTPChannel):
    requestFactory = TorProxyRequest

    # XXX can we get rid of these class attributes and make
    # this code work with the parent's class attributes?
    maxHeaders = 500 # max number of headers allowed per request
    length = 0
    persistent = 1
    __header = ''
    __first_line = 1
    __content = None

    def __init__(self, socksPort=None):
        self.socksPort = socksPort
        self.requestFactory.socksPort = self.socksPort
        http.HTTPChannel.__init__(self)


class TorProxyFactory(http.HTTPFactory):

    def __init__(self, socksPort=None):
        self.socksPort = socksPort
        http.HTTPFactory.__init__(self)

    def buildProtocol(self, addr):
        return TorProxy(socksPort=self.socksPort)
