#coding:utf-8
__author__ = 'lufeng4828@163.com'


class SwallException(Exception):
    """
    Base exception class; all Salt-specific exceptions should subclass this
    """


class SwallAgentError(SwallException):
    """
    Problem reading the master root key
    """


class SwallCommandExecutionError(SwallException):
    """
    Func run errror
    """


class SwallTimeoutError(SwallException):
    """
     Timeout error
    """


class SwallAuthenticationError(SwallException):
    """
    HMAC-SHA256 Authentication
    """