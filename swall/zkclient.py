#coding:utf8

import os
import logging
import traceback
import base64
import hashlib
import threading
import zookeeper
from collections import namedtuple

log = logging.getLogger()

#连接状态映射，将数字状态转换为文字状态
STATE_NAME_MAPPING = {
    zookeeper.ASSOCIATING_STATE: "associating",
    zookeeper.AUTH_FAILED_STATE: "auth-failed",
    zookeeper.CONNECTED_STATE: "connected",
    zookeeper.CONNECTING_STATE: "connecting",
    zookeeper.EXPIRED_SESSION_STATE: "expired"
}

# 事件类型映射，将数字事件类型描述转换为文字描述
TYPE_NAME_MAPPING = {
    zookeeper.NOTWATCHING_EVENT: "not-watching",
    zookeeper.SESSION_EVENT: "session",
    zookeeper.CREATED_EVENT: "created",
    zookeeper.DELETED_EVENT: "deleted",
    zookeeper.CHANGED_EVENT: "changed",
    zookeeper.CHILD_EVENT: "child"
}

#默认的连接超时
DEFAULT_TIMEOUT = 120000


class ZKClientError(Exception):
    """
    构造异常捕捉类
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class ClientEvent(namedtuple("ClientEvent", 'type, connection_state, path')):
    """
    事件相关的类，记录事件类型、事件状态、监听的路径、连接服务器状态
    """

    @property
    def type_name(self):
        return TYPE_NAME_MAPPING[self.type]

    @property
    def state_name(self):
        return STATE_NAME_MAPPING[self.connection_state]

    def __repr__(self):
        return "<ClientEvent %s at %r state: %s>" % (
            self.type_name, self.path, self.state_name)


def watchmethod(func):
    """
    watcher函数包装，包装以后原有的只接受一个ClientEvent类型的参数的函数变为接受handle, atype, state, path这四个参数的函数
    """

    def decorated(handle, atype, state, path):
        event = ClientEvent(atype, state, path)
        return func(event)

    return decorated


def digest_acl(key, perms):
    """
    如果是使用create方法创建一个节点，必须要使用如下方法加密的密码认证
    """
    sha1 = "%s:%s" % ("mcyw", base64.b64encode(hashlib.new("sha1", key).digest()))
    #digest类型的认证权限
    return {"perms": perms, "scheme": "digest", "id": sha1}


class ZKClient(object):

    ZKEPOCH = 0

    def __init__(self, servers, acl, timeout=DEFAULT_TIMEOUT):
        """
        zookeeper 操作类的封装
        """
        self.epoch = 0
        self.acl = acl
        self.timeout = timeout
        self.connected = False
        #线程同步对象
        self.conn_cv = threading.Condition()
        self.handle = -1
        #线程尝试获取锁，如果拿到就执行下面的代码，否则等待其他线程通知
        self.conn_cv.acquire()
        self.handle = zookeeper.init(servers, self.conn_watcher, timeout)
        #wait方法会释放锁，然后阻塞，等待其他线程执行notify或者notifyAll方法，如果指定的时间没有得到通知，线程重新获取锁，如果获取到锁，继续执行下面的代码
        self.conn_cv.wait(timeout / 10000)
        #释放锁
        self.conn_cv.release()
        #检查连接状态
        if not self.connected:
            raise ZKClientError("Unable to connect to %s" % (servers))

        if not self.add_auth(scheme=acl["scheme"], id=acl["id"]):
            raise ZKClientError("add_auth to zookeeper fail")

    def conn_watcher(self, h, type, state, path):
        """
        连接zookeeper的回调函数
        """
        self.handle = h
        self.conn_cv.acquire()
        self.connected = True
        ZKClient.ZKEPOCH += 1
        self.epoch = ZKClient.ZKEPOCH
        self.conn_cv.notifyAll()
        self.conn_cv.release()

    def state(self):
        """
        返回zk的连接状况
        """
        try:
            stat = zookeeper.state(self.handle)
            return STATE_NAME_MAPPING.get(stat)
        except:
            log.error(traceback.format_exc())
            return "unknwon"

    def add_auth(self, scheme, id, callback=None):
        """
        添加认证
        """
        zookeeper.add_auth(self.handle, scheme, id, callback)
        try:
            self.get("/")
            return 1
        except zookeeper.NoAuthException:
            return 0

    def close(self):
        """
        关闭zookeeper连接
        """
        return zookeeper.close(self.handle)

    def create(self, path, data="", flags=0, makepath=False, force=False):
        """
        创建节点
        """
        acl2 = {"perms": 0x1f, "scheme": "world", "id": "anyone"}
        if self.acl["scheme"] == "digest":
            user, _ = self.acl["id"].split(':')
            id2 = "%s:%s" % (user, base64.b64encode(hashlib.new("sha1", self.acl["id"]).digest()))
            acl2 = {"perms": self.acl["perms"], "scheme": "digest", "id": id2}
        log.info("zk create [%s]" % path)
        if makepath:
            if not self.exists(os.path.dirname(path)):
                self.create(path=os.path.dirname(path), data="", flags=flags, makepath=True)
        log.info(path)
        if force and self.exists(path):
            self.delete(path)

        zookeeper.create(self.handle, path, data, [acl2], flags)
        if self.exists(path):
            return 1
        else:
            return 0

    def delete(self, path, version=-1, recursive=False):
        """
        删除节点，可以制定特定版本的节点，默认是-1，即删除所有版本节点
        """
        if recursive:
            for child in self.get_children(path):
                self.delete(path=os.path.join(path, child), recursive=True)
        zookeeper.delete(self.handle, path, version)
        if not self.exists(path):
            return 1
        else:
            return 0

    def get(self, path, watcher=None):
        """
        获取节点信息,如果有watcher函数，则如果当前path节点变化、节点被删除，就会回调watcher函数
        """
        return zookeeper.get(self.handle, path, watcher)

    def exists(self, path, watcher=None):
        """
        检查节点是否存在，如果有watcher，那么节点创建、节点删除、节点改变都会回调该函数
        """
        return zookeeper.exists(self.handle, path, watcher)

    def set(self, path, data="", version=-1):
        """
        设置节点的value，返回更新结果
        """
        return zookeeper.set(self.handle, path, data, version)

    def set2(self, path, data="", version=-1):
        """
        设置节点value，返回节点更新以后的结构
        """
        return zookeeper.set2(self.handle, path, data, version)

    def get_children(self, path, watcher=None):
        """
        获取对应节点下的子节点列表，如果watcher不为空，子节点改变，就会出发执行watcher方法
        """
        return zookeeper.get_children(self.handle, path, watcher)

    def async(self, path="/"):
        """
        刷新leader，保证集群最新数据更新出去，这样获取的数据才是最新的
        """
        return zookeeper.async(self.handle, path)






