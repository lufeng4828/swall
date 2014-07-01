#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import logging
from swall.zkcon import ZKDb
from swall.utils import Conf
from swall.zkclient import ZKClientError

log = logging.getLogger()


class Keeper(ZKDb):
    """
    实现zookeeper一些基础功能
    """

    def __init__(self, config):
        #初始化下ZKDb的init方法
        super(Keeper, self).__init__()
        self.main_conf = Conf(config["swall"])
        self.zookeeper_conf = Conf(config["zk"])

    def init_db(self, force=False):
        """
        初始化zookeeper
        @param clean bool:True if you want to rmr /swall before init else False
        @return bool: False or True if success
        """
        base_node = self.zookeeper_conf.nodes
        if self.zkconn.exists(base_node):
            if force:
                self.zkconn.delete(self.zookeeper_conf.root, recursive=True)
            else:
                return 0
        return self.zkconn.create(base_node, makepath=True)

    def is_valid(self, node_path):
        """
        检查某个节点是否正常，其实只要检查是否存在tos目录就可以了
        @param node_path string:节点的目录路径
        @param int:1 of valid else 0
        """
        if self.zkconn.exists(node_path):
            return 1
        else:
            return 0

    def get_valid_nodes(self, role=None):
        """
        获取所有可用的节点
        @param role string:角色
        @return dict:{"role1":["node1","node2","node3","nodeN"],"role2":["node1","node2","node3","nodeN"]}
        """
        valid_nodes = {}
        node_parent = self.zookeeper_conf.nodes
        if not role:
            for sub_node in self.zkconn.get_children(node_parent):
                sub_node_path = os.path.join(node_parent, sub_node)
                for node in self.zkconn.get_children(sub_node_path):
                    if self.is_valid(os.path.join(sub_node_path, node, "tos")):
                        if valid_nodes.get(sub_node):
                            valid_nodes[sub_node].append(node)
                        else:
                            valid_nodes[sub_node] = [node]
                    else:
                        if not valid_nodes.get(sub_node):
                            valid_nodes[sub_node] = []
        else:
            sub_node_path = os.path.join(node_parent, role)
            for node in self.zkconn.get_children(sub_node_path):
                if self.is_valid(os.path.join(sub_node_path, node, "tos")):
                    if valid_nodes.get(role):
                        valid_nodes[role].append(node)
                    else:
                        valid_nodes[role] = [node]
        return valid_nodes

    def get_nodes_by_regex(self, role, nregx, nexclude):
        """
        get nodes by regex and role name
        @param role string:role name
        @param nregx string:筛选节点需要的正则表达式
        @param nexclude string:需要排除的节点
        @return list:the node list
        """
        valid_nodes = self.get_valid_nodes(role).get(role, [])
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

    def role_list(self):
        """
        获取所有的role类型
        @return list:["game","server","router"]
        """
        node_path = self.zookeeper_conf.nodes
        roles = []
        try:

            roles = self.zkconn.get_children(node_path)
        except ZKClientError, e:
            log.error(e.message)
        return roles
