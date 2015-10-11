一、Swall概述
============

swall升级以后用比较简单的redis替换zookeeper，swall是一个可以用于管理特别是架构比较灵活的服务，比如游戏。用swall，
你不用登陆到具体的服务器去操作，你指需要在一台机器上面就可以完成服务管理，比如获取服务器监控信息、执行shell命令等等，你还可以方便的实现自动化配置，一条命令实现所有应用的部署不再是难题。

特点：

    1.使用redis做任务信息存储，性能可靠
    3.简单灵活，五脏六腑俱全（文件拷贝、命令执行、模块管理）
    4.提供比较好的自省功能，可以让你比较方便调用各种模块
    5.容易扩展



二、Swall安装部署
==================

 准备两台机器，相关信息如下：

    ===========================================
    名称	             配置          IP地址
    -------------------------------------------
    redis1	         centos6.2	  192.168.0.181
    swall1	         centos6.2	  192.168.0.180


（一）安装redis
----------------------
    安装redis请自行google或者百度，这里我就不写了


（二）安装rsync服务
-------------------------

swall内部提供了一个组件的方式来实现文件传输，内部已经实现了三个组件：ssh、ftp、rsync，这几个组件按照swall约定实现了访问对应文件
服务器的api，对应的配置是fs.conf，组件具体功能是为swall提供一个存放和下载文件的临时场所，下面以rsync为例：

rsync配置在192.168.0.181，和zookeeper配置在一起，实际用的时候最好要部署到不同的机器上

1.添加rsync用户和目录

    [root@redis1 ~]# useradd swall
    [root@redis1 ~]# mkdir /data/swall_fs
    [root@redis1 ~]# chown -R swall:swall /data/swall_fs
    [root@redis1 ~]# vim /etc/rsyncd.conf


2.设置rsync配置

    secrets file = /etc/rsyncd.secrets
    list = no
    port = 61768
    read only = yes
    uid = swall
    gid = swall
    max connections = 3000
    log file = /var/log/rsyncd_swall.log
    pid file = /var/run/rsyncd_swall.pid
    lock file = /var/run/rsync_swall.lock

    [swall_fs]
    path = /data/swall_fs
    auth users = swall
    read only = no

3.设置rsync密码

    [root@redis1 ~]# echo 'swall:vGjeVUncnbPV8CcZ' > /etc/rsyncd.secrets
    [root@redis1 ~]# chmod 600 /etc/rsyncd.secrets


4.防火墙要允许访问61768端口

    [root@redis1 bin]# iptables -A INPUT -p tcp --dport 61768 -j ACCEPT
    [root@redis1 bin]# iptables -L -n | grep 61768
    ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0           tcp dpt:61768
    [root@redis1 bin]# iptables-save > /etc/sysconfig/iptables

5.运行rsync服务

    [root@redis1 bin]# rsync --port=61768 --config=/etc/rsyncd.conf --daemon


6.测试rsync是否正常服务,登录其他机器，这里以192.168.0.180为例

    [root@swall1 ~]# RSYNC_PASSWORD=vGjeVUncnbPV8CcZ rsync -a --port=61768 --partial /etc/services swall@192.168.0.181::swall_fs/service
    [root@swall1 ~]# echo $?
    0
    [root@swall1 ~]# RSYNC_PASSWORD=vGjeVUncnbPV8CcZ rsync -a --port=61768 --partial swall@192.168.0.181::swall_fs/service /tmp/service
    [root@swall1 ~]# ll /tmp/service
    -rw-r--r-- 1 root root 640999 Jan 12  2010 /tmp/service

如上，说明rsync配置成功。


（三）安装Swall
-------------------

Swall这里安装到192.168.0.180服务器上

1.下载最新版本swall

    [root@swall1 ~]# mkdir /data
    [root@swall1 ~]# cd /data
    [root@swall1 data]# git clone https://github.com/lufeng4828/swall.git

