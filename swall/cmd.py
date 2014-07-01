#coding:utf-8
__author__ = 'lufeng4828@163.com'

import sys
from swall.parser import SwallAgent, Swall

reload(sys)
sys.setdefaultencoding('utf-8')


def swall_agent():
    """
    manage the swall agent
    """
    agent = SwallAgent()
    agent.main()


if __name__ == "__main__":
    swall = Swall()
    swall.main()