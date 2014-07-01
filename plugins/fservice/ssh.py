
#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import logging
import paramiko
from swall.utils import checksum, \
    load_fclient

from swall.bfclient import BFClient

log = logging.getLogger()


class SSHClient(BFClient):

    def __init__(self, fs_conf):
        self.fs_conf = fs_conf
        self.pk = paramiko.Transport((self.fs_conf.fs_host, int(self.fs_conf.fs_port)))
        self.pk.connect(username=self.fs_conf.fs_user, password=self.fs_conf.fs_pass)
        self.sftp = paramiko.SFTPClient.from_transport(self.pk)

    def upload(self, upload_path):
        """
        上传文件
        @param upload_path string:本地文件路径
        @return string:remote file path if success else ""
        """
        fid = ""
        if os.path.exists(upload_path):
            fid = checksum(upload_path)
            dist = os.path.join(self.fs_conf.fs_tmp_dir, fid)
            if not self.exists(dist):
                try:
                    self.sftp.put(upload_path, dist)
                except IOError, er:
                    log.error(er)
                    return ""
        else:
            log.error("sfile [%s] not exists" % upload_path)
        return fid

    def exists(self, fid):
        """
        查看文件是否存在
        @param path string:需要查看的文件id
        @return int:1 for exists else 0
        """
        try:
            dist = os.path.join(self.fs_conf.fs_tmp_dir, fid)
            self.sftp.stat(dist)
            return 1
        except IOError:
            return 0

    def download(self, fid, to_path):
        """
        下载文件
        @param filename string:需要下载的文件路径，远程文件
        @param to_path string:存放本地的文件路径
        @return int:1 if success else 0
        """
        try:
            dist = os.path.join(self.fs_conf.fs_tmp_dir, fid)
            self.sftp.get(dist, to_path)
            return 1
        except IOError, er:
            log.error(er)
            return 0

if __name__ == "__main__":
    client = load_fclient("~/Documents/works/git/swall/plugins/fservice", ftype="rsync")
    print client
    scli = client("~/Documents/works/git/swall/conf/swall.conf")
    print scli
    print scli.upload("/etc/services")
    print scli.download("f9f1d3bc559b817e74c13efc3fd1172fbe170d37","/tmp/a.txt")