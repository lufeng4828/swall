#coding:utf-8
__author__ = 'lufeng4828@163.com'

import time
import logging
import traceback
from swall.zkclient import ZKClient

log = logging.getLogger()


class ZKDb(object):
    def __init__(self):
        self._zkconn = None

    @property
    def zkconn(self):
        """
        获取zookeeper连接
        """
        try:
            if self._zkconn and self._zkconn.state() == "connected":
                return self._zkconn
        except:
            log.error(traceback.format_exc())
        acl = {
            "perms": 0x1f,
            "scheme": self.zookeeper_conf.zk_scheme,
            "id": self.zookeeper_conf.zk_auth
        }

        while 1:
            try:
                zk = ZKClient(
                    self.zookeeper_conf.zk_servers,
                    acl,
                    getattr(self.zookeeper_conf, "zk_timeout", 30000)
                )
                if zk.state() == "connected":
                    self._zkconn = zk
                    return zk
                else:
                    log.warn("zkconn error state is:%s" % zk.state())
                    time.sleep(10)
            except:
                log.error(traceback.format_exc())
                time.sleep(10)
