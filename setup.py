#!/usr/bin/env python
#coding:utf-8
__author__ = 'lufeng118@outlook.com'

import os
from setuptools import setup, Extension
from distutils.command.build import build
from subprocess import call
from multiprocessing import cpu_count

BASEPATH = os.path.dirname(os.path.abspath(__file__))
ZK_PATH = os.path.join(BASEPATH, 'c')


class BuildZKlib(build):
    def run(self):
        build.run(self)
        print "xxxxxxxxxxxxxxxxxxx"
        build_path = os.path.abspath(self.build_temp)
        print build_path
        cmd = [
            'make',
            'install'
        ]
        try:
            cmd.append('-j%d' % cpu_count())
        except NotImplementedError:
            print 'Unable to determine number of CPUs. Using single threaded make.'

        def compile():
            print '*' * 80
            call(cmd, cwd=ZK_PATH)
            print '*' * 80

        self.execute(compile, [], 'compiling zklib')


zookeepermodule = Extension("swall_pyzk",
                            sources=["zookeeper.c"],
                            include_dirs=["/usr/include/c-client-src", "/usr/local/include/c-client-src",
                                          "/usr/include/zookeeper", "/usr/local/include/zookeeper"],
                            libraries=["zookeeper_mt"],
)

setup(
    name='swall_pyzk',
    version='0.4.6',
    description='swall_pyzk is a pylib of zookeeper for swall',
    maintainer='lufeng4828',
    maintainer_email='lufeng118@outlook.com',
    license='GPLv2',
    url='http://www.vcode.org/',
    cmdclass={
        'build': BuildZKlib,
    },
    ext_modules=[zookeepermodule]
)