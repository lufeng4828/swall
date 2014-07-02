#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import logging
from swall.utils import gen_node

log = logging.getLogger()


@gen_node
def game(*args):
    """
    def game(*args) -> 获取游戏节点列表，返回格式是
    @return dict:
    {
        'swall_sa_9002': {'project': 'swall', 'agent': 'sa'},
        'swall_sa_9001': {'project': 'swall', , 'agent': 'sa'},
    }
    """
    all_games = {}

    def rep(x):
        project = x.split('_')[0]
        agent = x.split('_')[1]
        sid = x.split('_')[2]
        if len(args) == 1:
            sub_role = args[0]
            return {"%s_%s_%s_%s" % (sub_role, project, agent, sid): {"agent": agent, "project": project, "role": "game"}}
        else:
            return {"%s_%s_%s" % (project, agent, sid): {"agent": agent, "project": project, "role": "game"}}
    for n in [g for g in os.listdir("/data/")
              if re.match(r'[a-z0-9]+_[0-9a-z]+_[0-9]+$', g)]:
        all_games.update(rep(n))
    return all_games
