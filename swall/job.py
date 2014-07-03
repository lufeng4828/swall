#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import time
import msgpack
import datetime
import logging
from swall.utils import cp, \
    check_cache, \
    make_dirs, \
    Conf, \
    load_fclient, \
    app_abs_path, \
    checksum, \
    Timeout

from copy import deepcopy
from swall.zkcon import ZKDb
from swall.crypt import Crypt
from swall.keeper import Keeper
from swall.zkclient import ZKClientError
from swall.utils import timeout as iTimeout
from swall.excpt import SwallAgentError

log = logging.getLogger()


class Job(ZKDb):
    """
    任务管理相关
    """
    def __init__(self, config, jid="", env="clear", timeout=60, retry_times=3):
        #初始化下ZKDb的init方法
        super(Job, self).__init__()

        self.fs_conf = Conf(config["fs"])
        self.main_conf = Conf(config["swall"])
        self.zookeeper_conf = Conf(config["zk"])
        self.keeper = Keeper(config)
        self.jid = jid
        self.env = env
        self.timeout = timeout
        self.retry_times = retry_times

    def _gen_jid(self):
        """
        如果没有传jid进来，需要生成一个jid
        """
        if not self.jid:
            self.jid = "{0:%Y%m%d%H%M%S%f}".format(datetime.datetime.now())

    def get_jid(self):
        """
        获取jid
        @return string:jid字符串
        """
        self._gen_jid()
        return self.jid

    def _send_job(self, data, role, node_name):
        """
        发送job到对应的zk目录
        @param data dict:
        @param role string:
        @param node_name string:
        @return int:1 for success else 0
        """
        ret = 0
        try:
            job_path = os.path.join(self.zookeeper_conf.nodes, role, node_name, "jobs", data["payload"]["jid"])
            if data.get("env") == "aes":
                key_str = self.main_conf.token
                crypt = Crypt(key_str)
                data["payload"] = crypt.dumps(data.get("payload"))
            data = msgpack.dumps(data)
            self.zkconn.create(job_path, data)
            ret = 1
        except ZKClientError, e:
            log.error("send_job error:%s" % e.message)
        return ret

    def submit_job(self, cmd, roles, nregex, nexclude=None, args=[], kwargs={}, wait_timeout=0, nthread=-1):
        """
        提交任务
        @param cmd string:需要执行的命令
        @param roles string:需要执行的节点类型，如game、admin、server等，多个用|分隔
        @param nregex string:节点匹配正则表达式
        @param nexclude string:排除节点正则，会从nregex结果排除掉
        @param args list:传给cmd命令的位置参数
        @param kwargs dict:传给cmd的位置参数
        @param wait_timeout int:等待结果的时间
        @param nthread int:单个机器上面执行任务的并发数量
        @return dict:{
                "retcode": 返回值
                "extra_data": 其他信息,
                "msg": 提示信息,
            }
        """
        self._gen_jid()
        match_nodes = {}
        for role in re.split(r"[|,]", roles):
            match = self.keeper.get_nodes_by_regex(role, nregex, nexclude)
            if match:
                match_nodes[role] = match
        if not match_nodes:
            log.warn("0 node match for %s [%s]" % (self.jid, cmd))
            return {
                "retcode": 1,
                "extra_data": {},
                "msg": "send_job complete,0 node match"
            }
        if cmd == "sys.copy":
            if "help" not in args:
                FsClient = load_fclient(app_abs_path(self.main_conf.fs_plugin), ftype=self.fs_conf.fs_type)
                fscli = FsClient(self.fs_conf)
                if "local_path" in kwargs and "remote_path" in kwargs:
                    local_path = kwargs["local_path"]
                else:
                    local_path = args[0]
                fid = fscli.upload(local_path)
                if "local_path" in kwargs and "remote_path" in kwargs:
                    kwargs["path_pair"] = "%s,%s" % (fid, os.path.basename(local_path))
                else:
                    args[0] = "%s,%s" % (fid, os.path.basename(local_path))
        if cmd == "sys.rsync_module":
            if not args or args[0] != "help":
                FsClient = load_fclient(app_abs_path(self.main_conf.fs_plugin), ftype=self.fs_conf.fs_type)
                fscli = FsClient(self.fs_conf)
                if "mods" in kwargs:
                    mods = kwargs["mods"].split(',')
                elif args:
                    mods = args
                else:
                    pass
                modules = {}
                if "mods" in kwargs or args:
                    for role in match_nodes:
                        t_path = [
                            os.path.join(role, mod) for mod in mods
                            if os.path.exists(os.path.join(app_abs_path(self.main_conf.module), role, mod))
                        ]
                        t_path.extend([
                            os.path.join("common", mod) for mod in mods
                            if os.path.exists(os.path.join(app_abs_path(self.main_conf.module), "common", mod))
                        ])
                        modules[role] = t_path
                else:
                    for role in match_nodes:
                        role_mod_path = os.path.join(app_abs_path(self.main_conf.module), role)
                        t_path = [
                            os.path.join(role, mod) for mod in os.listdir(role_mod_path)
                            if mod.endswith(".py")
                        ]
                        common_mod_path = os.path.join(app_abs_path(self.main_conf.module), "common")
                        t_path.extend(
                            [
                                os.path.join("common", mod) for mod in os.listdir(common_mod_path)
                                if mod.endswith(".py")
                            ]
                        )
                        modules[role] = t_path
                copy_pair = []
                for role in modules:
                    for mod in modules[role]:
                        mod_path = os.path.join(app_abs_path(self.main_conf.module), mod)
                        fid = fscli.upload(mod_path)
                        copy_pair.append((role, fid, mod))
                kwargs["copy_pair"] = copy_pair
        data = {
            "env": self.env,
            "payload":
            {
                "jid": self.jid,
                "cmd": cmd,
                "args": args,
                "kwargs": kwargs,
                "status": "READY",
                "timeout": self.timeout,
                "retry_times": self.retry_times
            }
        }
        if nthread != -1:
            data["payload"]["nthread"] = nthread
        send_ret = {}
        for role in match_nodes:
            for node_name in match_nodes[role]:
                job_data = deepcopy(data)
                send_ret.update({"%s.%s" % (role, node_name): self._send_job(job_data, role, node_name)})

        if wait_timeout:
            rets = {}

            @iTimeout(wait_timeout)
            def _return(nodes, job_rets):
                while 1:
                    try:
                        for r in nodes:
                            for n in nodes[r]:
                                job_ret = self.get_job(r, n, self.jid)
                                i_ret = job_ret["payload"].get("return", "")
                                if not i_ret:
                                    raise SwallAgentError("wait")
                                if job_rets.get(r):
                                    job_rets[r].update({n: i_ret})
                                else:
                                    job_rets[r] = {n: i_ret}
                    except SwallAgentError:
                        time.sleep(0.1)
                    else:
                        break
            try:
                _return(match_nodes, rets)
            except Timeout, e:
                log.error(e)

            return {
                "retcode": 1,
                "extra_data": rets,
                "msg": "get result complete!"
            }
        else:
            if all([ret for ret in send_ret.itervalues()]):
                return {
                    "retcode": 1,
                    "extra_data": {"jid": self.jid},
                    "msg": "send_job complete,all success"
                }
            else:
                return {
                    "retcode": 0,
                    "extra_data": {},
                    "msg": "send_job complete,fail",
                }

    def get_job(self, role, node_name, jid):
        """
        获取任务
        @param role string:角色
        @param node_name string:节点名称
        @param jid string:任务id
        @return dict:a job info
        """
        ret = {}
        try:
            node_path = os.path.join(self.zookeeper_conf.nodes, role, node_name, "jobs", jid)
            data = self.zkconn.get(node_path)[0]
            data = msgpack.loads(data)
            env = data.get("env")
            if env == "aes":
                key_str = self.main_conf.token
                crypt = Crypt(key_str)
                data["payload"] = crypt.loads(data.get("payload"))
            payload = data["payload"]
            if payload["cmd"] == "sys.get" and payload["status"] == "FINISH" and payload["return"] != "":
                if payload["args"][0] != "help":
                    fid = payload["return"]
                    if "local_path" in payload["kwargs"] and "remote_path" in payload["kwargs"]:
                        local_path = payload["kwargs"]["local_path"]
                        remote_path = payload["kwargs"]["remote_path"]
                    else:
                        local_path = payload["args"][1]
                        remote_path = payload["args"][0]
                    stat = payload["kwargs"].get("stat")
                    if local_path.endswith('/') or os.path.isdir(local_path):
                        local_path = os.path.join(local_path, os.path.basename(remote_path))
                    if checksum(local_path) != fid:
                        if not check_cache(app_abs_path(self.main_conf.cache), fid):
                            FsClient = load_fclient(app_abs_path(self.main_conf.fs_plugin), ftype=self.fs_conf.fs_type)
                            fscli = FsClient(self.fs_conf)
                            fscli.download(fid, os.path.join(app_abs_path(self.main_conf.cache), fid))

                        if check_cache(app_abs_path(self.main_conf.cache), fid):
                            if not make_dirs(os.path.dirname(local_path)):
                                log.error("创建目标目录:%s失败" % local_path)
                            if cp(os.path.join(app_abs_path(self.main_conf.cache), fid), local_path, stat):
                                payload["return"] = local_path
                            else:
                                payload["return"] = ""
                    else:
                        payload["return"] = local_path
            ret = data

        except (ZKClientError, KeyboardInterrupt), e:
            log.error(e.message)
        return ret

    def get_job_info(self, role, node_name, jid):
        """
        返回任务状态
        @param role string:角色
        @param node_name string:节点名称
        @param jid string:任务id
        @return dict:
        """
        node_base_dir = self.zookeeper_conf.nodes
        jid_path = os.path.join(node_base_dir, role, node_name, "jobs", jid)
        payload = {}
        if self.zkconn.exists(jid_path):
            job = self.zkconn.get(jid_path)[0]
            data = msgpack.loads(job)
            if data["env"] == "aes":
                key_str = self.main_conf.token
                crypt = Crypt(key_str)
                payload = crypt.loads(data.get("payload"))
        return payload

    def del_job(self, role, node_name, jid):
        """
        删除任务
        @param role string:角色
        @param node_name string:节点名称
        @param jid string:任务id
        @return int:1 for success else 0
        """
        ret = 0
        try:
            node_path = os.path.join(self.zookeeper_conf.nodes, role, node_name, "jobs", jid)
            if self.zkconn.exists(node_path):
                self.zkconn.delete(node_path)
                ret = 1
            else:
                ret = 1
        except ZKClientError, e:
            log.error(e.message)
        return ret

    def clear_role_jobs(self, role):
        """
        清理对应角色下面的所有节点的任务
        @param role string:角色名称
        @return int:1 for success else 0
        """
        dret = 0
        try:
            node_path = os.path.join(self.zookeeper_conf.nodes, role)
            nodes = self.zkconn.get_children(node_path)
            iret = []
            for node in nodes:
                for job in self.zkconn.get_children(os.path.join(node_path, node, "jobs")):
                    iret.append(self.del_job(role, node, job))
            if all(iret):
                dret = 1
        except ZKClientError, e:
            log.error(e.message)
        return dret

    def clear_all_jobs(self):
        """
        清空所有的任务
        @return int:1 for success else 0
        """
        roles = self.keeper.role_list()
        dret = []
        for role in roles:
            dret.append(self.clear_role_jobs(role))
        if all(dret):
            return 1
        else:
            return 0

    def jobs_list(self, role):
        """
        获取一个角色下面的所有任务
        @param role string:角色名称
        @return dict:{"ljxz_tx_5001":[job1,job2,job3,jobN]}
        """
        ret = {}
        try:
            node_path = os.path.join(self.zookeeper_conf.nodes, role)
            nodes = self.zkconn.get_children(node_path)
            for node in nodes:
                for job in self.zkconn.get_children(os.path.join(node_path, node, "jobs")):
                    if ret.get(node):
                        ret[node].append(job)
                    else:
                        ret[node] = [job]
        except ZKClientError, e:
            log.error(e.message)
        return ret