2.安装swall的依赖包，建议用pip安装
    
    [root@swall1 ~]# cd swall
    [root@swall1 swall]# pip install -r requirememts.txt
    注意：如果还没有装pip，centos可以通过yum install python-pip，ubuntu可以通过 apt-get install python-pip安装
    
3.修改swall配置

    [root@swall1 swall]# cd conf
    [root@swall1 conf]# vim swall.conf
    [main]
    #以此用户运行swall
    user = swall
    #定义角色，多个角色用逗号分开
    node_name = swall01 #这里我们只定义节点名称
    #agent地址，根据具体情况
    node_ip = 192.168.0.180 #这里写上当前服务器ip 192.168.0.180
    #缓存路径
    cache = var/cache
    #模块路径
    module = module/
    #文件备份路径
    backup = var/backup
    #plugins路径
    fs_plugin = plugins/fservice
    #pid文件
    pidfile = /tmp/.swall.pid
    #日志定义
    log_file = logs/swall.log
    log_level = INFO
    #认证key，数据传输用
    token = yhIC7oenuJDpBxqyP3GSHn7mgQThRHtOnNNwqpJnyPVhR1n9Y9Q+/T3PJfjYCZdiGRrX03CM+VI=
    
    说明：
    （1）node_name是定义agent名称
    （2）路径如果不是绝对路径，以程序根路径为基础，例如程序路径是/data/swall，则fs_plugin为/data/swall/plugins/fservice
    （3）node_ip是当前agent的ip地址
    （4）如果日志文件不存在，程序日志是记录不了，需要手动生成

    [root@swall1 conf]# vim fs.conf
    [main]
    fs_type = rsync #选择rsync
    fs_host = 192.168.0.181 #这里写我们部署好rsync的服务器地址192.168.0.181
    fs_port = 61768
    fs_user = swall
    fs_pass = vGjeVUncnbPV8CcZ
    fs_tmp_dir = /data/swall_fs
    fs_failtry = 3
    
    说明：
    （1）fs_type是指/data/swall/plugins/fservice下面的文件名（不带路径），目前只支持ssh、ftp、rsync，可以自己实现
    （2）fs_tmp_dir只有ssh组件使用到，，ftp和rsync用不到
    （3）fs_failtry只有rsync用到，当rsync传输失败了可以重试多少次
    （4）传输组件是用来给swall上传和下载文件来实现文件传输功能的


4.在启动swall之前，下面给出一个完整配置示例

    ###swall.conf配置
    [main]
    user = swall
    node_name = server
    node_ip = swall01
    cache = var/cache
    module = module/
    backup = var/backup
    fs_plugin = plugins/fservice
    pidfile = /tmp/.swall.pid
    log_file = /data/logs/swall.log
    log_level = INFO
    token = yhIC7oenuJDpBxqyP3GSHn7mgQThRHtOnNNwqpJnyPVhR1n9Y9Q+/T3PJfjYCZdiGRrX03CM+VI=

    ###fs.conf配置
    fs_type = rsync
    fs_host = 192.168.0.181
    fs_port = 61768
    fs_user = swall
    fs_pass = vGjeVUncnbPV8CcZ
    fs_tmp_dir = /data/swall_fs
    fs_failtry = 3


5.新增PATH和PYTHONPATH路径（PYTHONPATH一定要设置，否则程序运行会提示swall模块找不到的）

    [root@swall1 ~]# export PATH=/data/swall/bin:$PATH
    [root@swall1 ~]# export PYTHONPATH=/data/swall:$PYTHONPATH
    [root@swall1 ~]# #备注：最好把着两个环境变量写入配置文件

6.新建swall用户和设置文件权限

    [root@swall1 ~]# useradd swall
    [root@swall1 ~]# chown -R swall:swall /data/swall


7.启动swall节点程序

    [root@swall1 ~]# cd /data/swall/bin
    [root@swall1 bin]# ./swall server start

