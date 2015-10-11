#coding:utf-8
__author__ = 'lufeng4828@163.com'

import os
import msgpack
import hmac
import logging
import hashlib
from Crypto.Cipher import AES
from swall.excpt import SwallAuthenticationError

log = logging.getLogger()


class Crypt(object):
    """
    对称加密类
    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    """

    PICKLE_PAD = 'pickle::'
    AES_BLOCK_SIZE = 16
    SIG_SIZE = hashlib.sha256().digest_size

    def __init__(self, key_string, key_size=192):
        self.keys = self.extract_keys(key_string, key_size)
        self.key_size = key_size
        self.serial = msgpack

    @classmethod
    def gen_key(cls, key_size=192):
        """
        生成特定长度的用于堆成加密的key
        @param key_size:key len
        return string:key
        """
        key = os.urandom(key_size // 8 + cls.SIG_SIZE)
        return key.encode('base64').replace('\n', '')

    @classmethod
    def extract_keys(cls, key_string, key_size):
        """
        extract_keys to two part
        @param key_string:the key string
        @param key_size:key size
        @return tuple(keys,rand_pad)
        """
        key = key_string.decode('base64')
        if len(key) != (key_size / 8 + cls.SIG_SIZE):
            return ""
        else:
            return key[:-cls.SIG_SIZE], key[-cls.SIG_SIZE:]

    def encrypt(self, data):
        """
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        @param data string:
        @return string:aes_string
        """
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(data) % self.AES_BLOCK_SIZE
        data = data + pad * chr(pad)
        iv_bytes = os.urandom(self.AES_BLOCK_SIZE)
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = iv_bytes + cypher.encrypt(data)
        sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
        return data + sig

    def decrypt(self, data):
        """
        verify HMAC-SHA256 signature and decrypt data with AES-CBC
        @param data string:
        @return string
        """
        aes_key, hmac_key = self.keys
        sig = data[-self.SIG_SIZE:]
        data = data[:-self.SIG_SIZE]
        if hmac.new(hmac_key, data, hashlib.sha256).digest() != sig:
            raise SwallAuthenticationError('message authentication failed')
        iv_bytes = data[:self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        return data[:-ord(data[-1])]

    def dumps(self, obj):
        """
        Serialize and encrypt a python object
        @param obj python_obj:
        @return string
        """
        return self.encrypt(self.PICKLE_PAD + self.serial.dumps(obj))

    def loads(self, data):
        """
        Decrypt and un-serialize a python object
        @param data string:
        @return python_obj:
        """
        data = self.decrypt(data)
        if not data.startswith(self.PICKLE_PAD):
            return {}
        return self.serial.loads(data[len(self.PICKLE_PAD):])



