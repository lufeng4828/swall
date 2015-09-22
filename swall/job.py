#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import time
import traceback
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
from swall.mq import MQ
from swall.crypt import Crypt
from swall.keeper import Keeper
from swall.utils import timeout as iTimeout
from swall.excpt import SwallAgentError

log = logging.getLogger()


class Job(object):
    """
    任务管理相关
    """
    def __init__(self, config, jid="", env="clear", timeout=60, retry_times=3):
        #初始化下ZKDb的init方法
        super(Job, self).__init__()

        self.fs_conf = Conf(config["fs"])
        self.main_conf = Conf(config["swall"])
        self.keeper = Keeper(config)
        self.mq = MQ(config)
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

    def _send_job(self, data, node_name):
        """
        发送job到对应的zk目录
        @param data dict:
        @param node_name string:
        @return int:1 for success else 0
        """
        ret = 0
        try:
            jid = data["payload"]["jid"]
            if data.get("env") == "aes":
                key_str = self.main_conf.token
                crypt = Crypt(key_str)
                data["payload"] = crypt.dumps(data.get("payload"))
            data = msgpack.dumps(data)
            self.keeper.mq.set_job(node_name, jid, data)
            ret = 1
        except Exception, e:
            log.error("send_job error:%s" % traceback.format_exc())
        return ret

    def submit_job(self, cmd, nregex, nexclude=None, args=[], kwargs={}, wait_timeout=0, nthread=-1):
        """
        提交任务
        @param cmd string:需要执行的命令
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
        match_nodes = []
        match = self.keeper.get_nodes_by_regex(nregex, nexclude)
        if match:
            match_nodes = match
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
                modules = [mod for mod in os.listdir(app_abs_path(self.main_conf.module)) if mod.endswith(".py")]
                copy_pair = []
                for mod in modules:
                    mod_path = os.path.join(app_abs_path(self.main_conf.module), mod)
                    fid = fscli.upload(mod_path)
                    copy_pair.append((fid, mod))
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
        for node_name in match_nodes:
            job_data = deepcopy(data)
            send_ret.update({node_name: self._send_job(job_data, node_name)})

        if wait_timeout:
            rets = {}

            @iTimeout(wait_timeout)
            def _return(nodes, job_rets):
                while 1:
                    try:
                        for n in nodes:
                            job_ret = self.get_job(n, self.jid)
                            i_ret = job_ret["payload"].get("return", "")
                            if not i_ret:
                                raise SwallAgentError("wait")
                            if job_rets:
                                job_rets.update({n: i_ret})
                            else:
                                job_rets = {n: i_ret}
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

    def get_job(self, node_name, jid):
        """
        获取任务
        @param node_name string:节点名称
        @param jid string:任务id
        @return dict:a job info
        """
        ret = {}
        try:
            data = self.mq.get_job(node_name, jid)
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

        except Exception, e:
            log.error(e.message)
        return ret

    def get_job_info(self, node_name, jid):
        """
        返回任务状态
        @param node_name string:节点名称
        @param jid string:任务id
        @return dict:
        """
        self.mq.exists(node_name)
        payload = {}
        if self.mq.is_job_exists(node_name, jid):
            data = self.mq.get_job(node_name, jid)
            if data["env"] == "aes":
                key_str = self.main_conf.token
                crypt = Crypt(key_str)
                payload = crypt.loads(data.get("payload"))
        return payload

    def del_job(self, node_name, jid):
        """
        删除任务
        @param node_name string:节点名称
        @param jid string:任务id
        @return int:1 for success else 0
        """
        ret = 0
        try:
            return self.mq.del_job(node_name, jid)
        except Exception, e:
            log.error(e.message)
        return ret

    def clear_all_jobs(self):
        """
        清空所有的任务
        @return int:1 for success else 0
        """
        nodes = self.keeper.get_valid_nodes()
        for node in nodes:
            self.mq.del_node_jobs(node)
        return True

    def jobs_list(self):
        """
        获取一个角色下面的所有任务
        @return dict:{"ljxz_tx_5001":[job1,job2,job3,jobN]}
        """
        ret = {}
        try:

            nodes = self.keeper.get_valid_nodes()
            for node in nodes:
                for job in self.mq.get_node_job(node):
                    ret[node] = job
        except Exception, e:
            log.error(e.message)
        return ret









