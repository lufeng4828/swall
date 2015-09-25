#coding:utf-8
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
        self._redis = None
        self.pubsub_keys = set([])
        self.pubsub = self.redis.pubsub()

    def _ping(self):
        try:
            return self._redis.ping()
        except Exception:
            return False

    @property
    def redis(self):
        """
        返回redis链接对象
        :return:
        """
        if self._redis and self._redis.ping():
            return self._redis
        else:
            while (not self._redis) or (self._redis and not self._ping()):
                try:
                    self._redis = Redis(
                        host=self.redis_conf.host,
                        port=int(self.redis_conf.port),
                        db=int(self.redis_conf.db),
                        password=self.redis_conf.password,
                        socket_connect_timeout=5
                    )
                    for key in self.pubsub_keys:
                        self.pubsub(key)
                except Exception, error:
                    log.error(error.message)
            return self._redis

    def psub(self, pattern):
        """
        订阅
        :param pattern:
        :return:
        """
        self.pubsub.psubscribe(pattern)
        return True

    def unpsub(self, pattern):
        self.pubsub.punsubscribe(pattern)
        return True

    def register(self, node_name):
        """

        :param node_name:
        :return:
        """
        if self.tos(node_name):
            if not isinstance(node_name, list):
                node_name = [node_name]
            for node in node_name:
                key = "__keyspace@0__:_swall:_job:%s:*" % node
                self.psub(key)
                self.pubsub_keys.add(key)
            return True
        else:
            return False

    def unregister(self, node_name):
        ping = '_swall:_ping:%s' % node_name
        self.redis.delete(ping)
        key = "__keyspace@0__:_swall:_job:%s" % node_name
        if key in self.pubsub_keys:
            self.pubsub_keys.remove(key)
        self.unpsub(key)
        return True

    def tos(self, node_name):
        if isinstance(node_name, list):
            nodes = node_name
        else:
            nodes = [node_name]
        try:
            str_time = time.strftime('%y-%m-%d %H:%M:%S', time.localtime())
            tos_maps = {}
            for node in nodes:
                tval = "%s@%s@%s" % (node, self.main_conf.node_ip, str_time)
                ping = '_swall:_ping:%s' % node
                tos_maps[ping] = tval
            if not tos_maps:
                return None
            self.redis.mset(tos_maps)
            return True
        except Exception:
            log.error(traceback.format_exc())
        return False

    def get_tos(self, node_name):
        is_list = isinstance(node_name, list)
        if not node_name:
            return []
        if is_list:
            pings = ['_swall:_ping:%s' % node for node in node_name]
        else:
            pings = ['_swall:_ping:%s' % node_name]
        tos = self.redis.mget(pings)
        if tos:
            result = [t.split('@') for t in tos if t]
            if is_list:
                return result
            else:
                return result[0]

    def exists(self, node_name):
        """

        :param node_name:
        :return:
        """
        pings = []
        is_list = isinstance(node_name, list)
        if not is_list:
            node_name = [node_name]
        for node in node_name:
            pings.append('_swall:_ping:%s' % node)
        if pings:
            result = self.redis.mget(pings)
            pairs = zip(node_name, result)
            rets = {}
            for pair in pairs:
                rets[pair[0]] = pair[1]
            if not list:
                return result is not None
            else:
                return rets

    def is_job_exists(self, node_name, jid):
        """
        检查是否存在job
        :param node_name:
        :param jid:
        :return:
        """
        job_key = "_swall:_job:%s:%s" % (node_name, jid)
        return self.redis.exists(job_key)

    def get_job(self, node_name, jid):
        """
        获取job数据
        :param node_name:
        :param jid:
        :return:
        """
        job_key = "_swall:_job:%s:%s" % (node_name, jid)
        job = self.redis.get(job_key)
        if job:
            return msgpack.loads(job)
        else:
            return {}

    def mget_job(self, job_info):
        """
        获取job数据
        :param job_info:
        :param jid:
        :return:
        """
        data = []
        for job in job_info:
            data.append("_swall:_job:%s:%s" % (job[0], job[1]))
        jobs = self.redis.mget(data)
        result = {}
        for k, v in zip(job_info, jobs):
            result[k[0]] = v
        return result

    def get_node_job(self, node_name):
        """
        获取job数据
        :param node_name:
        :return:
        """
        job_key = "_swall:_job:%s:*" % node_name
        keys = self.redis.keys(job_key)
        jobs = []
        for key in keys:
            job = self.redis.get(key)
            if job:
                jobs.append(msgpack.loads(job))
        return jobs

    def del_job(self, node_name, jid):
        """
        删除job
        :param node_name:
        :param jid:
        :return:
        """
        job_key = "_swall:_job:%s:%s" % (node_name, jid)
        self.redis.delete(job_key)
        return True

    def del_node_jobs(self, node_name):
        """
        删除节点对应的job
        :param node_name:
        :return:
        """
        keys = self.redis.keys("_swall:_job:%s:*" % node_name)
        for key in keys:
            self.redis.delete(key)
        return True

    def set_job(self, job_data):
        """

        :param job_data=[(node_name, jid, data)]
        :return:
        """
        send_data = {}
        for job in job_data:
            job_key = "_swall:_job:%s:%s" % (job[0], job[1])
            send_data[job_key] = job[2]
        self.redis.mset(send_data)
        return True

    def get_nodes(self, type_="online"):
        """
        获取节点，默认获取可用节点，type_=online|offline|all
        """
        keys = self.redis.keys("_swall:_ping:*")
        log.info("get nodes [%s]" % len(keys))
        final_nodes = {}
        nodes = {}
        toses = self.get_tos([key.split(':')[-1] for key in keys])
        for node in toses:
            timedelta = datetime.now() - datetime.strptime(node[2], '%y-%m-%d %H:%M:%S')
            nodes.update({node[0]: {"ip": node[0], "update_time": node[2], "delta_seconds": timedelta.seconds}})
        if type_ == "online":
            for key in nodes:
                if nodes[key]["delta_seconds"] <= 60:
                    final_nodes[key] = nodes[key]
        elif type_ == "offline":
            for key in nodes:
                if nodes[key]["delta_seconds"] > 60:
                    final_nodes[key] = nodes[key]
        else:
            final_nodes = nodes
        log.info("get final_nodes [%s]" % len(final_nodes))
        return final_nodes

    def is_valid(self, node_name):
        """
        检查节点是否可用
        """
        data = self.get_tos(node_name)
        if data:
            timedelta = datetime.now() - datetime.strptime(data[1], '%Y-%m-%d %H:%M:%S')
            if timedelta.min <= 1:
                return True
        return False
