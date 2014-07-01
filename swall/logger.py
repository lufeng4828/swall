#coding:utf-8
__author__ = 'lufeng4828@163.com'

import logging

_IS_LOGGER_CONFIGURED = False


def is_logger_configured():
    global _IS_LOGGER_CONFIGURED
    return _IS_LOGGER_CONFIGURED


def setup_logger(handler=None, log_level="INFO", log_format=None, date_format=None):
    """
    设置logging
    """

    if is_logger_configured():
        logging.getLogger(__name__).warning("Logfile logging already configured")
        return

    if log_level is None:
        log_level = "INFO"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not handler:
        handler = logging.StreamHandler()
    if not log_format:
        log_format = "%(asctime)s %(levelname)s %(module)s.%(funcName)s:%(lineno)d %(message)s"
    if not date_format:
        date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def setup_file_logger(logfilepath, log_level="INFO", log_format=None, date_format=None):
    """
    设置file日志，其日志会保持到文件中
    """
    handler = logging.FileHandler(logfilepath, "a")
    setup_logger(handler, log_level, log_format, date_format)

    global _IS_LOGGER_CONFIGURED
    _IS_LOGGER_CONFIGURED = True


def setup_console_logger(log_level="INFO", log_format=None, date_format=None):
    """
    设置console日志，其日志直接打印到终端
    """
    handler = logging.StreamHandler()
    setup_logger(handler, log_level, log_format, date_format)

    global _IS_LOGGER_CONFIGURED
    _IS_LOGGER_CONFIGURED = True


if __name__ == "__main__":
    setup_file_logger("/tmp/test.log", log_level="DEBUG")
    logging.debug("log test")
    logging.info("log test")