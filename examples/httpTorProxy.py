#!/usr/bin/env python

import argparse
import sys

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString
from twisted.python import log

from txtorhttpproxy import AgentProxyFactory
from txtorhttpproxy import TorAgent


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("serverEndpoint")
    parser.add_argument("--socksPort", help="local Tor SOCKS port")
    parser.add_argument("--log", help="write logs. use '-' for stdout.")
    args = parser.parse_args()

    if args.log:
        if args.log == '-':
            log.startLogging(sys.stdout)
        else:
            log.startLogging(open(args.log,'a'))

    serverEndpoint = serverFromString(reactor, args.serverEndpoint)
    torAgent = TorAgent(reactor)
    connectDeferred = serverEndpoint.listen(AgentProxyFactory(torAgent))

    # XXX
    def clientConnectionFailed(factory, reason):
        log.err(reason)
        log.err("httpTorProxy: clientConnectionFailed")

    connectDeferred.addErrback(lambda r: clientConnectionFailed(f, r))


    reactor.run()


if __name__ == '__main__':
    main()


