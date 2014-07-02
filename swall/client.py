#coding:utf-8
__author__ = 'lufeng4828@163.com'

import re
import time
import logging
from swall.job import Job
from swall.utils import timeout as iTimeout
from swall.utils import app_abs_path, Automagic, Timeout

log = logging.getLogger()


class Client(object):
    def __init__(self, globs=None, exclude_globs=None, role=None, wait_all=False, timeout=30, nthread=None):
        self.job = Job(app_abs_path("conf/swall.conf"), env="aes")
        self.globs = globs if globs else ""
        self.exclude_globs = exclude_globs if exclude_globs else ""
        self.role = role
        self.wait_all = wait_all
        self.timeout = timeout
        self.nthread = nthread

    def submit_job(self, func=None, *args, **kwargs):
        wait_timeout = self.timeout if self.wait_all else 0
        rets = self.job.submit_job(
            func,
            self.role,
            self.globs,
            self.exclude_globs,
            args=list(args),
            kwargs=kwargs,
            wait_timeout=wait_timeout,
            nthread=int(self.nthread) if self.nthread is not None else -1
        )
        return rets

    def job_info(self, jid):
        """
        直接通过zookeeper查看任务状态
        """
        job_rets = {}
        match_nodes = self.get_host()
        for role in match_nodes:
            for node in match_nodes[role]:
                job_ret = self.job.get_job_info(role, node, jid)
                job_rets.update({(role, node): job_ret})
        log.info("end to get job_info for job [%s]" % self.job.get_jid())
        return [(k[0], k[1], job_rets[k]) for k in job_rets]

    def get_host(self):
        """
        获取节点列表
        @return dict:
        """
        match_nodes = {}
        for r in re.split(r"[|,]", self.role):
            match = self.job.keeper.get_nodes_by_regex(r, self.globs, self.exclude_globs)
            if match:
                match_nodes[r] = match
        return match_nodes

    def get_return(self, timeout=30):
        """
        获取结果数据
        @param _timeout int:获取数据的超时
        @return list:[(role1,node1,val1), (role2,node2,val2)]
        """

        @iTimeout(timeout)
        def _return():
            job_rets = {}
            match_nodes = self.get_host()
            while 1:
                wait = 0
                for role in match_nodes:
                    for node in match_nodes[role]:
                        job_ret = self.job.get_job(role, node, self.job.jid)
                        ret = job_ret.get("payload", {}).get("return", "")
                        if ret == "":
                            wait = 1
                        else:
                            job_rets.update({(role, node): ret})
                if wait:
                    time.sleep(1)
                else:
                    break
            return job_rets

        rets = {}
        try:
            rets = _return()
        except Timeout, e:
            log.error(e)
        log.info("end to get result for job [%s]" % self.job.get_jid())
        return [(k[0], k[1], rets[k]) for k in rets]

    def call_func(self, func, args):
        """
        调用客户端模块，然后返回job id,如果执行失败返回0
        """
        return self.submit_job(func, *args)

    def __getattr__(self, name):
        return Automagic(self, [name])

