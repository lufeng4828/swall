#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import traceback
import ftplib
import logging
from swall.utils import checksum, \
    load_fclient

from swall.bfclient import BFClient

log = logging.getLogger()

BLOCK_SIZE = 8192


class FTPClient(BFClient):

    def __init__(self, fs_conf):
        self.fs_conf = fs_conf
        self.ftp = ftplib.FTP(self.fs_conf.fs_host)
        self.ftp.port = int(self.fs_conf.fs_port)
        self.ftp.login(self.fs_conf.fs_user, self.fs_conf.fs_pass)
        self.ftp.cwd(self.fs_conf.fs_tmp_dir)

    def upload(self, upload_path):
        """
        上传文件
        @param upload_path string:本地文件路径
        @return string:remote file path if success else ""
        """
        if not upload_path:
            return ""
        fid = checksum(upload_path)
        if self.exists(fid):
            return 1
        ftp_path = os.path.join(self.fs_conf.fs_tmp_dir, fid)
        try:
            f = open(upload_path, 'rb')
            self.ftp.storbinary('STOR %s' % ftp_path, f, BLOCK_SIZE)
        except :
            log.error(traceback.format_exc())
            return 0
        return 1

    def exists(self, fid):
        """
        查看文件是否存在
        @param path string:需要查看的文件id
        @return int:1 for exists else 0
        """
        if fid in self.ftp.nlst(self.fs_conf.fs_tmp_dir):
            return 1
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
        ftp_file = os.path.join(self.fs_conf.fs_tmp_dir, fid)
        try:
            f = open(to_path, 'wb').write
            self.ftp.retrbinary('RETR %s' % ftp_file, f, BLOCK_SIZE)
        except :
            log.error(traceback.format_exc())
            return 0
        return 1

if __name__ == "__main__":
    client = load_fclient("~/Documents/works/git/swall/plugins/fservice", ftype="rsync")
    print client
    scli = client("~/Documents/works/git/swall/conf/swall.conf")
    print scli
    print scli.upload("/etc/services")
    print scli.download("f9f1d3bc559b817e74c13efc3fd1172fbe170d37","/tmp/a.txt")