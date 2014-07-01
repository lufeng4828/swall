#coding:utf-8
__author__ = 'lufeng4828@163.com'

from swall.utils import node


@node
def ip(*args, **kwargs):
    """
    获取ip地址
    """
    return kwargs.get("node_ip")


@node
def role(*args, **kwargs):
    """
    获取角色
    """
    return kwargs.get("role")


@node
def node(*args, **kwargs):
    """
    获取节点
    """
    return kwargs.get("node_name")


@node
def agent(*args, **kwargs):
    """
    获取节点对应的代理名称
    """
    return kwargs.get("agent")
