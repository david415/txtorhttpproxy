#!/usr/bin/env python

import argparse

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString

from txtorproxyhttp import TorProxyFactory


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("serverEndpoint")
    parser.add_argument("--socksPort", help="local Tor SOCKS port")
    args = parser.parse_args()

    serverEndpoint = serverFromString(reactor, args.serverEndpoint)
    connectDeferred = serverEndpoint.listen(TorProxyFactory(socksPort=args.socksPort))

    # XXX
    def clientConnectionFailed(factory, reason):
        print reason
        print "httpTorProxy: clientConnectionFailed"

    connectDeferred.addErrback(lambda r: clientConnectionFailed(f, r))


    reactor.run()


if __name__ == '__main__':
    main()


