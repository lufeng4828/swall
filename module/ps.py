#coding:utf-8
__author__ = 'lufeng4828@163.com'

import time
import psutil
import logging
from swall.utils import node

log = logging.getLogger()


@node
def top(num_processes=5, interval=3, *args, **kwarg):
    """
    def top((num_processes=5, interval=3, *args, **kwarg) -> Return a list of top CPU consuming processes during the interval.
    @param num_processes int:the top N CPU consuming processes
    @param interval int:the number of seconds to sample CPU usage over
    @return list:a list of top CPU consuming processes
    """
    num_processes = int(num_processes)
    interval = int(num_processes)
    result = []
    start_usage = {}
    for pid in psutil.get_pid_list():
        try:
            process = psutil.Process(pid)
            user, system = process.get_cpu_times()
        except psutil.NoSuchProcess:
            continue
        start_usage[process] = user + system
    time.sleep(interval)
    usage = set()
    for process, start in start_usage.items():
        try:
            user, system = process.get_cpu_times()
        except psutil.NoSuchProcess:
            continue
        now = user + system
        diff = now - start
        usage.add((diff, process))

    for idx, (diff, process) in enumerate(reversed(sorted(usage))):
        if num_processes and idx >= num_processes:
            break
        if len(process.cmdline()) == 0:
            cmdline = [process.name()]
        else:
            cmdline = process.cmdline()
        info = {'cmd': cmdline,
                'user': process.username(),
                'status': process.status(),
                'pid': process.pid,
                'create_time': process.create_time(),
                'cpu': {},
                'mem': {},
        }
        for key, value in process.get_cpu_times()._asdict().items():
            info['cpu'][key] = value
        for key, value in process.get_memory_info()._asdict().items():
            info['mem'][key] = value
        result.append(info)
    return result


@node
def get_pid_list(*args, **kwarg):
    """
    def get_pid_list(*args, **kwarg) -> Return a list of process ids (PIDs) for all running processes.
    @return list:
    """
    return psutil.get_pid_list()


@node
def kill_pid(pid, signal=15, *args, **kwarg):
    """
    def kill_pid(pid, signal=15, *args, **kwarg) -> Kill a process by PID.
    @param pid int:PID of process to kill.
    @param signal int:Signal to send to the process. See manpage entry for kill for possible values. Default: 15 (SIGTERM).
    @return bool:True or False
    """
    try:
        psutil.Process(int(pid)).send_signal(signal)
        return True
    except psutil.NoSuchProcess:
        return False


@node
def pkill(pattern, user=None, signal=15, full=False, *args, **kwarg):
    """
    def pkill(pattern, user=None, signal=15, full=False, *args, **kwarg) -> Kill processes matching a pattern.
    @param pattern string: Pattern to search for in the process list.
    @param user string: Limit matches to the given username. Default: All users.
    @param int signal: Signal to send to the process(es). See manpage entry for kill for possible values. Default: 15 (SIGTERM).
    @param full bool: A boolean value indicating whether only the name of the command or the full command line should be matched against the pattern.
    @return list:killed pid
    """
    signal = int(signal)
    killed = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(proc.cmdline()) if full \
            else pattern in proc.name()
        user_match = True if user is None else user == proc.username()
        if name_match and user_match:
            try:
                proc.send_signal(signal)
                killed.append(proc.pid)
            except psutil.NoSuchProcess:
                pass
    if not killed:
        return None
    else:
        return {'killed': killed}


@node
def pgrep(pattern, user=None, full=False, *args, **kwarg):
    """
    def pgrep(pattern, user=None, full=False, *args, **kwarg) -> Return the pids for processes matching a pattern. If full is true, the full command line is searched for a match,
    otherwise only the name of the command is searched.
    @param pattern string: Pattern to search for in the process list.
    @param user string: Limit matches to the given username. Default: All users.
    @param full bool: A boolean value indicating whether only the name of the command or the full command line should be matched against the pattern.
    @return list:
    """

    procs = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(proc.cmdline()) if full \
            else pattern in proc.name()
        user_match = True if user is None else user == proc.username()
        if name_match and user_match:
            procs.append({"pname": ','.join(proc.cmdline()), "pid": proc.pid})
    return procs or None


