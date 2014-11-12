
==============
txtorhttpproxy
==============



overview
--------

txtorhttpproxy is a http proxy server that makes outbound connections over Tor...
with minimal support for RFC 2817 proxy CONNECT method initiating a TCP portforwarding tunnel.
However the `AgentProxyFactory` and `AgentProxy` classes can be used with any
implementation of the IAgent Twisted interface. Furthermore the `TorAgent` class
can be used as a drop in replacement in any application using the Twisted `Agent` class.



dependencies
------------

txtorsocksx - https://github.com/david415/txtorsocksx



install
-------

you can install txtorhttpproxy in your python virtual environment like this:

   $ pip install git+https://github.com/david415/txtorsocksx.git
   $ pip install git+https://github.com/david415/txtorhttpproxy.git



usage
-----

   (virtenv-txtorsocksx)human@computer:~/projects/txtorhttpproxy$ ./bin/torhttpproxy
   usage: torhttpproxy [-h] [--torSocksHostname TORSOCKSHOSTNAME]
                       [--torSocksPort TORSOCKSPORT] [--log LOG]
                       serverEndpoint
   torhttpproxy: error: too few arguments


run it like this:

   (virtenv-txtorsocksx)human@computer:~/projects/txtorhttpproxy$ ./bin/torhttpproxy --log - tcp:interface=127.0.0.1:8080
   2014-11-12 16:30:13+0000 [-] Log opened.
   2014-11-12 16:30:13+0000 [-] AgentProxyFactory (WrappingFactory) starting on 8080
   2014-11-12 16:30:13+0000 [-] Starting factory <txtorhttpproxy.proxy.AgentProxyFactory instance at 0x7f9e243827a0>
   2014-11-12 16:30:13+0000 [-] Starting factory <twisted.protocols.policies.WrappingFactory instance at 0x3db23b0>



contact
-------

Bugfixes, suggestions and feature requests welcome!

  - email dstainton415@gmail.com
  - gpg key ID 0x836501BE9F27A723
  - gpg fingerprint F473 51BD 87AB 7FCF 6F88  80C9 8365 01BE 9F27 A723

