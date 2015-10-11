# coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import time
import signal
import logging
import traceback
from copy import deepcopy
from swall.mq import MQ
from swall.crypt import Crypt
from swall.utils import cp, thread, prog_dir, check_cache, make_dirs, Conf, load_env, load_fclient, app_abs_path, load_module
from swall.excpt import SwallCommandExecutionError

log = logging.getLogger()


class JobSubject(object):
    def __init__(self):
        self.observers = []
        self.job = None

    def register(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)

    def unregister(self, observer):
        if observer in self.observers:
            self.observers.remove(observer)

    @thread()
    def notify_observers(self):
        for o in self.observers:
            o.update(self.job)

    def data_changed(self):
        self.notify_observers()

    def set_data(self, job):
        self.job = job
        self.data_changed()


class Agent(object):
    """
    节点处理
    """

    def __init__(self, config):
        self.main_conf = Conf(config["swall"])
        self.node = self.main_conf.node_name
        self.node_ip = self.main_conf.node_ip
        self.node_funcs = self.load_module()
        self.mq = MQ(config)
        self._stop = 0
        self.sys_envs = self.load_env()
        self.job_sub = JobSubject()
        self.job_sub.register(self)
        self.crypt = Crypt(self.main_conf.token)

    def _get_func(self, module=None, *args, **kwargs):
        """
        def _get_func(self, module=None, *args, **kwargs) -> 获取某个模块的所有函数
        @param module string:模块名称
        @return list:
        """
        role_funcs = self.node_funcs
        if module:
            return [k for k in role_funcs if "%s." % module in k]
        else:
            return [k for k in role_funcs]

    def ping(self, *args, **kwargs):
        """
        def ping(self, *args, **kwargs) -> ping节点
        @return int:1
        """
        return 1

    def load_module(self, *args, **kwargs):
        """
        加载模块
        """
        node_funcs = load_module(app_abs_path("module/"))
        node_funcs.update({
            "sys.reload_module": self._reload_module,
            "sys.reload_env": self._reload_env,
            "sys.get_env": self._get_env,
            "sys.copy": self._copy,
            "sys.get": self._get,
            "sys.job_info": self._job_info,
            "sys.exprs": self.exprs,
            "sys.rsync_module": self._rsync_module,
            "sys.ping": self.ping,
            "sys.funcs": self._get_func,
            "sys.version": self._version,
        })
        return node_funcs

    def _job_info(self, jid, *args, **kwargs):
        """
        def _job_info(self, jid, *args, **kwargs) -> get the job info of jid
        @param jid string:the job id
        @return dict:
        """
        #为了加快速度，这部分在client.py实现了，不会调用到这里
        pass

    def _rsync_module(self, *args, **kwargs):
        """
        def rsync_module(*args, **kwargs) -> 同步模块
        @param args list:支持位置参数，例如sys.rsync_module common_tools.py game_tools.py
        @param kwargs dict:支持关键字参数，例如:sys.rsync_module mods=common_tools.py,game_tools.py
        @return int:1 if success
        """
        copy_pair = kwargs.get("copy_pair", [])
        copy_ret = []
        copy_mods = []
        for ifile, dfile in copy_pair:
            dfile = os.path.join(app_abs_path(self.main_conf.module), dfile)
            copy_mods.append(dfile)
            if not ifile:
                log.error("rsync_module [%s] error" % dfile)
                continue
            copy_ret.append(
                self._copy(path_pair="%s,%s" % (ifile, os.path.basename(dfile)), remote_path=dfile,
                           ret_type="full") == dfile)
        if all(copy_ret) and copy_ret:
            log.info(
                "rsync_module [%s] ok" % (','.join([os.path.basename(mod) for mod in copy_mods])))
            self.node_funcs.update(self.load_module())
            return 1
        else:
            return 0

    def _version(self, *args, **kargs):
        """
        def get_version(*args,**kargs) -> 获取swall的版本号
        @return string:
        """
        version = ""
        try:
            program_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ver_file = os.path.join(program_path, "version.txt")
            f = open(ver_file, "r")
            version = f.readline()
        except:
            log.error(traceback.format_exc())
        return version.strip()

    def _reload_module(self, *args, **kwargs):
        """
        def reload_module(*args, **kwargs) -> 重新加载模块
        @return int:1 if sucess
        """
        self.node_funcs.update(self.load_module())
        return 1

    def _reload_env(self, *args, **kwargs):
        """
        def reload_env(self, *args, **kwargs) -> 重新加载env模块
        @return int:1 if sucess
        """
        self.sys_envs = self.load_env()
        return 1

    def _get_env(self, *args, **kwargs):
        """
        def _get_env(self, *args, **kwargs) ->获取系统变量
        @return tuple:
        """
        return [i for i in self.sys_envs]

    def exprs(self, str1, *args, **kwargs):
        """
        def exprs(self, str, *args, **kwargs) -> 扩展env变量
        @param str string:需要扩展的字符串，例如：/tmp/{node}_mnesia.beam
        @return string:扩展以后的字符串，例如/tmp/{node}_mnesia.beam扩展为：/tmp/jxz_tx_5001_mnesia.beam
        """
        return str1

    def load_env(self, *args, **kwargs):
        """
        加载模块
        """
        node_envs = load_env(app_abs_path("module/"))
        return node_envs

    def _copy(self, *args, **kwargs):
        """
        def copy(*args, **kwargs) -> 拷贝文件到远程 可以增加一个ret_type=full，支持返回文件名
        @param args list:支持位置参数，例如 sys.copy /etc/src.tar.gz /tmp/src.tar.gz ret_type=full
        @param kwargs dict:支持关键字参数，例如sys.copy local_path=/etc/src.tar.gz remote_path=/tmp/src.tar.gz ret_type=full
        @return int:1 if success else 0
        """
        if "path_pair" in kwargs and "remote_path" in kwargs:
            fid, file_name = kwargs["path_pair"].split(',')
            remote_path = kwargs["remote_path"]
            make_path = kwargs.get("make_path", 1)
        else:
            fid, file_name = args[0].split(',')
            remote_path = args[1]
            make_path = args[2] if len(args) >= 3 else 1
        stat = kwargs.get("stat")
        ret_type = kwargs.get("ret_type")
        if os.path.isdir(remote_path) or remote_path.endswith('/'):
            remote_path = os.path.join(remote_path, file_name)

        try:
            if int(make_path):
                make_dirs(os.path.dirname(remote_path))
            else:
                if not os.path.exists(os.path.dirname(remote_path)):
                    return ""
        except:
            log.info(traceback.format_exc())

        #如果cache中没有对应的文件，则先从fs中拷贝过来
        if not check_cache(app_abs_path(self.main_conf.cache), fid):
            FsClient = load_fclient(app_abs_path(self.main_conf.fs_plugin), ftype=self.fs_conf.fs_type)
            fscli = FsClient(self.fs_conf)
            fscli.download(fid, os.path.join(app_abs_path(self.main_conf.cache), fid))
            #从cache目录中拷贝文件到目标
        ret = cp(os.path.join(app_abs_path(self.main_conf.cache), fid), remote_path, stat)
        if ret_type == "full":
            return remote_path if ret else ""
        else:
            return ret

    def _get(self, *args, **kwargs):
        """
        def get(*args, **kwargs) -> 从远程获取文件
        @param args list:支持位置参数，例如 sys.get /tmp/src.tar.gz /etc/src.tar.gz
        @param kwargs dict:支持关键字参数，例如sys.get remote_path=/tmp/src.tar.gz local_path=/etc/src.tar.gz
        @return string:local_path
        """
        if "local_path" in kwargs and "remote_path" in kwargs:
            remote_path = kwargs["remote_path"]
        else:
            remote_path = args[0]
        FsClient = load_fclient(app_abs_path(self.main_conf.fs_plugin), ftype=self.fs_conf.fs_type)
        fscli = FsClient(self.fs_conf)
        return fscli.upload(remote_path)

    @thread()
    def loop_tos(self):
        """
        定时检查tos
        """
        while 1:
            if self._stop:
                log.warn("loop_tos stopping")
                return
            try:
                self.mq.tos(self.node)
            except:
                log.error(traceback.format_exc())
            time.sleep(5)

    @thread()
    def loop_job_rev(self):
        """
        实时检查job
        :return:
        """
        while 1:
            if self._stop:
                log.warn("loop_job_rev stopping")
                return
            job = self.mq.get_job(self.node)
            if job:
                self.job_sub.set_data(job)
            time.sleep(0.001)

    def update(self, data):
        """
        执行任务
        """
        try:

            if data["env"] == "aes":
                data["payload"] = self.crypt.loads(data.get("payload"))
            cmd = data["payload"]["cmd"]
            args = list(data["payload"]["args"])
            kwargs = data["payload"]["kwargs"]
            jid = data["payload"]["jid"]
            #修改任务状态为RUNNING
            data_t = deepcopy(data)
            data_t["payload"]["status"] = "RUNNING"
            if data_t["env"] == "aes":
                data_t["payload"] = self.crypt.dumps(data_t.get("payload"))
            self.mq.set_res(self.node, jid, data_t)

            os.chdir(prog_dir())
            ret = ''
            #做一些变量替换，把变量中如{ip}、{node}替换为具体的值
            i = 0
            kwargs.update({"node_name": self.node, "node_ip": self.node_ip})
            env_regx = re.compile(r'{([a-zA-Z0-9]+)}')
            while i < len(args):
                if not isinstance(args[i], str):
                    continue
                matchs = env_regx.findall(args[i])
                for match in matchs:
                    if match in self.sys_envs:
                        val = self.sys_envs[match](**kwargs)
                        args[i] = env_regx.sub(val, args[i], count=1)
                i += 1
            for key in kwargs.iterkeys():
                if not isinstance(kwargs[key], str):
                    continue
                matchs = env_regx.findall(kwargs[key])
                for match in matchs:
                    if match in self.sys_envs:
                        val = self.sys_envs[match](**kwargs)
                        kwargs[key] = env_regx.sub(val, kwargs[key], count=1)

            #判断是否需要返回函数help信息
            if len(args) == 1 and args[0] == "help":
                ret = self.node_funcs[cmd].__doc__
            else:
                ret = self.node_funcs[cmd](
                    *args,
                    **kwargs
                )
        except KeyError as exc:
            ret = "cmd %s not found: %s" % (cmd, str(exc))
        except SwallCommandExecutionError as exc:
            ret = "cmd %s running error: %s" % (cmd, str(exc))
        except TypeError as exc:
            ret = "cmd %s argument error: %s" % (cmd, str(exc))
        except:
            ret = traceback.format_exc()
            log.error(ret)
        finally:
            os.chdir(prog_dir())
        data["payload"]["return"] = ret
        data["payload"]["status"] = "FINISH"
        if data["env"] == "aes":
                data["payload"] = self.crypt.dumps(data.get("payload"))
        self.mq.set_res(self.node, jid, data)
        return True

    def loop(self):
        """
        主体循环
        """
        def sigterm_stop(signum, frame):
            self._stop = 1

        signal.signal(signal.SIGUSR1, sigterm_stop)
        self.loop_tos()
        self.loop_job_rev()
        while 1:
            if self._stop:
                break
            time.sleep(5)

