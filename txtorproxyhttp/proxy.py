
from twisted.web import proxy, http
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString
from twisted.python import log

import urlparse


class TorProxyRequest(proxy.Request):
    """copied from twisted.web.proxy.ProxyRequest... and modified"""
    protocols = {'http': proxy.ProxyClientFactory}
    ports = {'http': 80}

    def __init__(self, channel, queued, reactor=reactor, socksPort=None):
        proxy.Request.__init__(self, channel, queued)
        self.reactor = reactor
        self.socksPort = socksPort

    def process(self):

        log.msg("Request %s from %s" % (self.uri, self.getClientIP()))

        parsed = urlparse.urlparse(self.uri)
        protocol = parsed[0]
        host = parsed[1]
        port = self.ports[protocol]
        if ':' in host:
            host, port = host.split(':')
            port = int(port)
        rest = urlparse.urlunparse(('', '') + parsed[2:])
        if not rest:
            rest = rest + '/'
        class_ = self.protocols[protocol]
        headers = self.getAllHeaders().copy()
        if 'host' not in headers:
            headers['host'] = host
        self.content.seek(0, 0)
        s = self.content.read()
        clientFactory = class_(self.method, rest, self.clientproto, headers,
                               s, self)
        # XXX
        if self.socksPort:
            self.endpointDescriptor = "tor:host=%s:port=%s:socksPort=%s" % (host, port, self.socksPort)
        else:
            self.endpointDescriptor = "tor:host=%s:port=%s" % (host, port)
        torEndpoint = clientFromString(self.reactor, self.endpointDescriptor)
        d = torEndpoint.connect(clientFactory)

        @d.addErrback
        def _gotError(error):
            # XXX
            log.err(error)
            log.err("TorProxyRequest: failure to connect: %s" % self.endpointDescriptor)


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


