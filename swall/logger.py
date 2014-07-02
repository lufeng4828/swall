#coding:utf-8
__author__ = 'lufeng4828@163.com'

import logging

LOG_LEVEL = {
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "WARN": logging.WARN,
    "ERROR": logging.ERROR
}


def setup_file_logger(logfilepath, log_level="INFO", log_format=None, date_format=None):
    """
    设置file日志，其日志会保持到文件中
    """
    if not log_format:
        log_format = "%(asctime)s %(levelname)s %(module)s.%(funcName)s:%(lineno)d %(message)s"
    if not date_format:
        date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(filename=logfilepath, level=LOG_LEVEL.get(log_level, logging.INFO), format=log_format, datefmt=date_format)


def setup_console_logger(log_level="INFO", log_format=None, date_format=None):
    """
    设置console日志，其日志直接打印到终端
    """
    if not log_format:
        log_format = "%(asctime)s %(levelname)s %(module)s.%(funcName)s:%(lineno)d %(message)s"
    if not date_format:
        date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(level=LOG_LEVEL.get(log_level, logging.INFO), format=log_format, datefmt=date_format)


if __name__ == "__main__":
    setup_file_logger("/tmp/test.log", log_level="DEBUG")
    logging.debug("log test")
    logging.info("log test")