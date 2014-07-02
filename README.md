一、概述
============

swall是一个基于zookeeper实现的分布式基础信息管理系统（Infrastructure Management）可以用于管理特别是架构比较灵活的服务，比如游戏。用swall，
你不用登陆到具体的服务器去操作，你指需要在一台机器上面就可以完成服务管理，比如获取服务器监控信息、执行shell命令等等，你还可以方便的实现自动化配置，一条命令实现所有应用的部署不再是难题。


二、Swall原理
==============

swall原理很简单，用过zookeeper的人都知道，zookeeper比较擅长存储敏感的状态信息，并提供一系列机制来操作这些信息，swall主要利用的是zookeeper
的watcher功能，就是当某个数据变化的时候会提供一个机制来实现通知，那么swall主要架构很简单了：
![image](https://raw.githubusercontent.com/lufeng4828/swall_doc/master/swall-arch.png)


三、安装zookeeper集群
=========================

1.下载 [jdk-7u55-linux-x64](http://www.oracle.com/technetwork/java/javase/downloads/jdk7-downloads-1880260.html)

2.上传jdk-7u55-linux-x64.gz到服务器，解压

    [root@zookeeper1 ~]# tar xf jdk-7u55-linux-x64.gz -C /usr/local/
    [root@zookeeper1 ~]# ls /usr/local/
    /usr/local/jdk1.7.0_55
    [root@zookeeper1 ~]# mv /usr/local/jdk1.7.0_55 /usr/local/java
    [root@zookeeper1 ~]#

3.配置jdk环境

    [root@zookeeper1 ~]# cat >> /etc/bashrc <<\eof
    > export JAVA_HOME=/usr/local/java
    > export CLASSPATH=.:$JAVA_HOME/lib/dt.jar:$JAVA_HOME/lib/tools.jar
    > export PATH=$PATH:$JAVA_HOME/bin
    > eof
    [root@zookeeper1 ~]# source /etc/bashrc

4.检查java是否安装成功

    [root@zookeeper1 ~]# java -version
    java version "1.7.0_55"
    Java(TM) SE Runtime Environment (build 1.7.0_55-b13)
    Java HotSpot(TM) 64-Bit Server VM (build 24.55-b03, mixed mode)


5.下载 [zookeeper-3.4.5-cdh5.0.0](http://archive.cloudera.com/cdh5/cdh/5/zookeeper-3.4.5-cdh5.0.0.tar.gz)

6.上传zookeeper-3.4.5-cdh5.0.0.tar.gz到服务器，解压

    [root@zookeeper1 ~]# tar xf zookeeper-3.4.5-cdh5.0.0.tar.gz -C /usr/local/
    [root@zookeeper1 ~]# ls -d /usr/local/zookeeper-3.4.5-cdh5.0.0
    /usr/local/zookeeper-3.4.5-cdh5.0.0
    [root@zookeeper1 ~]# mv /usr/local/zookeeper-3.4.5-cdh5.0.0 /usr/local/zookeeper

7.配置zookeeper，这里配置的是单节点（最好配置成多节点）

    [root@zookeeper1 ~]# cd /usr/local/zookeeper/conf/
    [root@zookeeper1 conf]# mv zoo_sample.cfg zoo.cfg
    [root@zookeeper1 conf]# vim zoo.cfg #修改dataDir=/data/database/zookeeper
    [root@zookeeper1 conf]# mkdir -p /data/database/zookeeper
    [root@zookeeper1 conf]# cd ..
    [root@zookeeper1 zookeeper]# cd bin/
    [root@zookeeper1 bin]# ./zkServer.sh start
    JMX enabled by default
    Using config: /usr/local/zookeeper/bin/../conf/zoo.cfg
    Starting zookeeper ... STARTED
    [root@zookeeper1 bin]# ./zkServer.sh status
    JMX enabled by default
    Using config: /usr/local/zookeeper/bin/../conf/zoo.cfg
    Mode: standalone #说明配置成功
    [root@zookeeper1 bin]#

8.配置防火墙，允许访问2181端口（这里以INPUT规则为例）

    [root@zookeeper1 bin]# iptables -A INPUT -p tcp --dport 2181 -j ACCEPT
    [root@zookeeper1 bin]# iptables -L -n | grep 2181
    ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0           tcp dpt:2181
    [root@zookeeper1 bin]# iptables-save > /etc/sysconfig/iptables
    [root@zookeeper1 bin]# echo ruok | nc localhost 2181
    imok #说明zookeeper安装成功
    [root@zookeeper1 bin]# 


四、安装swall
=========================

1.下载最新版本swall

    [root@swall1 ~]# mkdir /data
    [root@swall1 ~]# cd /data
    [root@swall1 data]# git clone https://github.com/lufeng4828/swall.git

2.安装swall的依赖包，建议用pip安装
    
    [root@swall1 ~]# cd swall
    [root@swall1 swall]# pip install -r requirememts.txt 
    
3.修改swall配置

    [root@swall1 swall]# cd conf
    [root@swall1 conf]# vim swall.conf
    [main]
    #定义角色，多个角色用逗号分开
    node_role = server
    #agent地址，根据具体情况
    node_ip = 192.168.4.180
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
    （1）node_role是定义agent角色的，一个角色对应module下面的目录的模块，多个角色用逗号分隔
    （2）路径如果不是绝对路径，以程序根路径为基础，例如程序路径是/data/swall，则fs_plugin为/data/swall/plugins/fservice
    （3）node_ip是当前agent的ip地址
    （4）如果日志文件不存在，程序日志是记录不了，需要手动生成
    
    [root@swall1 conf]# vim zk.conf
    [main]
    #zookeepr地址，支持多个，通过逗号分隔
    zk_servers = 192.168.4.181:2181
    #zookeeper权限管理方式
    zk_scheme = digest
    zk_auth = vcode:swall!@#
    #相关目录path
    root=/swall
    nodes=%(root)s/nodes
    
    说明：
    （1）zk_servers是zookeeper地址，格式是host1:port1,host2:port2,..,hostN:portN
    （2）zk_scheme是指定zookeeper的权限管理方式，目前支持digest
    （3）zk_auth是zk_scheme对应的id格式为：username:BASE64(SHA1(password))

    [root@swall1 conf]# vim fs.conf
    [main]
    fs_type = rsync
    fs_host = 192.168.4.181
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
    
    [root@swall1 conf]# vim roles.d/server.conf
    [main]
    project = vcode
    agent = sw
    node_name = %(project)s_%(agent)s_server_172.17.0.4
    
    说明：
    （1）如果node_name不是@@格式的，一定要为角色指定project标识，因为公司里面可以有很多项目，这个用来处理多项目的环境
    （2）agent可以认为是二级项目标识，作用和project一样，如果node_name不是@@格式的，就一定要为你的角色指定一个二级标识
    （3）自定该角色节点名列表，可以写死，多个节点名通过逗号分隔，如：vcode_swc_1,vcode_swc_2，也可以通过模块自动生成
         节点名列表，通过加@@标识，如：@@gen.game，意思是调用gen.py的game函数生成，gen.py要放在module/common下面

4.文件传输以rsync为例，配置rsync，一定要192.168.4.181的rsync服务已经正确运行了，
下面给出配置rsync过程，这里我们把rsync也配置到192.168.4.181

    [root@zookeeper1 ~]# useradd swall
    [root@zookeeper1 ~]# mkdir /data/swall_fs
    [root@zookeeper1 ~]# chown -R swall:swall /data/swall_fs
    [root@zookeeper1 ~]# vim /etc/rsyncd.conf


（1）rsync配置如下

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

（2）设置rsync密码

    [root@zookeeper1 ~]# echo 'swall:vGjeVUncnbPV8CcZ' > /etc/rsyncd.secrets
    [root@zookeeper1 ~]# chmod 600 /etc/rsyncd.secrets


（3）防火墙要允许访问61768端口

    [root@zookeeper1 bin]# iptables -A INPUT -p tcp --dport 61768 -j ACCEPT
    [root@zookeeper1 bin]# iptables -L -n | grep 61768
    ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0           tcp dpt:61768
    [root@zookeeper1 bin]# iptables-save > /etc/sysconfig/iptables

（4）运行rsync

    [root@zookeeper1 bin]# rsync --port=61768 --config=/etc/rsyncd.conf --daemon


（5）测试rsync是否正常服务,登录其他机器，这里以192.168.4.180为例

    [root@swall1 ~]# RSYNC_PASSWORD=vGjeVUncnbPV8CcZ rsync -a --port=61768 --partial /etc/services swall@192.168.4.181::swall_fs/service
    [root@swall1 ~]# echo $?
    0
    [root@swall1 ~]# RSYNC_PASSWORD=vGjeVUncnbPV8CcZ rsync -a --port=61768 --partial swall@192.168.4.181::swall_fs/service /tmp/service
    [root@swall1 ~]# ll /tmp/service
    -rw-r--r-- 1 root root 640999 Jan 12  2010 /tmp/service

如上，说明rsync配置成功。

5.在启动swall之前，下面给出一个完整配置示例

    ###swall.conf配置
    [main]
    node_role = game,server
    node_ip = 192.168.8.180
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
    fs_host = 192.168.4.181
    fs_port = 61768
    fs_user = swall
    fs_pass = vGjeVUncnbPV8CcZ
    fs_tmp_dir = /data/swall_fs
    fs_failtry = 3

    ###zk.conf配置
    [main]
    zk_servers = 192.168.4.181:2181
    zk_scheme = digest
    zk_auth = vcode:swall!@#
    root=/swall
    nodes=%(root)s/nodes

    ###roles.d/server.conf角色配置
    [main]
    project = swall
    agent = sa
    node_name = %(project)s_%(agent)s_server_192.168.8.180

    ###roles.d/game.conf配置
    [main]
    node_name = @@gen.game


6.新增PATH和PYTHONPATH路径

    [root@swall1 ~]# export PATH=/data/swall/bin:$PATH
    [root@swall1 ~]# export PYTHONPATH=/data/swall:$PYTHONPATH
    [root@swall1 ~]# #备注：最好把着两个环境变量写入配置文件

7.第一次配置swall集群下初始化zookeeper目录

    [root@swall1 ~]# cd /data/swall/bin
    [root@swall1 bin]# ./swall manage init

8.启动swall节点程序

    [root@swall1 ~]# cd /data/swall/bin
    [root@swall1 bin]# ./swall server start

9.测试命令

    [root@swall1 bin]# swall ctl server "*"  sys.ping
    ####################
    [server] xyz_sa_server_192.168.8.180 : 1
    ####################
    一共执行了[1]个
    
    
五、swall简单用法
====================

1.swall的管理工具是bin/swall, 使用方法如下

    Usage: /data/swall/bin/swall ctl  <role> [target] <module.function> [arguments]

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

    role：指的是在swall.conf的node_role配置角色，只有配置了对应的role才能接收到命令
    target：通配符或者正则，通配符只支持*号，用来匹配具体的节点，主要去匹配swall.conf的node_name
    module.function：要执行的函数，例如sys.ping，有内置函数和自定义函数
    arguments：传递到module.function中的参数，支持位置参数和关键字参数

3.选项解释

    --exclude：     需要从target刷选的列表中排除，支持通配符和正则
    --timeout：     设置超时
    --is_raw:       打印结果需要显示颜色
    --nthread：     需要多少个线程去执行任务，如果为1，代表一个swall接收到的任务只会在一个线程中执行
    --config_dir：  指定swall配置文件，否则使用默认的配置/data/swall/conf

4.下面演示一些功能函数的使用

（1）查看swall通讯是否正常:

    [root@swall1 ~]# swall ctl server "*"  sys.ping --timeout=10
    ####################
    [server] xyz_sa_server_192.168.8.190 : 1
    [server] xyz_sa_server_192.168.8.191 : 1
    [server] xyz_sa_server_192.168.8.195 : 1
    [server] xyz_sa_server_192.168.8.198 : 1
    [server] xyz_sa_server_192.168.8.203 : 1
    [server] xyz_sa_server_192.168.8.180 : 1
    ####################
    一共执行了[6]个

    
（2）拷贝文件到远程:

    [root@swall1 ~]# swall ctl server "*"  sys.copy /etc/hosts /tmp/xx_hosts --timeout=10
    ####################
    [server] xyz_sa_server_192.168.8.190 : 1
    [server] xyz_sa_server_192.168.8.191 : 1
    [server] xyz_sa_server_192.168.8.195 : 1
    [server] xyz_sa_server_192.168.8.198 : 1
    [server] xyz_sa_server_192.168.8.203 : 1
    [server] xyz_sa_server_192.168.8.180 : 1
    ####################
    一共执行了[6]个
    [root@swall1 ~]# swall ctl server "*"  sys.copy /etc/hosts /tmp/xx_hosts ret_type=full --timeout=10
    ####################
    [server] xyz_sa_server_192.168.8.190 : /tmp/xx_hosts
    [server] xyz_sa_server_192.168.8.191 : /tmp/xx_hosts
    [server] xyz_sa_server_192.168.8.195 : /tmp/xx_hosts
    [server] xyz_sa_server_192.168.8.198 : /tmp/xx_hosts
    [server] xyz_sa_server_192.168.8.203 : /tmp/xx_hosts
    [server] xyz_sa_server_192.168.8.180 : /tmp/xx_hosts
    ####################
    一共执行了[6]个
    [root@swall1 ~]#

（3）从远程拷贝文件到当前:

    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  sys.get /etc/services /tmp/xxx_service
    ####################
    [server] xyz_sa_server_192.168.8.190 : /tmp/xxx_service
    ####################
    一共执行了[1]个
    [root@swall1 ~]#


（4）执行shell命令:

    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  cmd.call 'df -h | grep data'
    ####################
    [server] xyz_sa_server_192.168.8.190 : {'pid': 5329, 'retcode': 0, 'stderr': None, 'stdout': '/dev/sda5              73G   15G   55G  21% /data'}
    ####################

    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  cmd.call 'df -h | grep data' ret_type=stdout
    ####################
    [server] xyz_sa_server_192.168.8.190 : /dev/sda5              73G   15G   55G  21% /data
    ####################
    一共执行了[1]个
    [root@swall1 ~]#

六、一些问题
===================
1.怎么添加节点到集群呢？
> 答：只要配置zk.conf好了，启动swall以后会自动添到集群

2.调用模块的时候如果不知道怎么使用模块，不知道传什么参数，怎么办？
> 答：每个函数后面加上 help参数都会打印这个函数使用说明
> > 
    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  sys.copy help
    ####################
    [server] xyz_sa_server_192.168.8.190 :
        def copy(*args, **kwargs) -> 拷贝文件到远程 可以增加一个ret_type=full，支持返回文件名
        @param args list:支持位置参数，例如 sys.copy /etc/src.tar.gz /tmp/src.tar.gz ret_type=full
        @param kwargs dict:支持关键字参数，例如sys.copy local_path=/etc/src.tar.gz remote_path=/tmp/src.tar.gz
        @return int:1 if success else 0
    ####################
    一共执行了[1]个
        
3.需要查看摸个模块的函数列表，怎么办？
> 答：提供了一个sys.funcs函数可以解决这个问题，需要输入想要查看的模块名称（不带后缀）
> > 
    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  sys.funcs sys
    ####################
    [server] xyz_sa_server_192.168.8.190 : ('sys.rsync_module', 'sys.get', 'sys.job_info', 'sys.exprs', 'sys.copy', 'sys.ping', 'sys.reload_env', 'sys.funcs', 'sys.roles', 'sys.reload_node', 'sys.reload_module')
    ####################
    一共执行了[1]个
    [root@swall1 ~]#
        
4.写好了模块以后要怎么同步到节点呢？

> 答：通过调用sys.rsync_module可以同步模块到节点
> > 如果写好了模块并且存放如当前节点的/module/{role}，这里的{role}对应你要同步的角色，/module/common是所有角色公用的模块，现在为server同步模块如下:

> >  
    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  sys.rsync_module
    ####################
    [server] xyz_sa_server_192.168.8.190 : 1
    ####################
    一共执行了[1]个
    
> > 支持同步个别模块，多个需要用逗号分隔：
> > 
    [root@swall1 ~]# swall ctl server "xyz_sa_server_192.168.8.190"  sys.rsync_module server_tools.py
    ####################
    [server] xyz_sa_server_192.168.8.190 : 1
    ####################
    一共执行了[1]个
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
    
七、更多详细文档和案例
============

更多详细和高级用法请参考：http://swall.readthedocs.org/en/latest/index.html




