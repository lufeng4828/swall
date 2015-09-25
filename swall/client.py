#coding:utf-8
__author__ = 'lufeng4828@163.com'

import re
import os
import time
import logging
from swall.job import Job
from swall.utils import timeout as iTimeout
from swall.utils import app_abs_path,\
    Automagic, \
    Timeout, \
    agent_config
from swall.excpt import SwallAgentError

log = logging.getLogger()

DEFAULT_CONF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conf")


class Client(object):
    def __init__(self, globs=None, exclude_globs=None, wait_all=False, timeout=30, nthread=None,
                 conf_dir=DEFAULT_CONF_DIR):
        self.config = {}
        for f in ('swall', 'zk', 'fs', 'redis'):
            abs_path = app_abs_path(os.path.join(conf_dir, "%s.conf" % f))
            self.config[f] = agent_config(abs_path)

        self.job = Job(self.config, env="aes")
        self.globs = globs if globs else ""
        self.exclude_globs = exclude_globs if exclude_globs else ""
        self.wait_all = wait_all
        self.timeout = timeout
        self.nthread = nthread

    def submit_job(self, func=None, *args, **kwargs):
        wait_timeout = self.timeout if self.wait_all else 0
        rets = self.job.submit_job(
            func,
            self.globs,
            self.exclude_globs,
            args=list(args),
            kwargs=kwargs,
            wait_timeout=wait_timeout,
            nthread=int(self.nthread) if self.nthread is not None else -1
        )
        return rets

    def job_info(self, jid, *args, **kwargs):
        """
        直接通过redis查看任务状态
        """
        job_rets = {}
        match_nodes = self.get_host()
        for node in match_nodes:
            job_ret = self.job.get_job_info(node, jid)
            if job_rets:
                job_rets.update({node: job_ret})

        log.info("end to get job_info for job [%s]" % self.job.get_jid())
        return job_rets

    def get_host(self):
        """
        获取节点列表
        @return dict:
        """
        match_nodes = self.job.keeper.get_nodes_by_regex(self.globs, self.exclude_globs)
        return match_nodes

    def get_return(self, timeout=60):
        """
        获取结果数据
        @param _timeout int:获取数据的超时
        @return dict:
        """

        @iTimeout(timeout)
        def _return(nodes, job_rets):
            job_data = []
            for n in nodes:
                job_data.append((n, self.job.jid))
            while 1:
                try:
                    rets = self.job.get_job(job_data)
                    for node, ret in rets.items():
                        i_ret = ret.get("payload", {}).get("return")
                        if i_ret is None:
                            raise SwallAgentError("wait")
                        else:
                            job_rets.update({node: i_ret})
                except SwallAgentError:
                    time.sleep(0.1)
                else:
                    break
        job_rets = {}
        try:
            match_nodes = self.get_host()
            if not match_nodes:
                return job_rets
            _return(match_nodes, job_rets)
        except Timeout, e:
            log.error(e)
        log.info("end to get result for job [%s]" % self.job.get_jid())
        return job_rets

    def call_func(self, func, args):
        """
        调用客户端模块，然后返回job id,如果执行失败返回0
        """
        return self.submit_job(func, *args)

    def __getattr__(self, name):
        return Automagic(self, [name])

