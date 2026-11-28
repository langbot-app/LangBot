"""Constrain disposable permission E2E Python children to loopback networking."""

import ipaddress
import socket


def _local(host):
    if host in ('localhost', None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_bind = socket.socket.bind
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo


def bind(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        host, *rest = address
        if host in ('', '0.0.0.0', '::'):
            host = '::1' if sock.family == socket.AF_INET6 else '127.0.0.1'
        if not _local(host):
            raise PermissionError('Permission E2E only permits loopback binds')
        address = (host, *rest)
    return _bind(sock, address)


def connect(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6) and not _local(address[0]):
        raise PermissionError('Permission E2E blocks external connections')
    return _connect(sock, address)


def connect_ex(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6) and not _local(address[0]):
        raise PermissionError('Permission E2E blocks external connections')
    return _connect_ex(sock, address)


def getaddrinfo(host, *args, **kwargs):
    if not _local(host):
        raise PermissionError('Permission E2E blocks external name resolution')
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.bind = bind
socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
