"""系统监控命令"""
import re


class MonitorCommands:
    def __init__(self, ssh, output):
        self.ssh = ssh
        self.output = output

    def run(self, subcmd, args):
        dispatch = {
            "system":        self.system,
            "cpu":           self.cpu,
            "memory":        self.memory,
            "processes":     self.processes,
            "disk":          self.disk,
            "network-stats": self.network_stats,
            "temperature":   self.temperature,
            "uptime":        self.uptime,
        }
        return self.output.dump(dispatch.get(subcmd, self._help)())

    def _help(self):
        return {"error": "未知子命令，可用: system / cpu / memory / processes / disk / network-stats / temperature / uptime"}

    def _parse_meminfo(self, raw):
        info = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        return info

    def _parse_uptime(self, raw):
        parts = raw.strip().split()
        uptime_seconds = float(parts[0]) if parts else 0
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        mins = int((uptime_seconds % 3600) // 60)
        idle = float(parts[1]) if len(parts) > 1 else 0
        idle_pct = min(100, idle / 10.0)
        return {"seconds": uptime_seconds, "human": f"{days}d {hours}h {mins}m", "idle_percent": idle_pct}

    # ── 系统概况 ──
    def system(self):
        board_info = self.ssh.exec("ubus call system board 2>/dev/null")
        import json
        try:
            board = json.loads(board_info)
        except Exception:
            board = {"raw": board_info}

        uptime_raw = self.ssh.exec("cat /proc/uptime")
        uptime = self._parse_uptime(uptime_raw)

        loadavg = self.ssh.exec("cat /proc/loadavg")
        parts = loadavg.strip().split()
        return {
            "board": board,
            "uptime": uptime,
            "load_average": parts[:3] if parts else [],
            "running_processes": parts[3] if len(parts) > 3 else "",
        }

    # ── CPU ──
    def cpu(self):
        top = self.ssh.exec("top -n1 2>/dev/null | head -15")
        # CPU 信息
        cpuinfo = self.ssh.exec("cat /proc/cpuinfo 2>/dev/null | grep -E 'model name|cpu MHz|Processor|BogoMIPS' | head -10")
        # 统计 /proc/stat（计算使用率）
        stat1 = self.ssh.exec("cat /proc/stat")
        import time; time.sleep(1)
        stat2 = self.ssh.exec("cat /proc/stat")
        try:
            def parse_stat(s):
                line = s.strip().splitlines()[0]
                fields = line.split()
                total = sum(int(x) for x in fields[1:])
                idle = int(fields[4])
                return total, idle
            t1, i1 = parse_stat(stat1)
            t2, i2 = parse_stat(stat2)
            usage = round((1 - (i2 - i1) / (t2 - t1)) * 100, 1) if (t2 - t1) > 0 else 0
        except Exception:
            usage = "unknown"
        return {
            "cpu_info": cpuinfo.strip(),
            "usage_percent": usage,
            "top_snapshot": top.strip(),
        }

    # ── 内存 ──
    def memory(self):
        meminfo = self.ssh.exec("cat /proc/meminfo")
        info = self._parse_meminfo(meminfo)
        # 解析 KB 值
        def kb(key):
            val = info.get(key, "0 kB")
            num = int(re.sub(r"[^\d]", "", val))
            return {"raw": val, "mb": round(num / 1024, 1)}
        return {
            "total":     kb("MemTotal"),
            "free":      kb("MemFree"),
            "available": kb("MemAvailable"),
            "buffers":   kb("Buffers"),
            "cached":    kb("Cached"),
            "swap_total": kb("SwapTotal"),
            "swap_free":  kb("SwapFree"),
        }

    # ── 进程列表 ──
    def processes(self):
        ps = self.ssh.exec(
            "ps ax -o pid,pcpu,pmem,rss,vsz,stat,user,comm --cols=200 2>/dev/null | head -50"
        )
        lines = []
        for line in ps.strip().splitlines()[1:]:
            parts = line.split(None, 7)
            if len(parts) >= 7:
                lines.append({
                    "pid":    parts[0],
                    "cpu":    parts[1],
                    "mem":    parts[2],
                    "rss_kb": parts[3],
                    "vsz_kb": parts[4],
                    "stat":   parts[5],
                    "user":   parts[6],
                    "comm":   parts[7] if len(parts) > 7 else "",
                })
        return {"processes": lines}

    # ── 磁盘 ──
    def disk(self):
        df = self.ssh.exec("df -h 2>/dev/null | grep -v 'tmpfs\\|overlay\\|udev'")
        mounts = []
        for line in df.strip().splitlines():
            parts = line.split()
            if len(parts) >= 6:
                mounts.append({
                    "filesystem": parts[0],
                    "size":       parts[1],
                    "used":       parts[2],
                    "avail":      parts[3],
                    "use_pct":    parts[4],
                    "mounted":    parts[5],
                })
        return {"filesystems": mounts}

    # ── 网络流量统计 ──
    def network_stats(self):
        dev_stats = self.ssh.exec("cat /proc/net/dev")
        interfaces = []
        for line in dev_stats.strip().splitlines()[2:]:
            parts = line.split(":", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                fields = parts[1].split()
                if len(fields) >= 8:
                    interfaces.append({
                        "name":    name,
                        "rx_bytes":   int(fields[0]),
                        "rx_packets": int(fields[1]),
                        "rx_errs":    int(fields[2]),
                        "tx_bytes":   int(fields[8]),
                        "tx_packets": int(fields[9]),
                        "tx_errs":    int(fields[10]),
                    })
        return {"interfaces": interfaces}

    # ── 温度 ──
    def temperature(self):
        # 尝试多个路径
        paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
            "/sys/class/hwmon/hwmon1/temp1_input",
            "/sys/devices/virtual/thermal/thermal_zone0/temp",
        ]
        for path in paths:
            raw = self.ssh.exec(f"cat {path} 2>/dev/null")
            if raw.strip().isdigit():
                temp_c = int(raw.strip()) / 1000.0
                return {"celsius": temp_c, "source": path}
        return {"celsius": None, "note": "温度传感器不可用"}

    # ── 运行时间 ──
    def uptime(self):
        raw = self.ssh.exec("cat /proc/uptime")
        return self._parse_uptime(raw)