8.测试命令

    [root@swall1 bin]# swall ctl "*"  sys.ping
    ##################################################
    swall_sa_server_192.168.0.180 : 1
    ##################################################
    一共执行了[1]个，失败了[0]
    
    
三、Swall命令入门
====================

1.swall的管理工具是bin/swall, 使用方法如下

    Usage: swall ctl [target] <module.function> [arguments]

    Send command to swall server.

    Options:
    -h, --help            show this help message and exit

    Options for swall ctl:
    -e EXCLUDE, --exclude=EXCLUDE
                        Specify the exclude hosts by regix

    -t TIMEOUT, --timeout=TIMEOUT
                        Specify the timeout,the unit is second

    -r, --is_raw        Specify the raw output
    -n NTHREAD, --nthread=NTHREAD
                        Specify running nthread

    Options for conf_dir:
    -c CONFIG_DIR, --config_dir=CONFIG_DIR
                        Pass in an alternative configuration dir. Default: /data/swall/conf

2.参数解释

    target：通配符或者正则，通配符只支持*号，用来匹配具体的节点，主要去匹配swall.conf的node_name
    module.function：要执行的函数，例如sys.ping，有内置函数和自定义函数
    arguments：传递到module.function中的参数，支持位置参数和关键字参数

3.选项解释

    --exclude：     需要从target刷选的列表中排除，支持通配符和正则
    --timeout：     设置超时
    --is_raw:       打印结果需要显示颜色
    --config_dir：  指定swall配置文件，否则使用默认的配置/data/swall/conf

4.下面演示一些功能函数的使用，假设已经配置了N个节点了

（1）查看swall通讯是否正常:

    [root@swall1 ~]# swall ctl "*"  sys.ping --timeout=10
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    swall_sa_server_192.168.0.195 : 1
    swall_sa_server_192.168.0.198 : 1
    swall_sa_server_192.168.0.203 : 1
    swall_sa_server_192.168.0.180 : 1
    ##################################################
    一共执行了[6]个，失败了[0]

    
（2）拷贝文件到远程:

    [root@swall1 ~]# swall ctl "*"  sys.copy /etc/hosts /tmp/xx_hosts --timeout=10
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    swall_sa_server_192.168.0.195 : 1
    swall_sa_server_192.168.0.198 : 1
    swall_sa_server_192.168.0.203 : 1
    swall_sa_server_192.168.0.180 : 1
    ##################################################
    一共执行了[6]个，失败了[0]
    [root@swall1 ~]# swall ctl "*"  sys.copy /etc/hosts /tmp/xx_hosts ret_type=full --timeout=10
    ##################################################
    swall_sa_server_192.168.0.190 : /tmp/xx_hosts
    swall_sa_server_192.168.0.191 : /tmp/xx_hosts
    swall_sa_server_192.168.0.195 : /tmp/xx_hosts
    swall_sa_server_192.168.0.198 : /tmp/xx_hosts
    swall_sa_server_192.168.0.203 : /tmp/xx_hosts
    swall_sa_server_192.168.0.180 : /tmp/xx_hosts
    ##################################################
    一共执行了[6]个，失败了[0]
    [root@swall1 ~]#

（3）从远程拷贝文件到当前:

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.get /etc/services /tmp/xxx_service
    ##################################################
    swall_sa_server_192.168.0.190 : /tmp/xxx_service
    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 ~]#


（4）执行shell命令:

    [root@swall1 swall]# swall ctl "swall_sa_server_192.168.0.190"  cmd.call 'echo ok | awk "{print \$0}"'
    ##################################################
    swall_sa_server_192.168.0.190 :
    {
        "pid": 1149,
        "retcode": 0,
        "stderr": null,
        "stdout": "ok"
    }

    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 swall]#

    [root@agent2 swall]# swall ctl "swall_sa_server_192.168.0.190"  cmd.call 'echo ok | awk "{print \$0}"' ret_type=stdout
    ##################################################
    swall_sa_server_192.168.0.190 : ok
    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 swall]#


