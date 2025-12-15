"""
系统监控服务模块

提供服务器系统信息、资源使用率、网络流量和 CPU 历史数据的获取功能。
所有方法都是异步的，避免阻塞事件循环。
"""

import asyncio
import platform
import socket
import random
from datetime import datetime

import psutil


class SystemMonitorService:
    """系统监控服务类（异步版本）"""

    async def get_system_info(self) -> dict:
        """
        获取系统基础信息（异步）
        
        Returns:
            包含主机名、操作系统、内核、架构、IP、启动时间、运行时长的字典
        """
        # 将同步操作放到线程池中执行，避免阻塞事件循环
        return await asyncio.to_thread(self._get_system_info_sync)

    def _get_system_info_sync(self) -> dict:
        """同步获取系统信息（在线程池中执行）"""
        # 获取主机名
        hostname = socket.gethostname()
        
        # 获取操作系统信息
        os_name = platform.system()
        os_release = platform.release()
        os_version = platform.version()
        
        # 组合操作系统名称
        if os_name == "Linux":
            try:
                # 尝试读取 Linux 发行版信息
                import distro
                os_full = distro.name(pretty=True)
            except ImportError:
                os_full = f"{os_name} {os_release}"
        else:
            os_full = f"{os_name} {os_release}"
        
        # 获取内核版本
        kernel = platform.release()
        
        # 获取架构
        arch = platform.machine()
        
        # 获取 IP 地址
        try:
            # 创建一个临时连接来获取本机 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"

        # 获取启动时间和运行时长
        boot_timestamp = psutil.boot_time()
        boot_time = datetime.fromtimestamp(boot_timestamp)
        boot_time_str = boot_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 计算运行时长（秒）
        uptime_seconds = int(datetime.now().timestamp() - boot_timestamp)
        
        return {
            "hostname": hostname,
            "os": os_full,
            "kernel": kernel,
            "arch": arch,
            "ip": ip,
            "bootTime": boot_time_str,
            "uptimeSeconds": uptime_seconds
        }

    async def get_resource_usage(self) -> dict:
        """
        获取当前资源使用率（异步）
        
        Returns:
            包含 CPU、内存、磁盘、网络使用率的字典，值为 0-100 的整数
        """
        # 将同步操作放到线程池中执行，避免阻塞事件循环
        # 特别是 psutil.cpu_percent(interval=0.1) 会阻塞 100ms
        return await asyncio.to_thread(self._get_resource_usage_sync)

    def _get_resource_usage_sync(self) -> dict:
        """同步获取资源使用率（在线程池中执行）"""
        # 获取 CPU 使用率（interval=0.1 会阻塞 100ms）
        cpu_percent = int(psutil.cpu_percent(interval=0.1))
        
        # 获取内存使用率
        memory = psutil.virtual_memory()
        memory_percent = int(memory.percent)
        
        # 获取磁盘使用率（根目录，Windows 用 C:）
        try:
            disk = psutil.disk_usage("/")
        except Exception:
            # Windows 系统使用 C: 盘
            disk = psutil.disk_usage("C:\\")
        disk_percent = int(disk.percent)
        
        # 获取网络使用率（模拟值，因为网络使用率需要基准值来计算）
        # 这里使用网络 IO 计数器的变化来估算
        net_io = psutil.net_io_counters()
        # 简单模拟：基于当前网络活动生成一个合理的百分比
        network_percent = min(100, max(0, int((net_io.bytes_sent + net_io.bytes_recv) % 100)))
        
        return {
            "cpu": cpu_percent,
            "memory": memory_percent,
            "disk": disk_percent,
            "network": network_percent
        }

    async def get_traffic_data(self, hours: int = 24) -> list[dict]:
        """
        获取网络流量数据（模拟数据，异步）
        
        Args:
            hours: 获取的小时数，默认 24 小时
            
        Returns:
            流量数据点列表，按时间升序排列（从最早到最新）
        """
        # 这个方法本身不阻塞，但为了一致性也改为异步
        return await asyncio.to_thread(self._get_traffic_data_sync, hours)

    def _get_traffic_data_sync(self, hours: int = 24) -> list[dict]:
        """同步获取流量数据（在线程池中执行）"""
        data = []
        current_hour = datetime.now().hour
        
        for i in range(hours):
            # 计算时间标签（从 hours 小时前开始，到当前时间）
            hour = (current_hour - hours + 1 + i) % 24
            time_label = f"{hour}:00"
            
            # 生成模拟的流量数据
            # 使用固定种子确保同一小时的数据相对稳定
            random.seed(hour + i * 100)
            inbound = random.randint(20, 100)
            outbound = random.randint(15, 80)
            
            data.append({
                "time": time_label,
                "inbound": inbound,
                "outbound": outbound
            })
        
        # 重置随机种子
        random.seed()
        
        return data

    async def get_cpu_history(self, minutes: int = 60) -> list[dict]:
        """
        获取 CPU 使用率历史数据（模拟数据，异步）
        
        Args:
            minutes: 获取的分钟数，默认 60 分钟
            
        Returns:
            CPU 历史数据点列表，按时间降序排列（从最新到最早）
        """
        # psutil.cpu_percent(interval=0.1) 会阻塞，放到线程池执行
        return await asyncio.to_thread(self._get_cpu_history_sync, minutes)

    def _get_cpu_history_sync(self, minutes: int = 60) -> list[dict]:
        """同步获取 CPU 历史数据（在线程池中执行）"""
        data = []
        
        # 获取当前 CPU 使用率作为基准（会阻塞 100ms）
        current_cpu = psutil.cpu_percent(interval=0.1)
        
        for i in range(minutes):
            # 时间标签：从最新（1s）到最早（minutes s）
            time_label = f"{i + 1}s"
            
            # 生成模拟的 CPU 使用率
            # 基于当前值添加一些随机波动
            random.seed(i * 50)
            variation = random.randint(-15, 15)
            usage = max(0, min(100, int(current_cpu + variation)))
            
            data.append({
                "time": time_label,
                "usage": usage
            })
        
        # 重置随机种子
        random.seed()
        
        return data


# 创建服务实例
system_monitor_service = SystemMonitorService()
