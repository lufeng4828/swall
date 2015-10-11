#coding:utf-8
__author__ = 'lufeng4828@163.com'

import logging
from swall.utils import node
from swall.utils import run

log = logging.getLogger()


@node
def call(cmd, ret_type="full", cwd=None, runas=None, shell="/bin/bash", env={}, *args, **kwarg):
    """
    def call(cmd, ret_type="full", cwd=None, runas=None, shell="/bin/bash", env={}, *args, **kwarg) -> Execute the passed command and return the output as a string
    @param cmd string:执行的命令
    @param ret_type string:返回格式，默认全部返回
    @param cwd string:工作目录，执行命令时候需要进入的目录
    @param runas string:以runas的身份执行命令
    @param shell string:解析脚本的shell，默认是/bin/bash
    @paran env dict:执行命令的环境
    @return dict:
    ret{
        'stdout': 标准输出
        'stderr': 错误输出
        'pid': 执行脚本的pid
        'retcode': 脚本返回状态
        }
    CLI Example::
        swall ctl '*' cmd.run "ls -l | awk '/foo/{print $2}'"
    """

    ret = run(cmd, runas=runas, shell=shell, cwd=cwd, env=env)
    #根据ret_type返回不同格式的结果
    if ret_type == "full":
        return ret
    else:
        return ret.get(ret_type)