五、Swall命令进阶
=========================

1.如果你安装好了swall，可以从sys.funcs和help来一步一步了解swall，swall内置有很多基本功能，如查看agent存活，拷贝文件，同步模块，查看模块，查看swall参数宏变量等，
  同时在module部分也实现了很多功能模块：网络模块，linux信息查看、远程命令执行等，当然你可以自己实现，添加自己的模块很简单，后面再告诉怎么添加。

（1）查看内置功能

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.funcs sys
    ##################################################
    swall_sa_server_192.168.0.190 :
    [
        "sys.rsync_module",
        "sys.get_env",
        "sys.job_info",
        "sys.funcs",
        "sys.exprs",
        "sys.copy",
        "sys.ping",
        "sys.get",
        "sys.reload_env",
        "sys.roles",
        "sys.reload_node",
        "sys.reload_module",
        "sys.version"
    ]

    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 ~]#

（2）查看功能函数帮助，在调用函数后面直接加上help就可以了

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.copy help
    ##################################################
    swall_sa_server_192.168.0.190 :
        def copy(*args, **kwargs) -> 拷贝文件到远程 可以增加一个ret_type=full，支持返回文件名
        @param args list:支持位置参数，例如 sys.copy /etc/src.tar.gz /tmp/src.tar.gz ret_type=full
        @param kwargs dict:支持关键字参数，例如sys.copy local_path=/etc/src.tar.gz remote_path=/tmp/src.tar.gz
        @return int:1 if success else 0
    ##################################################
    一共执行了[1]个，失败了[0]

（3）同步模块到节点

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.rsync_module
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    ##################################################
    一共执行了[1]个

    支持同步个别模块，多个需要用逗号分隔

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.rsync_module server_tools.py
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 ~]#

2.swall提供一些内置变量，使用在参数中，在真正执行的时候会被替换，查看当前系统支持的“参数宏变量”

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.get_env
    ##################################################
    swall_sa_server_192.168.0.190 :
    [
        "NODE",
        "IP",
        "TIME",
        "DATE"
    ]

    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 bin]#

    使用的时候需要加大括号，如{IP}参数宏变量自定义，查看参数宏变量的具体值如下:

    [root@swall1 bin]# swall ctl "*"  sys.exprs "ip:{IP},node:{NODE}"
    ##################################################
    swall_sa_server_192.168.0.190 : ip:192.168.0.190,node:swall_sa_server_192.168.0.190
    swall_sa_server_192.168.0.191 : ip:192.168.0.191,node:swall_sa_server_192.168.0.191
    swall_sa_server_192.168.0.195 : ip:192.168.0.195,node:swall_sa_server_192.168.0.195
    swall_sa_server_192.168.0.198 : ip:192.168.0.198,node:swall_sa_server_192.168.0.198
    swall_sa_server_192.168.0.203 : ip:192.168.0.203,node:swall_sa_server_192.168.0.203
    swall_sa_server_192.168.0.180 : ip:192.168.0.180,node:swall_sa_server_192.168.0.180
    ##################################################
    一共执行了[6]个，失败了[0]
    [root@swall1 bin]#
    [root@swall1 bin]# swall ctl "*"  sys.copy /etc/services /data/{NODE}/ ret_type=full
    ##################################################
    swall_sa_600 : /data/swall_sa_600/services
    swall_sa_601 : /data/swall_sa_601/services
    swall_sa_700 : /data/swall_sa_700/services
    ##################################################
    一共执行了[3]个，失败了[0]
    [root@swall1 bin]#


六、Swall模块编写
===================

swall模块存放在module下面的特定目录中，module下面的目录就是swall里面的角色，说白了，角色就是一个含有特定模块文件的组，
你写的模块属于哪个角色就放到哪个目录下去，例如你写了一个server_tools.py，属于server角色，就放到当前你所在节点的
/data/swall/module/server目录下（角色可以随意创建，只要在/data/swall/module/创建一个目录存放模块即可）一个agent
可以配置多个角色，就是swall.conf中的node_role，配置好角色还要为角色配置节点（节点的概念在swall中代表node），下面开始编写模块。