@node
def cpu_percent(interval=0.1, per_cpu=False, *args, **kwarg):
    """
    def cpu_percent(interval=0.1, per_cpu=False) -> Return the percent of time the CPU is busy.
    @param interval int: the number of seconds to sample CPU usage over
    @param per_cpu bool:if True return an array of CPU percent busy for each CPU, otherwise aggregate all percents into one number
    @return list:
    """
    interval = float(interval)
    if per_cpu:
        result = list(psutil.cpu_percent(interval, True))
    else:
        result = psutil.cpu_percent(interval)
    return result


@node
def cpu_times(per_cpu=False, *args, **kwarg):
    """
    def cpu_times(per_cpu=False) -> Return the percent of time the CPU spends in each state, e.g. user, system, idle, nice, iowait, irq, softirq.
    @param per_cpu bool:if True return an array of percents for each CPU, otherwise aggregate all percents into one number
    @return dict:
    """
    if per_cpu:
        result = [dict(times._asdict()) for times in psutil.cpu_times(True)]
    else:
        result = dict(psutil.cpu_times(per_cpu)._asdict())
    return result


@node
def virtual_memory(*args, **kwarg):
    """
    def virtual_memory(*args, **kwarg) -> Return a dict that describes statistics about system memory usage.
    @return dict:
    """
    return dict(psutil.virtual_memory()._asdict())


@node
def swap_memory(*args, **kwarg):
    """
    def swap_memory(*args, **kwarg) -> Return a dict that describes swap memory statistics.
    @return dict:
    """
    return dict(psutil.swap_memory()._asdict())


@node
def physical_memory_usage(*args, **kwarg):
    """
    def physical_memory_usage(*args, **kwarg) -> Return a dict that describes free and available physical memory.
    @return dict:
    """
    return dict(psutil.phymem_usage()._asdict())


@node
def virtual_memory_usage(*args, **kwarg):
    """
    def virtual_memory_usage(*args, **kwarg) -> Return a dict that describes free and available memory, both physical
    @return dict:
    """
    return dict(psutil.virtmem_usage()._asdict())


@node
def cached_physical_memory(*args, **kwarg):
    """
    def cached_physical_memory(*args, **kwarg) -> Return the amount cached memory.
    @return int:
    """
    return psutil.cached_phymem()


@node
def physical_memory_buffers(*args, **kwarg):
    """
    def physical_memory_buffers(*args, **kwarg) -> Return the amount of physical memory buffers.
    @return int
    """
    return psutil.phymem_buffers()


@node
def disk_partitions(all=False, *args, **kwarg):
    """
    def disk_partitions(all=False, *args, **kwarg) -> Return a list of disk partitions and their device, mount point, and filesystem type.
    @param all bool: if set to False, only return local, physical partitions (hard disk, USB, CD/DVD partitions).  If True, return all filesystems.
    return list(dict):
    """
    result = [dict(partition._asdict()) for partition in
              psutil.disk_partitions(all)]
    return result


@node
def disk_usage(path, *args, **kwarg):
    """
    def disk_usage(path, *args, **kwarg) -> Given a path, return a dict listing the total available space as well as the free space, and used space.
    @param path string:e.g /home
    @return dict:
    """
    return dict(psutil.disk_usage(path)._asdict())


@node
def disk_partition_usage(all=False, *args, **kwarg):
    """
    def disk_partition_usage(all=False, *args, **kwarg) -> Return a list of disk partitions plus the mount point, filesystem and usage statistics.
    @param all bool:if set to False, only return local, physical partitions (hard disk, USB, CD/DVD partitions).  If True, return all filesystems.
    @return list(dict):
    """
    result = disk_partitions(all)
    for partition in result:
        partition.update(disk_usage(partition['mountpoint']))
    return result


@node
def total_physical_memory(*args, **kwarg):
    """
    def total_physical_memory(*args, **kwarg) -> Return the total number of bytes of physical memory.
    @return int:
    """
    return psutil.TOTAL_PHYMEM


@node
def num_cpus(*args, **kwarg):
    """
    def num_cpus(*args, **kwarg) -> Return the number of CPUs.
    @return int:
    """
    return psutil.NUM_CPUS

