# coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import time
import signal
import Queue
import logging
import msgpack
import traceback
from threading import Lock, \
    Thread
from swall.crypt import Crypt
from swall.mq import MQ
from swall.utils import cp, \
    thread, \
    prog_dir, \
    check_cache, \
    make_dirs, \
    Conf, \
    load_env, \
    load_config, \
    load_fclient, \
    app_abs_path, \
    load_module

from swall.excpt import SwallCommandExecutionError

log = logging.getLogger()

QUEUE_SIZE = 20000
THREAD_NUM = 30


class Agent(object):
    """
    节点处理
    """

    def __init__(self, config):
        #初始化下ZKDb的init方法
        super(Agent, self).__init__()

        self.main_conf = Conf(config["swall"])
        self.mq = MQ(config)
        self.queues = {
            "reg_node": Queue.Queue(maxsize=QUEUE_SIZE),
            "get_job": Queue.Queue(maxsize=QUEUE_SIZE),
            "mult_run": Queue.Queue(maxsize=QUEUE_SIZE),
            "sigle_run": Queue.Queue(maxsize=QUEUE_SIZE),
            "ret_job": Queue.Queue(maxsize=QUEUE_SIZE)
        }

        self.locks = {
            "recv_job": Lock(),
            "get_job": Lock(),
            "mult_run": Lock(),
            "ret_job": Lock()
        }
        self.node_jobs = {}
        self.watch_procs = {}
        self.reg_nodes = {}
        self.node_types = {}
        self.node_funcs = self.load_module()
        self.nodes = {}
        self.sys_envs = {}
        self._stop = 0
        self.running_jobs = set([])

    def load_node(self, *args, **kwargs):
        """
        加载节点
        return dict:
        """
        nodes = {}
        node_roles = self.main_conf.node_role.split(',')
        for role in node_roles:
            conf = load_config(os.path.join(self.main_conf.config_dir, "roles.d", "%s.conf" % role))
            role_conf = Conf(conf)
            node_name = role_conf.node_name
            if node_name.startswith("@@"):
                func_str = node_name.lstrip("@@").split()
                if len(func_str) > 1:
                    func_name = func_str[0]
                    func_args = func_str[1:]
                else:
                    func_name = func_str[0]
                    func_args = []
                func = self.node_funcs.get(func_name)
                inodes = func(*func_args) if func else {}
                for k in inodes.iterkeys():
                    inodes[k].update({
                        "node_name": k,
                        "node_ip": self.main_conf.node_ip
                    })
                nodes.update(inodes)
            else:
                for n in node_name.split(','):
                    nodes[n] = {
                        "project": role_conf.project,
                        "agent": role_conf.agent,
                        "node_name": n,
                        "node_ip": self.main_conf.node_ip
                    }
        return nodes

    def _reload_node(self, *args, **kwargs):
        """
        def reload_node(*args, **kwargs) -> 重新加载节点
        @param args list:
        @param kwargs dict:
        @return int:1 if success
        """
        self.nodes = self.load_node()
        return 1

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
            "sys.reload_node": self._reload_node,
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

    def add_node(self, node_data):
        """
        add_node
        @parm node_data:dict
        @return:bool True or False if add_node fail
        """
        exist_info = self.mq.exists(node_data.keys())
        if exist_info:
            exist_nodes = [i for i in exist_info if exist_info[i] is not None]
        else:
            exist_nodes = []
        data = self.mq.get_tos(exist_nodes)
        add_nodes = set(node_data.keys()) - set(exist_nodes)
        for node in data:
            name, old_ip, _, = node
            if old_ip != node_data[name]:
                log.error(
                    "register attempt from %s for %s failed, the ip in pending is different"
                        % (node_data[name], name)
                )
            else:
                add_nodes.add(name)
        if add_nodes:
            if self.mq.register(list(add_nodes)):
                log.info("[%s] new register accepted" % len(add_nodes))
                return True
        return False

    def del_node(self, role_name):
        """
        删除节点
        @param role_name:角色名称
        @return bool:True or False
        """
        return self.mq.unregister(role_name)

    @thread(pnum=1)
    def auto_auth(self):
        """
        循环检查是否需要注册节点
        @return int:1 for success,else 0
        """
        self.sys_envs.update(self.load_env())
        while 1:
            if self._stop:
                log.warn("auto_auth stopping")
                return
            curr_nodes = self.load_node()
            add_nodes = set(curr_nodes.keys()) - set(self.nodes.keys())
            del_nodes = set(self.nodes.keys()) - set(curr_nodes.keys())
            node_data = {}
            for node_name in add_nodes:
                node_info = curr_nodes.get(node_name, {})
                node_ip = node_info.get("node_ip")
                if node_info and node_ip:
                    node_data[node_name] = node_ip
            if self.add_node(node_data):
                for node_name in node_data:
                    self.nodes[node_name] = curr_nodes.get(node_name, {})

            for node_name in del_nodes:
                if node_name in self.nodes.keys():
                    del self.nodes[node_name]
            for node_name in del_nodes:
                if self.del_node(node_name):
                    log.info("delete node [%s] ok" % node_name)
                else:
                    log.error("delete node [%s] fail" % node_name)
            time.sleep(7)

    @thread(pnum=1)
    def loop_tos(self):
        """
        定时检查tos
        """
        while 1:
            if self._stop:
                log.warn("loop_tos stopping")
                return
            try:
                self.mq.tos(self.nodes.keys())
            except:
                log.error(traceback.format_exc())
            time.sleep(5)

    @thread(pnum=5)
    def loop_job_rev(self):
        """
        实时检查job
        :return:
        """
        while 1:
            message = None
            if self.locks["recv_job"].acquire():
                try:
                    message = self.mq.pubsub.get_message()
                except:
                    time.sleep(0.0001)
                self.locks["recv_job"].release()
                if message and message["type"] == "pmessage":
                    channel = message["channel"]
                    data = channel.replace("__keyspace@0__:_swall:_job:", '').split(':')
                    if len(data) != 2:
                        continue
                    dist_node, jid = tuple(data)
                    if '%s@%s' % (jid, dist_node) in self.running_jobs:
                        continue
                    self.queues["get_job"].put((dist_node, jid), timeout=5)
                else:
                    time.sleep(0.001)
            else:
                time.sleep(0.001)

    @thread(pnum=THREAD_NUM)
    def get_job(self):
        """
        获取job内容，发送到执行队列，并修改任务状态
        """
        key_str = self.main_conf.token
        crypt = Crypt(key_str)
        while 1:
            if self._stop:
                log.warn("get_job stopping")
                return
            if self.locks["get_job"].acquire():
                if self.queues["get_job"].empty():
                    self.locks["get_job"].release()
                    time.sleep(0.5)
                    continue
                dist_node, jid = self.queues["get_job"].get(timeout=5)
                self.queues["get_job"].task_done()
                self.locks["get_job"].release()
                try:
                    data = self.mq.get_job(dist_node, jid)
                    if data["env"] == "aes":
                        data["payload"] = crypt.loads(data.get("payload"))
                    if data["payload"]["status"] != "READY":
                        continue
                    self.running_jobs.add('%s@%s' % (jid, dist_node))
                    data["payload"]["node_name"] = dist_node
                    #发送到执行队列中
                    if data["payload"].get("nthread"):
                        self.queues["sigle_run"].put(msgpack.dumps(data), timeout=5)
                    else:
                        self.queues["mult_run"].put(msgpack.dumps(data), timeout=5)

                    data["payload"]["status"] = "RUNNING"
                    if data["env"] == "aes":
                        data["payload"] = crypt.dumps(data.get("payload"))
                        #修改任务状态为RUNNING
                    self.mq.set_job([dist_node, jid, msgpack.dumps(data)])
                except:
                    log.error(traceback.format_exc())
                    self.queues["get_job"].put((dist_node, jid))

    @thread(pnum=1)
    def single_run_job(self):
        """
        执行一定数量的任务
        """
        env_regx = re.compile(r'{([a-zA-Z0-9]+)}')
        while 1:
            if self._stop:
                log.warn("single_run_job stopping")
                return
            try:
                if self.queues["sigle_run"].empty():
                    time.sleep(1)
                    continue
                log.info("single_run_job start")
                data = msgpack.loads(self.queues["sigle_run"].get(timeout=5))
                cmd, node_name = data["payload"]["cmd"], data["payload"]["node_name"]
                #做一些变量替换，把变量中如{ip}、{node}替换为具体的值
                i = 0
                args = list(data["payload"]["args"])
                data["payload"]["kwargs"].update(self.nodes.get(node_name, {}))
                while i < len(args):
                    if not isinstance(args[i], str):
                        continue
                    matchs = env_regx.findall(args[i])
                    for match in matchs:
                        if match in self.sys_envs:
                            val = self.sys_envs[match](**data["payload"]["kwargs"])
                            args[i] = env_regx.sub(val, args[i], count=1)
                    i += 1
                kwargs = data["payload"]["kwargs"]
                for key in kwargs.iterkeys():
                    if not isinstance(kwargs[key], str):
                        continue
                    matchs = env_regx.findall(kwargs[key])
                    for match in matchs:
                        if match in self.sys_envs:
                            val = self.sys_envs[match](**data["payload"]["kwargs"])
                            kwargs[key] = env_regx.sub(val, kwargs[key], count=1)

                def do(data):
                    #判断是否需要返回函数help信息
                    os.chdir(prog_dir())
                    try:
                        if len(data["payload"]["args"]) == 1 and data["payload"]["args"][0] == "help":
                            ret = self.node_funcs[cmd].__doc__
                        else:
                            ret = self.node_funcs[cmd](
                                *data["payload"]["args"],
                                **data["payload"]["kwargs"]
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
                    self.queues["ret_job"].put((node_name, msgpack.dumps(data)), timeout=5)

                works = []
                log.info("nthread [%s]" % data["payload"]["nthread"])
                for i in xrange(data["payload"]["nthread"]):
                    t = Thread(target=lambda: do(data))
                    works.append(t)
                    t.start()
                for proc in works:
                    proc.join()
            except:
                log.error(traceback.format_exc())

    @thread(pnum=THREAD_NUM)
    def run_job(self):
        """
        执行任务
        """
        env_regx = re.compile(r'{([a-zA-Z0-9]+)}')
        while 1:
            if self._stop:
                log.warn("run_job stopping")
                return
            if self.locks["mult_run"].acquire():
                if self.queues["mult_run"].empty():
                    self.locks["mult_run"].release()
                    time.sleep(0.5)
                    continue
                data = msgpack.loads(self.queues["mult_run"].get(timeout=5))
                self.queues["mult_run"].task_done()
                self.locks["mult_run"].release()
                os.chdir(prog_dir())
                ret = ''
                cmd, node_name = data["payload"]["cmd"], data["payload"]["node_name"]
                try:
                    #做一些变量替换，把变量中如{ip}、{node}替换为具体的值
                    i = 0
                    args = list(data["payload"]["args"])
                    data["payload"]["kwargs"].update(self.nodes.get(node_name, {}))
                    while i < len(args):
                        if not isinstance(args[i], str):
                            continue
                        matchs = env_regx.findall(args[i])
                        for match in matchs:
                            if match in self.sys_envs:
                                val = self.sys_envs[match](**data["payload"]["kwargs"])
                                args[i] = env_regx.sub(val, args[i], count=1)
                        data["payload"]["args"] = args
                        i += 1
                    kwargs = data["payload"]["kwargs"]
                    for key in kwargs.iterkeys():
                        if not isinstance(kwargs[key], str):
                            continue
                        matchs = env_regx.findall(kwargs[key])
                        for match in matchs:
                            if match in self.sys_envs:
                                val = self.sys_envs[match](**data["payload"]["kwargs"])
                                kwargs[key] = env_regx.sub(val, kwargs[key], count=1)

                    #判断是否需要返回函数help信息
                    if len(data["payload"]["args"]) == 1 and data["payload"]["args"][0] == "help":
                        ret = self.node_funcs[cmd].__doc__
                    else:
                        ret = self.node_funcs[cmd](
                            *data["payload"]["args"],
                            **data["payload"]["kwargs"]
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
                self.queues["ret_job"].put((node_name, msgpack.dumps(data)), timeout=5)

    @thread(pnum=THREAD_NUM)
    def send_ret(self):
        """
        发送结果
        """
        key_str = self.main_conf.token
        crypt = Crypt(key_str)
        while 1:
            if self._stop:
                log.warn("send_ret stopping")
                return
            if self.locks["ret_job"].acquire():
                if self.queues["ret_job"].empty():
                    self.locks["ret_job"].release()
                    time.sleep(0.005)
                    continue
                result = []
                for _ in xrange(100):
                    try:
                        node_name, data = self.queues["ret_job"].get(block=False)
                        result.append((node_name, data))
                    except Queue.Empty:
                        continue
                self.queues["ret_job"].task_done()
                self.locks["ret_job"].release()
                log.info("send [%s] result" % len(result))
                rets = []
                del_jobs = []
                for res in result:
                    data = res[1]
                    node_name = res[0]
                    data = msgpack.loads(data)
                    jid = data["payload"]["jid"]
                    del_jobs.append('%s@%s' % (jid, node_name))
                    try:
                        if data["env"] == "aes":
                            data["payload"] = crypt.dumps(data.get("payload"))
                        rets.append((node_name, jid, msgpack.dumps(data)))
                    except:
                        log.error(traceback.format_exc())
                if rets:
                    if self.mq.set_job(rets):
                        for i in del_jobs:
                            if i in self.running_jobs:
                                self.running_jobs.remove(i)

    @thread(pnum=1)
    def check_redis(self):
        while 1:
            if not self.mq.ping():
                log.info("redis ping false")
                self.mq.is_repubsub = True
            time.sleep(0.001)

    def loop(self):
        """
        主体循环
        """

        def sigterm_stop(signum, frame):
            self._stop = 1

        signal.signal(signal.SIGUSR1, sigterm_stop)
        self.auto_auth()
        self.loop_tos()
        self.get_job()
        self.run_job()
        self.check_redis()
        self.loop_job_rev()
        self.single_run_job()
        self.send_ret()
        while 1:
            if self._stop:
                break
            time.sleep(5)

