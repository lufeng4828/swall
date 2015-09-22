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
        self._redis = self._conn()
        self.pubsub = self.redis.pubsub()

    @property
    def redis(self):
        """
        返回redis链接对象
        :return:
        """
        return self._conn()

    def _conn(self):
        """
        返回redis链接对象,为了保证链接先暂时在获取redis时候先检查链接
        :return:
        """
        status = False
        try:
            if self._redis:
                status = self._redis.ping()
        except ConnectionError, error:
            log.error("redis connect error:%s, try...." % error)
        except Exception, error:
            log.error(error)
        if not status:
            pool = ConnectionPool(host=self.redis_conf.host, port=int(self.redis_conf.port), db=int(self.redis_conf.db), password=self.redis_conf.password)
            return Redis(connection_pool=pool)
        else:
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
            self.psub("__keyspace@0__:_swall:_job:" % node_name)
            return True
        else:
            return False

    def unregister(self, node_name):
        ping = '_swall:_ping:%s' % node_name
        self.redis.delete(ping)
        self.unpsub("__keyspace@0__:_swall:_job:%s" % node_name)
        return True

    def tos(self, node_name):
        if isinstance(node_name, list):
            nodes = node_name
        else:
            nodes = [node_name]
        try:
            tval = "%s@%s" % (self.main_conf.node_ip, time.strftime('%y-%m-%d %H:%M:%S', time.localtime()))
            for node in nodes:
                ping = '_swall:_ping:%s' % node
                self.redis.set(ping, tval)
                self.redis.expire(ping, int(self.redis_conf.expire))
                return True
        except Exception:
            log.error(traceback.format_exc())
        return False

    def get_tos(self, node_name):
        ping = '_swall:_ping:%s' % node_name
        tos = self.redis.get(ping)
        if tos:
            return tos.split('@')

    def exists(self, node_name):
        """

        :param node_name:
        :return:
        """
        ping = '_swall:_ping:%s' % node_name
        return self.redis.exists(ping)

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

    def set_job(self, node_name, jid, data):
        """

        :param node_name:
        :param jid:
        :param data:
        :return:
        """
        job_key = "_swall:_job:%s:%s" % (node_name, jid)
        self.redis.set(job_key, data)
        return True

    def get_nodes(self, type_="online"):
        """
        获取节点，默认获取可用节点，type_=online|offline|all
        """
        keys = self.redis.keys("_swall:_ping:*")
        final_nodes = {}
        nodes = {}
        for key in keys:
            data = self.get_tos(key)
            if data:
                timedelta = datetime.now() - datetime.strptime(data[1], '%Y-%m-%d %H:%M:%S')
                nodes.update({key: {"ip": data[0], "update_time": data[1], "delta_min": timedelta.min}})
        if type_ == "online":
            for key in nodes:
                if nodes[key]["delta_min"] <= 1:
                    final_nodes[key] = nodes[key]
        elif type_ == "offline":
            for key in nodes:
                if nodes[key]["delta_min"] > 1:
                    final_nodes[key] = nodes[key]
        else:
            final_nodes = nodes

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
