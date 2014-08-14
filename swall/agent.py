#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import re
import time
import signal
import Queue
import logging
import msgpack
import zookeeper
import traceback
from swall.zkcon import ZKDb
from threading import Lock,\
    Thread
from swall.crypt import Crypt

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

from swall.zkclient import watchmethod
from swall.excpt import SwallCommandExecutionError

log = logging.getLogger()

QUEUE_SIZE = 20000
THREAD_NUM = 10


class Agent(ZKDb):
    """
    节点处理
    """

    def __init__(self, config):
        #初始化下ZKDb的init方法
        super(Agent, self).__init__()

        self.main_conf = Conf(config["swall"])
        self.zookeeper_conf = Conf(config["zk"])
        self.fs_conf = Conf(config["fs"])
        self.zkepoch = 0
        self.queues = {
            "reg_node": Queue.Queue(maxsize=QUEUE_SIZE),
            "get_job": Queue.Queue(maxsize=QUEUE_SIZE),
            "mult_run": Queue.Queue(maxsize=QUEUE_SIZE),
            "sigle_run": Queue.Queue(maxsize=QUEUE_SIZE),
            "ret_job": Queue.Queue(maxsize=QUEUE_SIZE)
        }

        self.locks = {
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
                func = self.node_funcs[role].get(func_name)
                inodes = func(*func_args) if func else {}
                for k in inodes.iterkeys():
                    inodes[k].update({
                        "role": role,
                        "node_name": k,
                        "node_ip": self.main_conf.node_ip
                    })
                nodes.update(inodes)
            else:
                for n in node_name.split(','):
                    nodes[n] = {
                        "project": role_conf.project,
                        "agent": role_conf.agent,
                        "role": role,
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
        role_funcs = self.node_funcs[kwargs["role"]]
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

    def load_module(self, role=None, *args, **kwargs):
        """
        加载模块
        """
        node_funcs = {}
        if role is None:
            loop_roles = self.main_conf.node_role.split(',')
        else:
            loop_roles = [role]

        for role in loop_roles:
            node_funcs.update({
                role: load_module("%s,%s" % (app_abs_path("module/common"), app_abs_path("module/%s" % role)))
            })
            node_funcs[role].update({
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
                "sys.roles": self._get_roles,
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

    def _get_roles(self, *args, **kwargs):
        """
        def roles( *args, **kwargs) -> get all roles of this agent
        @return list:
        """
        iroles = set([])
        for v in self.nodes.itervalues():
            iroles.add(v["role"])
        return list(iroles)

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
        for role, ifile, dfile in copy_pair:
            dfile = os.path.join(app_abs_path(self.main_conf.module), dfile)
            if role != kwargs["role"]:
                continue
            copy_mods.append(dfile)
            if not ifile:
                log.error("rsync_module [%s] error" % dfile)
                continue
            copy_ret.append(
                self._copy(path_pair="%s,%s" % (ifile, os.path.basename(dfile)), remote_path=dfile,
                           ret_type="full") == dfile)
        if all(copy_ret) and copy_ret:
            log.info(
                "rsync_module [%s %s] ok" % (kwargs["role"], ','.join([os.path.basename(mod) for mod in copy_mods])))
            self.node_funcs.update(self.load_module(kwargs["role"]))
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
        role = kwargs["role"]
        self.node_funcs.update(self.load_module(role))
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
        role = kwargs["role"]
        return [i for i in self.sys_envs[role]]

    def exprs(self, str1, *args, **kwargs):
        """
        def exprs(self, str, *args, **kwargs) -> 扩展env变量
        @param str string:需要扩展的字符串，例如：/tmp/{node}_mnesia.beam
        @return string:扩展以后的字符串，例如/tmp/{node}_mnesia.beam扩展为：/tmp/jxz_tx_5001_mnesia.beam
        """
        return str1

    def load_env(self, role=None, *args, **kwargs):
        """
        加载模块
        """
        node_envs = {}
        roles = self._get_roles()
        if not role:
            for r in roles:
                node_envs.update({
                    r: load_env("%s,%s" % (app_abs_path("module/common"), app_abs_path("module/%s" % r)))
                })
        else:
            node_envs.update({
                role: load_env("%s,%s" % (app_abs_path("module/common"), app_abs_path("module/%s" % role)))
            })
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

    def add_node(self, role, role_name, role_ip):
        """
        add_node
        @param role:string 节点所属类型
        @param role_name:string 节点名称
        @parm role_ip:string 角色所在的服务器ip
        @return:bool True or False if add_node fail
        """
        node_path = os.path.join(self.zookeeper_conf.nodes, role, role_name)
        zkcli = self.zkconn
        if zkcli.exists(node_path):
            old_ip = zkcli.get(os.path.join(node_path, "ip"))[0]
            if old_ip != role_ip:
                log.error(
                    "register attempt from %s for %s(%s) failed, the ip in pending is different"
                    % (role_ip, role_name, role)
                )
                return False
            else:
                zkcli.create(os.path.join(node_path, "tos"), flags=zookeeper.EPHEMERAL, force=True)
                log.info("register already accepted from %s for %s(%s)" % (old_ip, role_name, role))
                return True

        ret1 = zkcli.create(os.path.join(node_path, "ip"), role_ip, makepath=True)
        ret2 = zkcli.create(os.path.join(node_path, "jobs"), makepath=True)
        ret3 = zkcli.create(os.path.join(node_path, "result"), makepath=True)
        ret4 = zkcli.create(os.path.join(node_path, "tos"), flags=zookeeper.EPHEMERAL, force=True)
        if all([ret1, ret2, ret3, ret4]):
            log.info("new register accepted from %s for %s(%s) success" % (role_ip, role_name, role))
            return True
        else:
            log.error("new register accepted from %s for %s(%s) fail" % (role_ip, role_name, role))
            return False

    def del_node(self, role, role_name):
        """
        删除节点
        @param role string:角色名
        @param role_name:角色名称
        @return bool:True or False
        """
        zkcli = self.zkconn
        node_path = os.path.join(self.zookeeper_conf.nodes, role, role_name)
        return zkcli.delete(node_path, recursive=True)

    @thread(pnum=1)
    def auto_auth(self):
        """
        循环检查是否需要注册节点
        @return int:1 for success,else 0
        """
        q = self.queues["reg_node"]
        while 1:
            if self._stop:
                log.warn("auto_auth stopping")
                return
            curr_nodes = self.load_node()
            add_nodes = set([v for v in curr_nodes]) - set([v for v in self.nodes])
            del_nodes = set([v for v in self.nodes]) - set([v for v in curr_nodes])
            for node_name in add_nodes:
                q.put(("add", node_name, curr_nodes[node_name]), timeout=5)
            for node_name in del_nodes:
                q.put(("del", node_name, self.nodes[node_name]), timeout=5)
            time.sleep(6)

    @thread(pnum=1)
    def crond_clear_job(self):
        """
        定时清理已经完成的job
        """
        while 1:
            if self._stop:
                log.warn("crond_clear_job stopping")
                return
            try:
                for node_name in self.nodes.keys():
                    job_path = os.path.join(self.zookeeper_conf.nodes, self.nodes[node_name]["role"], node_name, "jobs")
                    jids = self.zkconn.get_children(job_path)
                    for jid in jids:
                        jid_path = os.path.join(job_path, jid)
                        znode = self.zkconn.get(jid_path)
                        job = znode[0]
                        mtime = znode[1]["mtime"] / 1000
                        data = msgpack.loads(job)
                        if data["env"] == "aes":
                            key_str = self.main_conf.token
                            crypt = Crypt(key_str)
                            data["payload"] = crypt.loads(data.get("payload"))
                        cur_t = int(time.strftime('%s', time.localtime()))
                        delay_sec = cur_t - mtime
                        keep_job_time = getattr(self.main_conf, "keep_job_time", 604800)

                        if delay_sec >= keep_job_time:
                            zkcli = self.zkconn
                            if zkcli.delete(jid_path):
                                log.info("delete the timeout %s %s job [%s] ok" % (keep_job_time,
                                                                                   data["payload"]["status"], jid))
                            else:
                                log.error("delete the timeout %s %s job [%s] fail" % (keep_job_time,
                                                                                      data["payload"]["status"], jid))
            except:
                log.error(traceback.format_exc())
            time.sleep(5)

    @thread(pnum=1)
    def loop_tos(self):
        """
        定时检查tos
        """
        while 1:
            if self._stop:
                log.warn("loop_tos stopping,delete tos")
                for node_name in self.nodes:
                    node_path = os.path.join(self.zookeeper_conf.nodes, self.nodes[node_name]["role"], node_name)
                    if zkcli.exists(os.path.join(node_path, "tos")):
                        zkcli.delete(os.path.join(node_path, "tos"))
                return
            try:
                zkcli = self.zkconn
                for node_name in self.nodes:
                    node_path = os.path.join(self.zookeeper_conf.nodes, self.nodes[node_name]["role"], node_name)
                    if not zkcli.exists(os.path.join(node_path, "tos")):
                        zkcli.create(os.path.join(node_path, "tos"), flags=zookeeper.EPHEMERAL)
            except:
                log.error(traceback.format_exc())
            time.sleep(5)

    @thread(pnum=1)
    def node_watcher(self):

        @watchmethod
        def recv_job(event):
            children = self.zkconn.get_children(event.path, watcher=recv_job)
            if event and event.type_name == "child":
                add_jobs = set(children) - self.node_jobs.get(event.path, set([]))
                if add_jobs:
                    self.node_jobs[event.path] = set(children)
                    dist_role = event.path.split('/')[-3]
                    dist_node = event.path.split('/')[-2]
                    log.info("[%s %s] receive job [%s]" % (dist_role, dist_node, ','.join(add_jobs)))
                    for jid in add_jobs:
                        self.queues["get_job"].put((dist_role, dist_node, jid), timeout=5)

        def rewatch():
            for i in self.nodes.keys():
                path = os.path.join(self.zookeeper_conf.nodes, self.nodes[i]["role"], i, "jobs")
                self.zkconn.get_children(path, watcher=recv_job)

        while 1:
            if self._stop:
                log.warn("node_watcher stopping")
                return
            try:
                q = self.queues["reg_node"]
                zkconn = self.zkconn
                if self.zkepoch and zkconn.epoch != self.zkepoch:
                    log.warn("start rewatch")
                    rewatch()
                    self.zkepoch = zkconn.epoch
                if q.empty():
                    time.sleep(0.5)
                    continue
                action, node_name, node_info = q.get(timeout=5)
                job_path = os.path.join(self.zookeeper_conf.nodes, node_info["role"], node_name, "jobs")
                if action == "add":
                    if self.add_node(node_info["role"], node_name, node_info["node_ip"]):
                        children = zkconn.get_children(job_path, watcher=recv_job)
                        self.node_jobs[job_path] = set(children)
                        #加载系统变量
                        if node_info["role"] not in self.sys_envs:
                            self.sys_envs.update(self.load_env(node_info["role"]))
                        log.info("register node [%s %s] ok" % (node_info["role"], node_name))
                        self.nodes[node_name] = node_info
                    else:
                        log.error("register node [%s %s] fail" % (node_info["role"], node_name))
                else:
                    if self.del_node(node_info["role"], node_name):
                        log.info("delete node [%s %s] ok" % (node_info["role"], node_name))
                        self.node_jobs.pop(job_path)
                        self.nodes.pop(node_name)
                    else:
                        log.error("delete node [%s %s] fail" % (node_info["role"], node_name))
            except:
                log.error(traceback.format_exc())

    @thread(pnum=THREAD_NUM)
    def get_job(self):
        """
        获取job内容，发送到执行队列，并修改任务状态
        """
        while 1:
            if self._stop:
                log.warn("get_job stopping")
                return
            if self.locks["get_job"].acquire():
                if self.queues["get_job"].empty():
                    self.locks["get_job"].release()
                    time.sleep(0.5)
                    continue
                dist_role, dist_node, jid = self.queues["get_job"].get(timeout=5)
                self.queues["get_job"].task_done()
                self.locks["get_job"].release()
                node_base_dir = self.zookeeper_conf.nodes
                jid_path = os.path.join(node_base_dir, dist_role, dist_node, "jobs", jid)
                try:
                    job = self.zkconn.get(jid_path)[0]
                    data = msgpack.loads(job)
                    if data["env"] == "aes":
                        key_str = self.main_conf.token
                        crypt = Crypt(key_str)
                        data["payload"] = crypt.loads(data.get("payload"))
                    if data["payload"]["status"] != "READY":
                        continue
                    data["payload"]["role"] = dist_role
                    data["payload"]["node_name"] = dist_node
                    #发送到执行队列中
                    if data["payload"].get("nthread"):
                        self.queues["sigle_run"].put(msgpack.dumps(data), timeout=5)
                    else:
                        self.queues["mult_run"].put(msgpack.dumps(data), timeout=5)

                    data["payload"]["status"] = "RUNNING"
                    if data["env"] == "aes":
                        key_str = self.main_conf.token
                        crypt = Crypt(key_str)
                        data["payload"] = crypt.dumps(data.get("payload"))
                        #修改任务状态为RUNNING
                    self.zkconn.set(jid_path, msgpack.dumps(data))
                except:
                    log.error(traceback.format_exc())
                    self.queues["get_job"].put((dist_role, dist_node, jid))

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
                role, cmd, node_name = data["payload"]["role"], data["payload"]["cmd"], data["payload"][
                    "node_name"]
                #做一些变量替换，把变量中如{ip}、{node}替换为具体的值
                i = 0
                args = list(data["payload"]["args"])
                data["payload"]["kwargs"].update(self.nodes.get(node_name, {}))
                while i < len(args):
                    if not isinstance(args[i], str):
                        continue
                    matchs = env_regx.findall(args[i])
                    for match in matchs:
                        if match in self.sys_envs[role]:
                            val = self.sys_envs[role][match](**data["payload"]["kwargs"])
                            args[i] = env_regx.sub(val, args[i], count=1)
                    i += 1
                kwargs = data["payload"]["kwargs"]
                for key in kwargs.iterkeys():
                    if not isinstance(kwargs[key], str):
                        continue
                    matchs = env_regx.findall(kwargs[key])
                    for match in matchs:
                        if match in self.sys_envs[role]:
                            val = self.sys_envs[role][match](**data["payload"]["kwargs"])
                            kwargs[key] = env_regx.sub(val, kwargs[key], count=1)

                def do(data):
                    #判断是否需要返回函数help信息
                    os.chdir(prog_dir())
                    try:
                        if len(data["payload"]["args"]) == 1 and data["payload"]["args"][0] == "help":
                            ret = self.node_funcs[role][cmd].__doc__
                        else:
                            ret = self.node_funcs[role][cmd](
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
                    self.queues["ret_job"].put(msgpack.dumps(data), timeout=5)

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
                try:
                    role, cmd, node_name = data["payload"]["role"], data["payload"]["cmd"], data["payload"][
                        "node_name"]
                    #做一些变量替换，把变量中如{ip}、{node}替换为具体的值
                    i = 0
                    args = list(data["payload"]["args"])
                    data["payload"]["kwargs"].update(self.nodes.get(node_name, {}))
                    while i < len(args):
                        if not isinstance(args[i], str):
                            continue
                        matchs = env_regx.findall(args[i])
                        for match in matchs:
                            if match in self.sys_envs[role]:
                                val = self.sys_envs[role][match](**data["payload"]["kwargs"])
                                args[i] = env_regx.sub(val, args[i], count=1)
                        data["payload"]["args"] = args
                        i += 1
                    kwargs = data["payload"]["kwargs"]
                    for key in kwargs.iterkeys():
                        if not isinstance(kwargs[key], str):
                            continue
                        matchs = env_regx.findall(kwargs[key])
                        for match in matchs:
                            if match in self.sys_envs[role]:
                                val = self.sys_envs[role][match](**data["payload"]["kwargs"])
                                kwargs[key] = env_regx.sub(val, kwargs[key], count=1)

                    log.info("[%s %s] start run job [%s]" % (
                        data["payload"]["role"], data["payload"]["node_name"], data["payload"]["jid"])
                    )
                    #判断是否需要返回函数help信息
                    if len(data["payload"]["args"]) == 1 and data["payload"]["args"][0] == "help":
                        ret = self.node_funcs[role][cmd].__doc__
                    else:
                        ret = self.node_funcs[role][cmd](
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
                self.queues["ret_job"].put(msgpack.dumps(data), timeout=5)

    @thread(pnum=THREAD_NUM)
    def send_ret(self):
        """
        发送结果
        """
        while 1:
            if self._stop:
                log.warn("send_ret stopping")
                return
            if self.locks["ret_job"].acquire():
                if self.queues["ret_job"].empty():
                    self.locks["ret_job"].release()
                    time.sleep(0.5)
                    continue
                data = msgpack.loads(self.queues["ret_job"].get(timeout=5))
                self.queues["ret_job"].task_done()
                self.locks["ret_job"].release()
                node_base_dir = self.zookeeper_conf.nodes
                jid_path = os.path.join(
                    node_base_dir,
                    data["payload"]["role"],
                    data["payload"]["node_name"],
                    "jobs",
                    data["payload"]["jid"]
                )
                log.info("[%s %s] send the result of job [%s]" % (
                    data["payload"]["role"], data["payload"]["node_name"], data["payload"]["jid"]))
                try:
                    if data["env"] == "aes":
                        key_str = self.main_conf.token
                        crypt = Crypt(key_str)
                        data["payload"] = crypt.dumps(data.get("payload"))

                    #遇到过set返回成功但是却没有更新的情况，这里尝试set两次看看
                    self.zkconn.set(jid_path, msgpack.dumps(data))
                    time.sleep(0.0001)
                    set_ret = self.zkconn.set(jid_path, msgpack.dumps(data))

                    if set_ret != 0:
                        log.error("send result error,retcode is [%s]" % set_ret)
                except:
                    log.error(traceback.format_exc())

    def loop(self):
        """
        主体循环
        """

        def sigterm_stop(signum, frame):
            self._stop = 1

        signal.signal(signal.SIGUSR1, sigterm_stop)
        self.auto_auth()
        self.node_watcher()
        self.loop_tos()
        self.get_job()
        self.run_job()
        self.single_run_job()
        self.send_ret()
        self.crond_clear_job()
        while 1:
            if self._stop:
                break
            time.sleep(5)

