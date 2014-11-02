#!/usr/bin/env python

import sys

from twisted.internet import reactor
from twisted.python import log
from twisted.web.http_headers import Headers

from txtorproxyhttp import TorAgent


def cbBody(body):
    print 'Response body:'
    print body

def main():
    log.startLogging(sys.stdout)
    agent = TorAgent(reactor)
    url = 'http://icanhazip.com'
    d = agent.request(
        'GET', url,
        Headers({'User-Agent': ['Firefox']}),
        None)
    def cbRequest(response):
        print 'Response version:', response.version
        print 'Response code:', response.code
        print 'Response phrase:', response.phrase
        print 'Response headers:'
        print pformat(list(response.headers.getAllRawHeaders()))
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        return finished

    d.addCallback(cbRequest)

    def cbShutdown(ignored):
        reactor.stop()
    d.addBoth(cbShutdown)

    reactor.run()

if __name__ == "__main__":
    main()
