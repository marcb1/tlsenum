from __future__ import absolute_import, division, print_function

import socket

import click

from tlsenum.parsedDictionary import parsedDictionary

from construct import UBInt16

from tlsenum.parse_hello import (
    ClientHello, Extensions, HandshakeFailure, ServerHello,
    construct_sslv2_client_hello
)
from tlsenum.mappings import (
    CipherSuites, ECCurves, ECPointFormat, TLSProtocolVersion
)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def send_client_hello(host, port, data):
    """
    Sends a ClientHello message in bytes.

    Returns a ServerHello message in bytes

    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.send(data)

        server_hello = s.recv(5)

        # This is to handle the case where the server fails
        # to respond instead of a returning a handshake failure.
        if len(server_hello) == 0:
            raise HandshakeFailure()

        server_hello += s.recv(UBInt16("length").parse(server_hello[3:5]))

        return server_hello

    except socket.error:
        raise HandshakeFailure()


def send_sslv2_client_hello(host, port):
    """
    Sends a SSLv2 ClientHello message in bytes.

    If server supports SSLv2, returns None. Else raise a HandshakeFailure().

    """
    data = construct_sslv2_client_hello()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.send(data)

        server_hello = s.recv(3)

        if len(server_hello) == 0:
            raise HandshakeFailure()

        if server_hello[2] == 4:
            pass
        else:
            raise HandshakeFailure()

    except socket.error:
        raise HandshakeFailure()



def get_supported_cipher_suites(host, port, client_hello, cipher_suites_list):
    supported_cipher_suites = []

    try:
        server_hello = send_client_hello(host, port, client_hello.build())
        server_hello = ServerHello.parse_server_hello(server_hello)
    except HandshakeFailure:
        pass

    if server_hello.deflate:
        support_cipher_suites.append("Deflate: supported")
    else:
        supported_cipher_suites.append("Deflate: not supported")

    client_hello.deflate = False

    while True:
        try:
            server_hello = send_client_hello(host, port, client_hello.build())
            server_hello = ServerHello.parse_server_hello(server_hello)
        except (HandshakeFailure, ValueError) as e:
            break

        supported_cipher_suites.append(server_hello.cipher_suite)
        cipher_suites_list.remove(server_hello.cipher_suite)

    return supported_cipher_suites;


def get_supported_tls_versions(host, port, client_hello):
    supported_tls_versions = []

    try:
        send_sslv2_client_hello(host, port)
        supported_tls_versions.append("2.0")
    except HandshakeFailure:
        pass

    for i in TLSProtocolVersion:
        client_hello.protocol_version = i
        try:
            server_hello = send_client_hello(host, port, client_hello.build())
            server_hello = ServerHello.parse_server_hello(server_hello)
        except(HandshakeFailure, ValueError) as e:
            continue

        supported_tls_versions.append(server_hello.protocol_version)

    supported_tls_versions = sorted(
        list(set(supported_tls_versions)),
        key=lambda x: 0 if x == "2.0" else TLSProtocolVersion.index(x) + 1
    )
    return supported_tls_versions;


def get_tls_and_ciphers(host, port):
      cipher_suites_list = [i.name for i in CipherSuites]
      supported_cipher_suites = [];
      supported_tls_versions = [];

      extension = Extensions()
      extension.sni = host
      extension.ec_curves = [i.name for i in ECCurves]
      extension.ec_point_format = [i.name for i in ECPointFormat]

      client_hello = ClientHello()
      client_hello.deflate = False
      client_hello.extensions = extension.build()
      client_hello.cipher_suites = cipher_suites_list
      supported_tls_versions = get_supported_tls_versions(host, port, client_hello)

      if len(supported_tls_versions) > 0:
        client_hello.protocol_version = supported_tls_versions[-1]
        client_hello.deflate = True

        supported_cipher_suites = get_supported_cipher_suites(host, port, client_hello, cipher_suites_list)
      return supported_cipher_suites, supported_tls_versions
 

@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("host", type=click.STRING)
@click.argument("port", type=click.INT)
def cli(host, port):
    """
    A command line tool to enumerate TLS cipher-suites supported by a server.
    """
    supported_cipher_suites, supported_tls_versions = get_tls_and_ciphers(host, port)
    print("TLS Versions supported by server: {0}".format(
        ", ".join(supported_tls_versions)
    ))

    print("Supported Cipher suites in order of priority: ")
    for i in supported_cipher_suites:
        print(i)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("file_name", type=click.STRING)
def cli2(file_name):
    """
    A command line tool to enumerate TLS cipher-suites supported by a server from a file with a list of servers.
    """
    print("Reading input file and parsing list of websites.");
    tls_versions = parsedDictionary()
    cipher_suites = parsedDictionary()

    f = open(file_name, "r" )
    lines = [line.rstrip('\n') for line in f]
    f.close()

    for i in range(0, len(lines)):
        host = lines[i]
        port = 443
        print("Enumerating tls ciphers: " + lines[i])
        supported_cipher_suites, supported_tls_versions = get_tls_and_ciphers(host, port)
        tls_versions.add_list(supported_tls_versions)
        cipher_suites.add_list(supported_cipher_suites)

    tls_versions.sortByValue()
    cipher_suites.sortByValue()
    print(cipher_suites.Dict)
    print(tls_versions.Dict)