1.swall模块最小单元是函数，目前不支持直接调用方法，函数需要加上node修饰器，同时最好要给函数设置doc帮助信息

    [root@swall1 server]# pwd
    /data/swall/module/server
    [root@swall1 server]# vim mem_info.py
    import psutil
    import logging
    from swall.utils import node

    log = logging.getLogger()

    @node
    def physical_memory_usage(*args, **kwarg):
        """
        def physical_memory_usage(*args, **kwarg) -> Return a dict that describes free and available physical memory.
        @return dict:
        """
        return dict(psutil.phymem_usage()._asdict())

2.编写好了以后需要同步出去，同步命令会自动加载模块

    [root@swall1 swall]# swall ctl "*" sys.rsync_module mem_info.py
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]

3.查看写好的模块

    [root@swall1 swall]# swall ctl "*" sys.funcs mem_info
    ##################################################
    swall_sa_server_192.168.0.190 : ['mem_info.physical_memory_usage']
    swall_sa_server_192.168.0.191 : ['mem_info.physical_memory_usage']
    ##################################################
    一共执行了[2]个，失败了[0]
    [root@swall1 swall]#

    [root@swall1 swall]# swall ctl "*" mem_info.physical_memory_usage help
    ##################################################
    swall_sa_server_192.168.0.190 :
        def physical_memory_usage(*args, **kwarg) -> Return a dict that describes free and available physical memory.
        @return dict:

    swall_sa_server_192.168.0.191 :
        def physical_memory_usage(*args, **kwarg) -> Return a dict that describes free and available physical memory.
        @return dict:

    ##################################################
    一共执行了[2]个，失败了[0]

4.调用执行我们的模块

    [root@swall1 swall]# swall ctl "*" mem_info.physical_memory_usage
    ##################################################
    swall_sa_server_192.168.0.190 :
    {
        "active": 417042432,
        "available": 57892864,
        "buffers": 5967872,
        "cached": 45473792,
        "free": 6451200,
        "inactive": 24846336,
        "percent": 88.700000000000003,
        "total": 514326528,
        "used": 507875328
    }

    swall_sa_server_192.168.0.191 :
    {
        "active": 417067008,
        "available": 57929728,
        "buffers": 5967872,
        "cached": 45518848,
        "free": 6443008,
        "inactive": 24940544,
        "percent": 88.700000000000003,
        "total": 514326528,
        "used": 507883520
    }

    ##################################################
    一共执行了[2]个，失败了[0]
    [root@swall1 swall]#


七、Swall参数宏变量
===================

swall支持在调用函数的时候，在参数（位置参数、关键字参数）里面加上宏变量，这些变量会在agent执行命令的时候扩展为具体的值，目前swall已经
支持如下几个参数宏变量：

    NODE：   node的名称
    IP：     node的ip地址
    TIME     node的当前时间
    DATE     node的当前日期


1.查看参数宏变量列表

    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.get_env
    ##################################################
    swall_sa_server_192.168.0.190 :
    [
        "NODE",
        "IP",
        "TIME",
        "DATE"
    ]

    ##################################################
    一共执行了[1]个，失败了[0]

2.查看具体参数宏变量的值

    [root@swall1 bin]# swall ctl "*"  sys.exprs "{NODE}"
    ##################################################
    swall_sa_server_192.168.0.190 : node:swall_sa_server_192.168.0.190
    swall_sa_server_192.168.0.191 : node:swall_sa_server_192.168.0.191
    swall_sa_server_192.168.0.195 : node:swall_sa_server_192.168.0.195
    swall_sa_server_192.168.0.198 : node:swall_sa_server_192.168.0.198
    swall_sa_server_192.168.0.203 : node:swall_sa_server_192.168.0.203
    swall_sa_server_192.168.0.180 : node:swall_sa_server_192.168.0.180
    ##################################################
    一共执行了[6]个，失败了[0]

    这里sys.exprs可以帮你打印节点的参数宏变量值，经常用来做参数宏变量查看的

