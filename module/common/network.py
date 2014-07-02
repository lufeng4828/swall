#coding:utf-8
__author__ = 'lufeng4828@163.com'

import socket
import fcntl
import struct
import logging
import commands
from swall.utils import node

log = logging.getLogger()


@node
def get_ip(ifname="eth0", *args, **kwarg):
    """
    def get_ip(ifname="eth0") -> 获取对应网卡的ip地址
    @param ifname string:网卡名称
    @return string:ip地址
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,
        struct.pack('256s', ifname[:15])
    )[20:24])


@node
def get_ping(host="121.14.207.189", count=5, *args, **kwarg):
    """
    def get_ping(host="121.14.207.189", count=5, *args, **kwarg) -> 获取到某个地址的ping延迟
    @param host string:目标检测点
    @param count int:检测几次
    @return int:延迟数据，单位是毫秒
    """
    return commands.getoutput("ping %s -c %s -q | awk -F'/' '/rtt/{print $(NF-2)}'" % (host, count))