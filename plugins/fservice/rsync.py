#coding:utf-8
__author__ = 'lufeng4828@163.com'

import time
import logging
from subprocess import call
from swall.utils import checksum, \
    load_fclient

from swall.bfclient import BFClient

log = logging.getLogger()


class RSYNCClient(BFClient):

    def __init__(self, fs_conf):
        self.fs_conf = fs_conf

    def upload(self, upload_path):
        """
        上传文件
        @param upload_path string:本地文件路径
        @return string:remote file path if success else ""
        """
        if not upload_path:
            return ""
        fid = checksum(upload_path)
        max_retry = self.fs_conf.fs_failtry
        index = 1
        while index <= int(max_retry):
            ret = call(
                "RSYNC_PASSWORD=%s rsync -a --port=%s --partial %s %s@%s::swall_fs/%s" %
                (
                    self.fs_conf.fs_pass,
                    self.fs_conf.fs_port,
                    upload_path,
                    self.fs_conf.fs_user,
                    self.fs_conf.fs_host,
                    fid
                ),
                shell=True
            )
            if ret != 0:
                time.sleep(5)
            else:
                break
            index += 1
        if index <= int(max_retry):
            return fid
        else:
            return ""

    def exists(self, fid):
        """
        查看文件是否存在
        @param path string:需要查看的文件id
        @return int:1 for exists else 0
        """
        return 0

    def download(self, fid, to_path):
        """
        下载文件
        @param filename string:需要下载的文件路径，远程文件
        @param to_path string:存放本地的文件路径
        @return int:1 if success else 0
        """
        if fid == "" or to_path == "":
            return 0
        max_retry = self.fs_conf.fs_failtry
        index = 1
        while index <= int(max_retry):
            ret = call(
                "RSYNC_PASSWORD=%s rsync -a --port=%s --partial %s@%s::swall_fs/%s %s" %
                (
                    self.fs_conf.fs_pass,
                    self.fs_conf.fs_port,
                    self.fs_conf.fs_user,
                    self.fs_conf.fs_host,
                    fid,
                    to_path
                ),
                shell=True
            )
            if ret != 0:
                time.sleep(5)
            else:
                break
            index += 1
        if index <= int(max_retry):
            return 1
        else:
            return 0

if __name__ == "__main__":
    client = load_fclient("~/Documents/works/git/swall/plugins/fservice", ftype="rsync")
    print client
    scli = client("~/Documents/works/git/swall/conf/swall.conf")
    print scli
    print scli.upload("/etc/services")
    print scli.download("f9f1d3bc559b817e74c13efc3fd1172fbe170d37","/tmp/a.txt")