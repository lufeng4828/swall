概述
============

swall是一个基于zookeeper实现的分布式基础信息管理系统（Infrastructure Management）可以用于管理特别是架构比较灵活的服务，比如游戏。用swall，你不用登陆到具体的服务器去操作，你指需要在一台机器上面就可以完成服务管理，比如获取服务器监控信息、执行shell命令等等，你还可以方便的实现自动化配置，一条命令实现所有应用的部署不再是难题。


安装jdk和配置java环境
------------------------


下载[jdk-7u55-linux-x64](http://www.oracle.com/technetwork/java/javase/downloads/jdk7-downloads-1880260.html)

上传jdk-7u55-linux-x64.gz到服务器，解压::

    [root@zookeeper1 ~]# tar xf jdk-7u55-linux-x64.gz -C /usr/local/
    [root@zookeeper1 ~]# ls /usr/local/
    /usr/local/jdk1.7.0_55
    [root@zookeeper1 ~]# mv /usr/local/jdk1.7.0_55 /usr/local/java
    [root@zookeeper1 ~]#

配置jdk环境::

    [root@zookeeper1 ~]# cat >> /etc/bashrc <<\eof
    > export JAVA_HOME=/usr/local/java
    > export CLASSPATH=.:$JAVA_HOME/lib/dt.jar:$JAVA_HOME/lib/tools.jar
    > export PATH=$PATH:$JAVA_HOME/bin
    > eof
    [root@zookeeper1 ~]# source /etc/bashrc

检查java是否安装成功::

    [root@zookeeper1 ~]# java -version
    java version "1.7.0_55"
    Java(TM) SE Runtime Environment (build 1.7.0_55-b13)
    Java HotSpot(TM) 64-Bit Server VM (build 24.55-b03, mixed mode)

详细文档
============

http://swall.readthedocs.org/en/latest/index.html




