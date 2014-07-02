#coding:utf-8
__author__ = 'lufeng4828@163.com'

import re
import sys
import imp
import time
import traceback
import hashlib
import functools
import pwd
import pipes
import os
import shutil
import logging
import operator
import subprocess
from signal import SIGUSR1
from threading import Thread
from swall.kthread import KThread
from swall.bfclient import BFClient
from ConfigParser import ConfigParser

log = logging.getLogger()


def c(s, t=None):
    """
    颜色渲染
    """
    color = {
        'r': "\033[1;31;1m%s\033[0m" % s,
        'g': "\033[0;32;1m%s\033[0m" % s,
        'y': "\033[0;33;1m%s\033[0m" % s,
        'b': "\033[0;34;1m%s\033[0m" % s
    }
    return color.get(t) or s


def color(str_ret, t=1):
    """
    颜色渲染
    """
    str_ret = str(str_ret)
    if any([str_ret == '{}', str_ret == '[]', str_ret == '', str_ret == '0', t != 1]):
        return c(str_ret, 'r')
    else:
        return c(str_ret, 'g')


def prog_dir():
    """
    获取程序的根路径
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_abs_path(rel_path=None):
    """
    返回路径的绝对路径，相对程序目录
    :param rel_path:相对路径
    :return:绝对路径
    """
    abs_path = ''
    if rel_path:
        abs_path = os.path.join(prog_dir(), rel_path)
    return abs_path


def listener(state):
    """
    listening for connection events
    @param state
    """
    log.info("zookeeper connection events [%s]" % state)


def node(func):
    """
    修饰器，用来说明修饰的函数是node节点函数
    :param func: 修饰的函数
    """
    func.node = True

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        ret = func(*args, **kwargs)
        return ret

    return wrapped


def env(func):
    """
    修饰器，用来说明修饰的函数是node节点函数
    :param func: 修饰的函数
    """
    func.env = True

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        ret = func(*args, **kwargs)
        return ret

    return wrapped


def gen_node(func):
    """
    修饰器，用来检查生成节点列表的函数返回格式是否正确
    @param func: 修饰的函数
    @return:
    """
    func.node = True

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        nodes = func(*args, **kwargs)
        rets = {}
        for k, v in nodes.iteritems():
            if not all(map(lambda x: x in v, ["agent", "project", "role"])):
                log.error("node [%s] format is error,node info master include :'agent', 'project', 'role'")
                continue
            else:
                rets.update({k: v})
        return rets

    return wrapped


def parse_args_and_kwargs(args):
    """
    解析参数
    @param args string:例如：[arg1, arg2, key1=val1, key2=val2]
    @return (list,dict):
    e.g. (['arg1', 'arg2'], {'val2': 'key2', 'val1': 'key1'})
    """
    r_args = []
    r_kwargs = {}
    for arg in args:
        regx = re.compile(r"([a-z0-9A-Z_-]+)=([a-z0-9A-Z_-]+)")
        kv = regx.findall(arg)
        if kv:
            r_kwargs.update({kv[0][0]: kv[0][1]})
        else:
            r_args.append(arg)
    return r_args, r_kwargs


def thread(is_join=False, pnum=1):
    def _wrap1(func):
        @functools.wraps(func)
        def _wrap2(*args, **kwargs):
            pros = []
            for x in xrange(pnum):
                pros.append(Thread(target=lambda: func(*args, **kwargs)))
            for th in pros:
                th.start()
            if is_join:
                for th in pros:
                    th.join()

        return _wrap2

    return _wrap1


class Automagic(object):
    """
    一个很神奇的类，无法用言语表达
    """

    def __init__(self, clientref, base):
        self.base = base
        self.clientref = clientref

    def __getattr__(self, name):
        base2 = self.base[:]
        base2.append(name)
        return Automagic(self.clientref, base2)

    def __call__(self, *args):
        if not self.base:
            raise AttributeError("something wrong here in Automagic __call__")
        if len(self.base) < 2:
            raise AttributeError("no method called: %s" % ".".join(self.base))
        func = ".".join(self.base[0:])
        return self.clientref.call_func(func, args)


def load_module(mod_dirs):
    """
    加载模块
    @param mod_dirs string:模块的路径
    @return dict:
    """
    names = {}
    modules = []
    funcs = {}
    mod_dirs = mod_dirs.split(',')
    for mod_dir in mod_dirs:
        if not os.path.isdir(mod_dir):
            continue
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith('_'):
                continue
            if fn_.endswith('.py') and not fn_.startswith("_sys_"):
                extpos = fn_.rfind('.')
                if extpos > 0:
                    _name = fn_[:extpos]
                else:
                    _name = fn_
                names[_name] = os.path.join(mod_dir, fn_)
    for name in names:
        try:
            #模块的加载mod_dirs一定是一个list类型数据，否则执行失败
            fn_, path, desc = imp.find_module(name, mod_dirs)
            mod = imp.load_module(name, fn_, path, desc)
        except:
            log.error(traceback.format_exc())
            continue
        modules.append(mod)
    for mod in modules:
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
                #将加载的模块存放到字典里面
            if callable(getattr(mod, attr)):
                func = getattr(mod, attr)
                if isinstance(func, type) and getattr(func, "node", False):
                    if any(['Error' in func.__name__, 'Exception' in func.__name__]):
                        continue
                try:
                    if getattr(func, "node", None):
                        funcs['{0}.{1}'.format(mod.__name__, attr)] = func
                except AttributeError:
                    continue
    return funcs


def load_env(mod_dirs):
    """
    加载系统变量
    """
    names = {}
    modules = []
    funcs = {}
    mod_dirs = mod_dirs.split(',')
    for mod_dir in mod_dirs:
        if not os.path.isdir(mod_dir):
            continue
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith("_sys_") and fn_.endswith(".py"):
                extpos = fn_.rfind('.')
                if extpos > 0:
                    _name = fn_[:extpos]
                else:
                    _name = fn_
                names[_name] = os.path.join(mod_dir, fn_)
    for name in names:
        try:
            #模块的加载mod_dirs一定是一个list类型数据，否则执行失败
            fn_, path, desc = imp.find_module(name, mod_dirs)
            mod = imp.load_module(name, fn_, path, desc)
        except:
            log.error(traceback.format_exc())
            continue
        modules.append(mod)
    for mod in modules:
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
                #将加载的模块存放到字典里面
            if callable(getattr(mod, attr)):
                func = getattr(mod, attr)
                if isinstance(func, type) and getattr(func, "env", False):
                    if any(['Error' in func.__name__, 'Exception' in func.__name__]):
                        continue
                try:
                    #if getattr(func, mod_type, None):
                    funcs['{0}'.format(attr)] = func
                except AttributeError:
                    continue
    return funcs


def load_fclient(mod_dir, ftype="ssh"):
    """
    根据ftype加载fservice
    @param mod_dir string:fs模块目录
    @param ftype string:模块名称
    return BFClient:
    """
    ret = None
    mod_dirs = mod_dir.split(',')
    try:
        #模块的加载mod_dirs一定是一个list类型数据，否则执行失败
        fn_, path, desc = imp.find_module(ftype, mod_dirs)
        mod = imp.load_module(ftype, fn_, path, desc)
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
            if callable(getattr(mod, attr)):
                fcli = getattr(mod, attr)
                if issubclass(fcli, BFClient) and str(fcli) != "BFClient":
                    ret = fcli
                    continue
    except:
        log.error(traceback.format_exc())
    return ret


def make_dirs(path):
    """
    创建多层次的目录
    @param path string:
    @return bool:True or False
    """
    if os.path.exists(path):
        return True
    try:
        os.makedirs(path)
    except OSError:
        return False
    return True


def backup_local(fn, backup_dir, ext):
    """
    备份文件到self.opts['backup_dir']目录，加上后缀
    @param fn string:需要备份的文件
    @param backup_dir string:备份文件存放目录
    @param ext string:备份文件后缀
    @return bool:True or False
    """
    if not os.path.exists(fn):
        return True
    backup_dest = os.path.join(backup_dir, '%s.%s' % (os.path.basename(fn), ext))
    try:
        shutil.copy2(fn, backup_dest)
    except shutil.Error:
        return False
    return True


def cp(src_file, dest_file, stat=None):
    """
    拷贝文件
    @param src_file:
    @param dest_file:
    @return bool:True or False
    """
    try:
        if os.path.isdir(dest_file):
            log.warn("%s is a directory" % dest_file)
            return False
        shutil.copy(src_file, dest_file)
        if stat:
            mode, gid, uid = stat
            if mode != -1:
                os.chmod(dest_file, mode)
            if uid != -1 or gid != -1:
                os.chown(dest_file, uid, gid)
    except:
        log.error(traceback.format_exc())
        return 0
    else:
        return 1


def check_cache(cache_dir, sha):
    """
    检查cache目录是否存在文件
    @param cache_dir string:
    @param sha string:
    @return bool:True or False
    """
    cache_file = os.path.join(cache_dir, sha)
    if os.path.exists(cache_file) and checksum(cache_file) == sha:
        return True
    else:
        return False


def checksum(thing):
    """
    计算文件或者字符串散列
    @param thing string:文件名
    @return string:散列
    """
    CHUNK = 2 ** 16
    thissum = hashlib.new('sha1')
    if os.path.exists(thing):
        fo = open(thing, 'r', CHUNK)
        chunk = fo.read
        while chunk:
            chunk = fo.read(CHUNK)
            thissum.update(chunk)
        fo.close()
        del fo
    else:
        thissum.update(thing)
    return thissum.hexdigest()


def daemonize():
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.stderr.write('fork #1 failed: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1)
        os.setsid()
        os.chdir('/')
        os.umask(022)
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.stderr.write('fork #2 failed: %d (%s)\n' % (e.errno, e.strerror))
            sys.exit(1)


def set_pidfile(pidfile):
    """
    Save the pidfile
    @param pidfile string:
    @return None
    """
    try:
        pf = file(pidfile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        message = 'pidfile %s already exist. Daemon already running?\n'
        sys.stderr.write(message % pidfile)
        sys.exit(1)

    pdir = os.path.dirname(pidfile)
    if not os.path.isdir(pdir):
        os.makedirs(pdir)
    try:
        with open(pidfile, 'w+') as f:
            f.write(str(os.getpid()))
    except IOError, err:
        sys.stderr.write(err.message)
        sys.exit(1)


class Conf(object):
    def __init__(self, config):
        self.config = config
        self.set_opts()

    def set_opts(self):
        """
        set attr for opts
        """
        for opt in self.config:
            setattr(self, opt, self.config[opt])


def load_config(conf_path):
    """
    解析配置文件
    @param conf_path string: 配置路径
    @return dict: 配置信息{key:val}
    """
    opts = {}
    confparser = ConfigParser()
    if os.path.exists(conf_path):
        confparser.read(conf_path)
        for k, v in confparser.items("main"):
            opts[k] = v
    return opts


def kill_daemon(pidfile):
    """
    kill掉守护进程
    @param pidfile string:pid文件
    @return None
    """
    try:
        pf = file(pidfile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        message = 'pidfile %s does not exist. Daemon not running?\n'
        sys.stderr.write(message % pidfile)
        return

    try:
        times = 1
        while times <= 10:
            os.kill(pid, SIGUSR1)
            time.sleep(2)
            times += 1
        sys.stderr.write("Stop Swall daemon fail,the pid is %d" % pid)
    except OSError, err:
        err = str(err)
        if err.find('No such process') > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
        else:
            sys.exit(1)


class Timeout(Exception):
    pass


def timeout(seconds):
    """
    为函数新增超时功能
    """

    def timeout_decorator(func):
        def _new_func(oldfunc, result, oldfunc_args, oldfunc_kwargs):
            result.append(oldfunc(*oldfunc_args, **oldfunc_kwargs))

        def _(*args, **kwargs):
            result = []
            new_kwargs = {
                'oldfunc': func,
                'result': result,
                'oldfunc_args': args,
                'oldfunc_kwargs': kwargs
            }

            thd = KThread(target=_new_func, kwargs=new_kwargs)
            thd.start()
            try:
                thd.join(seconds)
                alive = thd.isAlive()
                thd.kill()
                if alive:
                    raise Timeout(u'%s run timeout %d seconds.' % (func.__name__, seconds))
                elif thd.exception is not None:
                    raise thd.exception
            except KeyboardInterrupt:
                thd.kill()
            return result[0] if result else ''

        _.__name__ = func.__name__
        _.__doc__ = func.__doc__
        return _

    return timeout_decorator


def retry(times, cmp_val=1):
    """
    如果修饰的函数返回结果不等于cmp_val，则重新执行函数，一共重试times
    """

    def fail_retry_decorator(func):
        def _new_func(oldfunc, oldfunc_args, oldfunc_kwargs):
            return oldfunc(*oldfunc_args, **oldfunc_kwargs)

        def _(*args, **kwargs):
            tries = 1
            result = None
            new_kwargs = {
                'oldfunc': func,
                'oldfunc_args': args,
                'oldfunc_kwargs': kwargs
            }
            while tries <= times:
                result = _new_func(**new_kwargs)
                if result == cmp_val:
                    break
                else:
                    print "%s fail,retry %s" % (func.__name__, tries)
                    time.sleep(3)
                    tries += 1
            return result

        _.__name__ = func.__name__
        _.__doc__ = func.__doc__
        return _

    return fail_retry_decorator


def which(exe=None):
    """
    Python clone of POSIX's /usr/bin/which
    """
    if exe:
        (path, name) = os.path.split(exe)
        if os.access(exe, os.X_OK):
            return exe

        # default path based on busybox's default
        default_path = "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin"
        for path in os.environ.get('PATH', default_path).split(os.pathsep):
            full_path = os.path.join(path, exe)
            if os.access(full_path, os.X_OK):
                return full_path
    return None

def _run(cmd,
         cwd=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         quiet=False,
         runas=None,
         with_env=True,
         shell="/bin/bash",
         env={},
         rstrip=True,
         retcode=False):
    # Set the default working directory to the home directory
    # of the user salt-minion is running as.  Default:  /root
    if not cwd:
        cwd = os.path.expanduser('~{0}'.format('' if not runas else runas))

        # make sure we can access the cwd
        # when run from sudo or another environment where the euid is
        # changed ~ will expand to the home of the original uid and
        # the euid might not have access to it. See issue #1844
        if not os.access(cwd, os.R_OK):
            cwd = '/'

    ret = {}

    if runas:
        # Save the original command before munging it
        orig_cmd = cmd
        try:
            pwd.getpwnam(runas)
        except KeyError:
            msg = 'User \'{0}\' is not available'.format(runas)
            log.error(msg)
            return

        cmd_prefix = 'su -s {0}'.format(shell)

        # Load the 'nix environment
        if with_env:
            cmd_prefix += ' -'
            cmd = 'cd {0} && {1}'.format(cwd, cmd)

        cmd_prefix += ' {0} -c'.format(runas)
        cmd = '{0} {1}'.format(cmd_prefix, pipes.quote(cmd))

    if not quiet:
        # Put the most common case first
        if not runas:
            log.info('Executing command {0} in directory {1}'.format(cmd, cwd))
        else:
            log.info('Executing command {0} as user {1} in directory {2}'.format(
                orig_cmd, runas, cwd))

    run_env = os.environ
    run_env.update(env)
    kwargs = {'cwd': cwd,
              'shell': True,
              'env': run_env,
              'stdout': stdout,
              'stderr': stderr}
    if not os.environ.get('os', '').startswith('Windows'):
        kwargs['executable'] = shell
        # This is where the magic happens
    proc = subprocess.Popen(cmd, **kwargs)

    # If all we want is the return code then don't block on gathering input,
    # this is used to bypass ampersand issues with background processes in
    # scripts
    if retcode:
        while True:
            retcode = proc.poll()
            if retcode is None:
                continue
            else:
                out = ''
                err = ''
                break
    else:
        out, err = proc.communicate()

    if rstrip:
        if out:
            out = out.rstrip()
            # None lacks a rstrip() method
        if err:
            err = err.rstrip()

    ret['stdout'] = out
    ret['stderr'] = err
    ret['pid'] = proc.pid
    ret['retcode'] = proc.returncode
    return ret


def run(cmd, cwd=None, runas=None, shell="/bin/bash", env={}):
    """
    Execute the passed command and return the output as a string
    @param cmd string:执行的命令
    @param cmd string:工作目录，执行命令时候需要进入的目录
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
    """
    ret = _run(cmd, runas=runas, shell=shell,
               cwd=cwd, stderr=subprocess.STDOUT, env=env)
    return ret


def sort_ret(rets):
    """
    特定格式的list进行排序
    """
    t = []
    list_result = []
    for role in rets:
        id1 = role
        for node in rets[role]:
            try:
                id2 = '_'.join(node.split('_')[:-1])
                id3 = int(node.split('_')[-1])
            except:
                id2 = '_'.join(node.split('_')[:-1])
                id3 = node.split('_')[-1]
            t.append({"id1": id1, "id2": id2, "id3": id3, "info": (role, node, rets[role][node])})
    t.sort(key=operator.itemgetter("id1", "id2", "id3"))
    for i in t:
        list_result.append(i["info"])
    return list_result
