#!/usr/bin/env python


import sys

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.python import log
from twisted.web.client import HTTPConnectionPool
from twisted.web.client import ProxyAgent
from txtorproxyhttp import AgentProxy, AgentProxyFactory
from txtorproxyhttp import TorAgent


def main():
        
    log.startLogging(sys.stdout)

    startPort = 3000

    lastServerEndpoint = 'tcp:interface=127.0.0.1:%s' % startPort
    torAgent = TorAgent(reactor)
    serverEndpoint = serverFromString(reactor, lastServerEndpoint)
    connectDeferred = serverEndpoint.listen(AgentProxyFactory(torAgent))

    endpoint = []
    agent = []
    for x in range(10):
        endpoint = clientFromString(reactor, "tcp:127.0.0.1:%s" % (startPort + x))
        proxyAgent = ProxyAgent(endpoint)
        serverEndpoint = serverFromString(reactor, "tcp:interface=127.0.0.1:%s" % (startPort + x + 1))
        
        connectDeferred = serverEndpoint.listen(AgentProxyFactory(proxyAgent))


    # XXX
    def clientConnectionFailed(factory, reason):
        log.err(reason)
        log.err("httpTorProxy: clientConnectionFailed")

    connectDeferred.addErrback(clientConnectionFailed)


    reactor.run()


if __name__ == '__main__':
    main()


