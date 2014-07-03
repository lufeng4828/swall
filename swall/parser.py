#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import sys
import logger
import logging
import optparse
from swall.utils import c, \
    format_obj, \
    daemonize, \
    app_abs_path, \
    parse_args_and_kwargs, \
    color, \
    sort_ret, \
    kill_daemon, \
    agent_config, \
    set_pidfile

from swall.client import Client
from swall.agent import Agent
from swall.keeper import Keeper


class OptionParserMeta(type):
    def __new__(cls, name, bases, attrs):
        instance = super(OptionParserMeta, cls).__new__(cls, name, bases, attrs)
        if not hasattr(instance, '_mixin_setup_funcs'):
            instance._mixin_setup_funcs = []
        if not hasattr(instance, '_mixin_process_funcs'):
            instance._mixin_process_funcs = []

        for base in bases + (instance,):
            func = getattr(base, '_mixin_setup', None)
            if func is not None and func not in instance._mixin_setup_funcs:
                instance._mixin_setup_funcs.append(func)

        return instance


class BaseOptionParser(optparse.OptionParser, object):
    usage = '%prog [OPTIONS] COMMAND [arg...]'
    description = None
    version = None

    def __init__(self, *args, **kwargs):
        if self.version:
            kwargs.setdefault('version', self.version)

        kwargs.setdefault('usage', self.usage)

        if self.description:
            kwargs.setdefault('description', self.description)

        optparse.OptionParser.__init__(self, *args, **kwargs)

    def parse_args(self, args=None, values=None):
        options, args = optparse.OptionParser.parse_args(self, args, values)
        self.options, self.args = options, args
        return options, args

    def _populate_option_list(self, option_list, add_help=True):
        optparse.OptionParser._populate_option_list(
            self, option_list, add_help=add_help
        )
        for mixin_setup_func in self._mixin_setup_funcs:
            mixin_setup_func(self)

    def print_help(self, file=None):
        """
        overwrite the print_help
        """
        if file is None:
            file = sys.stdout
        result = []
        if self.usage:
            result.append(self.get_usage() + "\n")
        if self.description:
            result.append(self.description)
        result.append(self.format_option_help(self.formatter))

        encoding = self._get_encoding(file)
        file.write("%s\n" % "".join(result).encode(encoding, "replace"))


class ConfParser(BaseOptionParser):
    def setup_config(self):
        opts = {}
        for f in ('swall', 'zk', 'fs'):
            opts[f] = agent_config(self.get_config_file_path("%s.conf" % f))
        return opts

    def __merge_config_with_cli(self, *args):
        for option in self.option_list:
            if option.dest is None:
                continue
            value = getattr(self.options, option.dest)
            if option.dest not in self.config["swall"]:
                if value is not None:
                    self.config["swall"][option.dest] = value
            elif value is not None and value != self.config["swall"][option.dest]:
                self.config["swall"][option.dest] = value

        for group in self.option_groups:
            for option in group.option_list:
                if option.dest is None:
                    continue
                value = getattr(self.options, option.dest)
                if option.dest not in self.config["swall"]:
                    if value is not None:
                        self.config["swall"][option.dest] = value
                elif value is not None and value != self.config["swall"][option.dest]:
                    self.config["swall"][option.dest] = value

    def parse_args(self, args=None, values=None):
        options, args = super(ConfParser, self).parse_args(args, values)
        self.process_config_dir()
        logger.setup_file_logger(app_abs_path(self.config["swall"]["log_file"]), self.config["swall"]["log_level"])
        return options, args

    def process_config_dir(self):
        self.options.config_dir = os.path.abspath(self.options.config_dir)
        if hasattr(self, 'setup_config'):
            self.config = self.setup_config()
            self.__merge_config_with_cli()

    def get_config_file_path(self, configfile):
        return os.path.join(self.options.config_dir, configfile)


class ConfMin(object):
    def _mixin_setup(self):
        group = optparse.OptionGroup(
            self, "Options for conf_dir"
        )
        self.add_option_group(group)
        group.add_option(
            '-c', '--config_dir', dest='config_dir',
            default='/data/swall/conf',
            help='Pass in an alternative configuration dir. Default: %default'
        )


