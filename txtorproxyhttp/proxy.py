
from twisted.web import proxy, http, client
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString
from twisted.python import log

from txtorproxyhttp.agent import TorAgent

import urlparse


class TorProxyRequest(http.Request):

    ports = {'http': 80}

    def __init__(self, channel, queued, reactor=reactor):
        http.Request.__init__(self, channel, queued)
        self.reactor = reactor

    def process(self):

        headers = self.getAllHeaders().copy()

        # XXX
        agent = TorAgent(self.reactor)
        d = agent.request(self.method, self.uri, headers, None)

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

    def __init__(self, reactor=reactor, socksPort=None, newCircuit=None):
        self.reactor = reactor
        self.socksPort = socksPort
        self.newCircuit = newCircuit
        self.pool = pool = client.HTTPConnectionPool(self.reactor)
        #self.proxyAgent = client.ProxyAgent(self.proxyEndpoint, reactor=self.reactor, pool=self.pool)
        http.HTTPChannel.__init__(self)

    def lineReceived(self, line):
        """copied from twisted... and then modified"""
        self.resetTimeout()

        if self.__first_line:
            # if this connection is not persistent, drop any data which
            # the client (illegally) sent after the last request.
            if not self.persistent:
                self.dataReceived = self.lineReceived = lambda *args: None
                return

            # IE sends an extraneous empty line (\r\n) after a POST request;
            # eat up such a line, but only ONCE
            if not line and self.__first_line == 1:
                self.__first_line = 2
                return

            # XXX

            # create a new Request object
            request = self.requestFactory(self, len(self.requests))
            self.requests.append(request)

            self.__first_line = 0
            parts = line.split()
            if len(parts) != 3:
                self.transport.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                self.transport.loseConnection()
                return
            log.msg("PARTS")
            log.msg(parts)
            command, request, version = parts
            self._command = command
            self._path = request
            self._version = version
        elif line == b'':
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = ''
            self.allHeadersReceived()
            if self.length == 0:
                self.allContentReceived()
            else:
                self.setRawMode()
        elif line[0] in b' \t':
            self.__header = self.__header + '\n' + line
        else:
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = line


class TorProxyFactory(http.HTTPFactory):

    def __init__(self, socksPort=None, newCircuit=None):
        self.socksPort = socksPort
        self.newCircuit = newCircuit
        http.HTTPFactory.__init__(self)

    def buildProtocol(self, addr):
        return TorProxy(socksPort=self.socksPort, newCircuit=self.newCircuit)


