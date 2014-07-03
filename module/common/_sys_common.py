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
def ROLE(*args, **kwargs):
    """
    获取角色
    """
    return kwargs.get("role")


@env
def NODE(*args, **kwargs):
    """
    获取节点
    """
    return kwargs.get("node_name")


@env
def PROJECT(*args, **kwargs):
    """
    获取节点对应的项目名称
    """
    return kwargs.get("project")


@env
def AGENT(*args, **kwargs):
    """
    获取节点对应的代理名称
    """
    return kwargs.get("agent")


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