class DaemonMin(object):
    def _mixin_setup(self):
        group = optparse.OptionGroup(
            self, "Options for swalld daemon"
        )
        self.add_option_group(group)
        group.add_option(
            '-D', dest='daemon',
            default=True,
            action='store_false',
            help='Run the {0} as a non daemon'.format(self.get_prog_name())
        )
        group.add_option(
            '-C', '--cache_dir', dest='cache',
            help='Specify the cache dir'
        )
        group.add_option(
            '-B', '--backup_dir', dest='backup',
            help='Specify the backup dir'
        )
        group.add_option(
            '-p', '--pid_file', dest='pidfile',
            help='Specify the location of the pidfile. Default: %default'
        )

    def daemonize_if_required(self):
        if self.options.daemon:
            daemonize()

    def set_pidfile(self):
        set_pidfile(self.config["swall"]['pidfile'])


class CtlMin(object):
    def _mixin_setup(self):
        group = optparse.OptionGroup(
            self, "Options for swall ctl"
        )
        self.add_option_group(group)
        group.add_option('-e', '--exclude',
                         default='',
                         dest='exclude',
                         help='Specify the exclude hosts by regix'
        )
        group.add_option('-t', '--timeout',
                         default=30,
                         dest='timeout',
                         help='Specify the timeout,the unit is second'
        )
        group.add_option('-r', '--is_raw',
                         action="store_true",
                         default=False,
                         dest='is_raw',
                         help='Specify the raw output'
        )
        group.add_option('-n', '--nthread',
                         default=-1,
                         dest='nthread',
                         help='Specify running nthread'
        )
        group.add_option('-F', '--no_format',
                         action="store_true",
                         default=False,
                         dest='no_format',
                         help='Do not format the output'
        )


class MainParser(object):
    def __init__(self, *args, **kwargs):
        self.usage = "Usage: %s [OPTIONS] COMMAND [arg...]" % sys.argv[0]
        self.description = """
A approach to infrastructure management.

  Commands:
    server     Manage a agent server:start,stop,restart
    ctl        Send functions to swall server
    manage     Tools to manage the swall cluster

"""

    def print_help(self, file=None):
        """
        overwrite the print_help
        """
        if file is None:
            file = sys.stdout
        result = []
        result.append(self.usage)
        result.append(self.description)
        file.write("%s\n" % "".join(result))


class InitParser(ConfParser, ConfMin):
    __metaclass__ = OptionParserMeta

    def __init__(self, *args, **kwargs):
        super(InitParser, self).__init__(*args, **kwargs)
        self.usage = '%prog init [OPTIONS]'
        self.description = """
Init zookeeper db for swall at first.

"""

    def _mixin_setup(self):
        group = optparse.OptionGroup(
            self, "Options for init zookeeper"
        )
        self.add_option_group(group)
        group.add_option(
            '-f', "--force", dest='force',
            default=False,
            action='store_true',
            help='Force init zookeeper db'
        )


class ServerParser(ConfParser, DaemonMin, ConfMin):
    __metaclass__ = OptionParserMeta

    def __init__(self, *args, **kwargs):
        super(ServerParser, self).__init__(*args, **kwargs)
        self.usage = '%prog server [OPTIONS] COMMAND'
        self.description = """
Run swall server.

  Commands:
    start       start swall server
    stop        stop swall server
    restart     restart swall server
    status      show the status of the swall server

"""


class ManageParser(ConfParser, ConfMin):
    __metaclass__ = OptionParserMeta

    def __init__(self, *args, **kwargs):
        super(ManageParser, self).__init__(*args, **kwargs)
        self.usage = '%prog manage  [OPTIONS] COMMAND'
        self.description = """
Manage tool for  swall server.

  Commands:
    init       Init zookeeper db for swall server
    info       Show same information for swall

"""


class CtlParser(ConfParser, CtlMin, ConfMin):
    __metaclass__ = OptionParserMeta

    def __init__(self, *args, **kwargs):
        super(CtlParser, self).__init__(*args, **kwargs)
        self.usage = '%prog ctl  <role> [target] <module.function> [arguments]'
        self.description = """
Send command to swall server.

"""


