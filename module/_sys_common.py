#coding:utf-8
__author__ = 'lufeng4828@163.com'

import time
from swall.utils import env


@env
def IP(*args, **kwargs):
    """
    获取ip地址
    """
    return kwargs.get("node_ip")

@env
def NODE(*args, **kwargs):
    """
    获取节点
    """
    return kwargs.get("node_name")


@env
def DATE(*args, **kwargs):
    """
    返回当前日期，格式为2014-07-03
    """
    return time.strftime("%Y-%m-%d", time.localtime())


@env
def TIME(*args, **kwargs):
    """
    返回当前时间，格式为12:00:00
    """
    return time.strftime("%H:%M:%S", time.localtime())