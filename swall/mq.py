# coding:utf-8
__author__ = 'lufeng4828@163.com'

import time
import msgpack
import logging
import traceback
from datetime import datetime
from swall.utils import Conf
from redis import ConnectionPool, Redis, ConnectionError


log = logging.getLogger()


class MQ(object):
    """
    消息传输
    """

    def __init__(self, config):
        self.redis_conf = Conf(config["redis"])
        self.main_conf = Conf(config["swall"])
        self.redis = self.redis()
        self.node_ping = "SWALL:PING"
        self.node_job_req = "SWALL:JOBQ"
        self.node_job_res = "SWALL:JOBR"

    def redis(self):
        """
        返回redis链接对象
        :return:
        """
        return Redis(
            host=self.redis_conf.host,
            port=int(self.redis_conf.port),
            db=int(self.redis_conf.db),
            password=self.redis_conf.password,
            socket_connect_timeout=5
        )

    def tos(self, node):
        try:
            str_time = time.strftime('%y-%m-%d %H:%M:%S', time.localtime())
            self.redis.hset(self.node_ping, node, "%s@%s@%s" % (node, self.main_conf.node_ip, str_time))
            return True
        except Exception:
            log.error(traceback.format_exc())
        return False

    def mget_job(self, job_info):
        """
        获取job数据
        :param job_info list:
        :return:
        """
        job_dict = []
        for node, jid in job_info:
            job_dict.append("%s:%s" % (node, jid))
        jobs = self.redis.hmget(self.node_job_res, job_dict)
        result = {}
        if jobs:
            for ret in zip([node for node, _ in job_info], jobs):
                result[ret[0]] = msgpack.loads(ret[1]) if ret[1] else ret[1]
        return result

    def get_job(self, node):
        item = self.redis.lpop("%s:%s" % (self.node_job_req, node))
        if item:
            item = msgpack.loads(item)
        return item

    def set_res(self, node, jid, result):
        """
        保存执行后的任务信息
        :param node:
        :param jid:
        :param result:
        :return:
        """
        key = "%s:%s" % (node, jid)
        self.redis.hset(self.node_job_res, key, msgpack.dumps(result))
        return True

    def del_res(self, node, jid):
        """
        删除任务执行结果
        :param node:
        :param jid:
        :return:
        """
        key = "%s:%s" % (node, jid)
        self.redis.hdel(self.node_job_res, key)
        return True

    def get_res(self, node, jid):
        """
        获取任务执行结果
        :param node:
        :param jid:
        :return:
        """
        key = "%s:%s" % (node, jid)
        item = self.redis.hget(self.node_job_res, key)
        if item:
            item = msgpack.loads(item)
        return item

    def mset_job(self, job_data):
        """

        :param job_data=[(node_name, data)]
        :return:
        """
        pl = self.redis.pipeline()
        for job in job_data:
            pl.rpush('%s:%s' % (self.node_job_req, job[0]), msgpack.dumps(job[1]))
        pl.execute()
        return True

    def get_nodes(self, type_="online"):
        """
        获取节点，默认获取可用节点，type_=online|offline|all
        """
        nodes = self.redis.hgetall(self.node_ping)
        log.info("get nodes [%s]" % len(nodes))
        final_nodes = {}
        nodes_t = {}
        for node in nodes:
            node_data = nodes[node].split('@')
            timedelta = datetime.now() - datetime.strptime(node_data[2], '%y-%m-%d %H:%M:%S')
            nodes_t.update({node: {"ip": node_data[0], "update_time": node_data[2], "delta_seconds": timedelta.seconds}})
        if type_ == "online":
            for key in nodes_t:
                if nodes_t[key]["delta_seconds"] <= 60:
                    final_nodes[key] = nodes_t[key]
        elif type_ == "offline":
            for key in nodes_t:
                if nodes_t[key]["delta_seconds"] > 60:
                    final_nodes[key] = nodes_t[key]
        else:
            final_nodes = [key for key in nodes_t]
        log.info("get final_nodes [%s]" % len(final_nodes))
        return final_nodes

    def is_valid(self, node_name):
        """
        检查节点是否可用
        """
        data = self.redis.hget(self.node_ping, node_name)
        if data:
            data = data.split('@')
            timedelta = datetime.now() - datetime.strptime(data[1], '%Y-%m-%d %H:%M:%S')
            if timedelta.min <= 1:
                return True
        return False