class Ctl(CtlParser):
    """
    发送命令
    """

    def main(self):
        self.parse_args()
        args, kwargs = parse_args_and_kwargs(self.args[1:])

        if len(args) < 2:
            self.print_help()
            sys.exit(1)
            #解析参数，获取位置参数和关键字参数

        cli = Client(
            globs=args[1],
            exclude_globs=self.options.exclude,
            role=args[0],
            nthread=int(self.options.nthread),
            conf_dir=self.options.config_dir
        )
        rets = {}
        if args[2] == "sys.job_info":
            if len(args[3:]) == 0 and len(kwargs) == 0:
                sys.stderr.write(c("jid needed for sys.job_info\n", 'r'))
                sys.stderr.flush()
            else:
                rets = cli.job_info(*args[3:], **kwargs)
        else:
            cli.submit_job(args[2], *args[3:], **kwargs)
            rets = cli.get_return(self.options.timeout)

        if rets:
            rets = sort_ret(rets)
        else:
            print c('#' * 50, 'y')
            print color(rets.get("msg"), 'r')
            print c('#' * 50, 'y')
            sys.exit(1)

        nfail = 0
        for ret in rets:
            if not ret[2]:
                nfail += 1

        if not self.options.is_raw:
            format_ret = enumerate(
                [u"%s %s : %s" % (u"[%s]" % c(ret[0], 'y'), c(ret[1], 'b'), color(format_obj(ret[2]))) for ret in rets])
        else:
            format_ret = enumerate(
                [u"%s %s : %s" % (u"[%s]" % ret[0], ret[1], ret[2]) for ret in rets])
        print c('#' * 50, 'y')

        for index, item in format_ret:
            print item.encode("utf-8")

        print c('#' * 50, 'y')

        if locals().get('index') >= 0:
            index += 1
        else:
            index = 0
        print "一共执行了[%s]个，失败了[%s]" % (color(index), color(nfail, 0))


class SwallManage(ManageParser):
    def main(self):
        self.parse_args()

        if not sys.argv[2:]:
            self.print_help()
            sys.exit(1)
        cmd = sys.argv[2]
        self._sub_commands(cmd)

    def _sub_commands(self, cmd):
        if cmd == "init":
            init = ZKInit()
            init.main()
        elif cmd == "info":
            self._show_info()
        else:
            self.print_help()

    def _show_info(self):
        """
        显示swall信息
        """
        keeper = Keeper(self.config)
        valid_nodes = keeper.get_valid_nodes()
        info = {
            "config": self.config,
            "node_list": valid_nodes
        }
        print format_obj(info)


class SwallAgent(ServerParser):
    """
    swall进程管理
    """

    def main(self):
        self.parse_args()
        if self.args[1:]:
            action = self.args[1]
        else:
            self.print_help()
            sys.exit(1)
        cmds = {
            "start": self.start,
            "stop": self.stop,
            "restart": self.restart,
            "status": self.status
        }
        func = cmds.get(action)
        if func:
            func()
        else:
            self.print_help()
            sys.exit(1)

    def status(self):
        """
        show status
        """
        try:
            pid = open(self.config["swall"]["pidfile"], 'r').read()
            message = c("swall is running[%s]...\n" % pid, 'g')
        except IOError:
            message = c("swall is not running!\n", 'r')
        sys.stdout.write(message)
        sys.stdout.flush()

    def stop(self):
        """
        stop server
        """
        kill_daemon(self.config["swall"]["pidfile"])

    def start(self):
        """
        restart server
        """
        self.daemonize_if_required()
        try:
            sagent = Agent(self.config)
            self.set_pidfile()
            sagent.loop()
        except KeyboardInterrupt:
            print "Stopping the Swall Agent"
            self.stop()
            logging.getLogger().warn()

    def restart(self):
        self.stop()
        self.start()


class ZKInit(InitParser, ConfMin):
    __metaclass__ = OptionParserMeta

    def main(self):
        """
        init zookeeper
        """
        self.parse_args()
        keeper = Keeper(self.config)
        if keeper.init_db(self.options.force):
            sys.stdout.write(c("init zookeeper db ok\n", 'g'))
        else:
            sys.stdout.write(c("init zookeeper db fail\n", 'r'))
        sys.stdout.flush()


class Swall(MainParser):
    def main(self):
        """
        get args for commands
        """
        if not sys.argv[1:]:
            self.print_help()
            sys.exit(1)
        cmd = sys.argv[1]
        self._sub_commands(cmd)

    def _sub_commands(self, cmd):
        if cmd == "server":
            agent = SwallAgent()
            agent.main()
        elif cmd == "manage":
            manger = SwallManage()
            manger.main()
        elif cmd == "ctl":
            ctl = Ctl()
            ctl.main()
        else:
            self.print_help()