3.在执行sys.copy的时候将当前/etc/hosts文件拷贝到server角色的所有节点的/tmp下面，同时加上拷贝的时间

    [root@swall1 swall]# swall ctl "*190*;*191*" sys.copy /etc/hosts /tmp/hosts.{DATE}_{TIME} ret_type=full
    ##################################################
    swall_sa_server_192.168.0.190 : /tmp/hosts.2014-07-03_07:36:17
    swall_sa_server_192.168.0.191 : /tmp/hosts.2014-07-03_07:36:17
    ##################################################
    一共执行了[2]个，失败了[0]
    [root@swall1 swall]#

4.新增参数宏变量

    （1）编辑module/common/_sys_common.py文件，直接在里面参考其他参数宏变量添加，然后通过下面的命令同步
    [root@swall1 swall]# swall ctl "*" sys.rsync_module _sys_common.py
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]

    （2）由于同步模块不会自动加载参数宏变量，需要手动加载
    [root@swall1 swall]# swall ctl "*" sys.reload_env
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]
    [root@swall1 swall]#


八、一些问题
===================

1.怎么匹配节点？
> 答：swall支持通过通配符（*）和正则表达式匹配节点，如：
> >
    （1）通配符，只支持星号，功能和linux shell环境下面的功能是一样的，如果有多个通配符，支持通过分号分隔
> >
    [root@swall1 swall]# swall ctl "swall_sa_server*" sys.ping
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]
    [root@swall1 swall]#
    [root@swall1 swall]# swall ctl "*190;*191" sys.ping
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]
> >
    （2）正则表达式
    [root@swall1 swall]# swall ctl "swall_sa_server_192.168.0.\d+" sys.ping
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    swall_sa_server_192.168.0.191 : 1
    ##################################################
    一共执行了[2]个，失败了[0]
> >
    （3）写完整的节点名称，如果有多个，支持分号分隔
    [root@swall1 swall]# swall ctl "swall_sa_server_192.168.0.190" sys.ping
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    ##################################################
    一共执行了[1]个，失败了[0]

2.调用模块的时候如果不知道怎么使用模块，不知道传什么参数，怎么办？
> 答：每个函数后面加上 help参数都会打印这个函数使用说明
> > 
    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.copy help
    ##################################################
    swall_sa_server_192.168.0.190 :
        def copy(*args, **kwargs) -> 拷贝文件到远程 可以增加一个ret_type=full，支持返回文件名
        @param args list:支持位置参数，例如 sys.copy /etc/src.tar.gz /tmp/src.tar.gz ret_type=full
        @param kwargs dict:支持关键字参数，例如sys.copy local_path=/etc/src.tar.gz remote_path=/tmp/src.tar.gz
        @return int:1 if success else 0
    ##################################################
    一共执行了[1]个，失败了[0]
        
3.需要查看摸个模块的函数列表，怎么办？
> 答：提供了一个sys.funcs函数可以解决这个问题，需要输入想要查看的模块名称（不带后缀）
> > 
    [root@swall1 swall]# swall ctl "swall_sa_server_192.168.0.190"  sys.funcs network
    ##################################################
    swall_sa_server_192.168.0.190 : ['network.get_ip', 'network.get_ping']
    [root@swall1 ~]#
        
4.写好了模块以后要怎么同步到节点呢？

> 答：通过调用sys.rsync_module可以同步模块到节点
> > 如果写好了模块并且存放如当前节点的/module/{role}，这里的{role}对应你要同步的角色，/module/common是所有角色公用的模块，现在为server同步模块如下:

> >  
    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.rsync_module
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    ##################################################
    一共执行了[1]个，失败了[0]
    
