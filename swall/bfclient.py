#coding:utf-8
__author__ = 'lufeng4828@163.com'

from abc import ABCMeta, abstractmethod


class BFClient(object):
    """
    该类为文件客户端的基类，所有的file_client都需要继承本类并实现upload、download、find方法
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def upload(self, upload_path):
        pass

    @abstractmethod
    def download(self, fid, to_path):
        pass

    @abstractmethod
    def exists(self, fid):
        pass
