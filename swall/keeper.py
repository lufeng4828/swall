#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import logging
from swall.utils import Conf
from swall.mq import MQ

log = logging.getLogger()


class Keeper(object):
    """
    实现keeper一些基础功能
    """

    def __init__(self, config):
        self.main_conf = Conf(config["swall"])
        self.mq = MQ(config)

    def is_valid(self, node_name):
        """
        检查某个节点是否正常
        """
        return self.mq.is_valid(node_name)

    def get_valid_nodes(self):
        """
        获取所有可用的节点
        @return dict:["node1","node2","node3","nodeN"]
        """
        nodes = self.mq.get_nodes()
        valid_nodes = [key for key in nodes]
        return valid_nodes

    def get_nodes_by_regex(self, nregx, nexclude):
        """
        get nodes by regex
        @param nregx string:筛选节点需要的正则表达式
        @param nexclude string:需要排除的节点
        @return list:the node list
        """
        valid_nodes = self.get_valid_nodes()
        match_nodes = []
        ex_nodes = []
        nregx = nregx.replace('*', '.*').replace('?', '.')
        if ';' in nregx:
            regs = ["(^%s$)" % n for n in nregx.split(';')]
            nregx = '|'.join(regs)
        else:
            nregx = "^%s$" % nregx
        regx = re.compile(nregx)
        if nregx:
            for node in valid_nodes:
                if regx.match(node):
                    match_nodes.append(node)

        nexclude = nexclude.replace('*', '.*').replace('?', '.')
        if ';' in nexclude:
            nexcludes = ["(^%s$)" % n for n in nexclude.split(';')]
            nexclude = '|'.join(nexcludes)
        else:
            nexclude = "^%s$" % nexclude
        ex_regx = re.compile(nexclude)
        if nexclude:
            for node in valid_nodes:
                if ex_regx.match(node):
                    ex_nodes.append(node)
        return list(set(match_nodes) - set(ex_nodes))