> > 支持同步个别模块，多个需要用逗号分隔：
> > 
    [root@swall1 ~]# swall ctl "swall_sa_server_192.168.0.190"  sys.rsync_module server_tools.py
    ##################################################
    swall_sa_server_192.168.0.190 : 1
    ##################################################
    一共执行了[1]个，失败了[0]
    [root@swall1 ~]#


5.如何编写模块？

> 答：模块编写如下所示：
> > 
> > 
    #coding:utf-8
    from swall.utils import node
> >   
    @node
    def ping(*args, **kwargs):
        return 1

> > 说明：
    所有模块需要加上node修饰器才可以让swall调用，函数一定要加上kwargs这个关键字扩展参数，swall内部会传一些信息过来，这些
    信息有:project，agent、role、node_name、node_ip
    在函数里面可以通过kwargs["project"]等获取这些信息
    
> > 写好模块以后保存，例如ping.py，存放到module下对应的角色目录中，通过命令同步到agent，归属于这个角色节点就可以调用该
> > 函数

6.什么场景下使用参数宏变量呢？

> 答：例如其他节点获取配置的时候，一般情况下，如果你不加参数宏变量，获取到当前节点的文件是同一个路径，你根本区分不出来，如下:
> >
    [root@swall1 bin]# swall ctl "*"  sys.get /etc/hosts /tmp/
    ##################################################
    swall_sa_server_192.168.0.190 : /etc/hosts
    swall_sa_server_192.168.0.191 : /etc/hosts
    swall_sa_server_192.168.0.195 : /etc/hosts
    swall_sa_server_192.168.0.198 : /etc/hosts
    swall_sa_server_192.168.0.203 : /etc/hosts
    swall_sa_server_192.168.0.205 : /etc/hosts
    ##################################################
    一共执行了[6]个，失败了[0]
    [root@swall1 bin]#

> > 这里就有一个问题了，所有获取的文件路径都是/etc/hosts，区分不出是那个节点的文件，如果使用参数宏变量，就不一样了:
> >
    [root@swall1 bin]# swall ctl "*"  sys.get /etc/hosts /tmp/hosts.{node}
    ##################################################
    swall_sa_server_192.168.0.190 : /tmp/hosts.swall_sa_server_192.168.0.190
    swall_sa_server_192.168.0.191 : /tmp/hosts.swall_sa_server_192.168.0.191
    swall_sa_server_192.168.0.195 : /tmp/hosts.swall_sa_server_192.168.0.195
    swall_sa_server_192.168.0.198 : /tmp/hosts.swall_sa_server_192.168.0.198
    swall_sa_server_192.168.0.203 : /tmp/hosts.swall_sa_server_192.168.0.203
    swall_sa_server_192.168.0.205 : /tmp/hosts.swall_sa_server_192.168.0.205
    ##################################################
    一共执行了[6]个，失败了[0]
    [root@swall1 bin]#


> > 还有一种场景，在游戏运维中，针对一机多服，假设游戏有/data/swall_sa_600,/data/swall_sa_601,/data/swall_sa_700三个程序，
    对应三个game的节点，节点名称就是目录名。如果我要拷贝文件到/data/swall_sa_600,/data/swall_sa_601,/data/swall_sa_700各个目录下，用swall的参数宏变量替换就很容易解决:
> >
    [root@swall1 bin]# swall ctl "*"  sys.copy /etc/services /data/{node}/ ret_type=full
    ##################################################
    swall_sa_600 : /data/swall_sa_600/services
    swall_sa_601 : /data/swall_sa_601/services
    swall_sa_700 : /data/swall_sa_700/services
    ##################################################
    一共执行了[3]个，失败了[0]
    [root@swall1 bin]#

7.怎么找不到sys.py文件？
> 答：swall模块分有两大类，一类是内置的，sys开头，这些模块在agent.py里面实现了，其他模块都可以在module目录下找到




