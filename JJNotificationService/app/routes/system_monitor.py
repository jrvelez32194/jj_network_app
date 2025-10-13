from fastapi import APIRouter
import psutil, os, time, platform

router = APIRouter()

def get_uptime():
    uptime_seconds = time.time() - psutil.boot_time()
    days = int(uptime_seconds // (24 * 3600))
    hours = int((uptime_seconds % (24 * 3600)) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{days} days {hours:02}:{minutes:02}"

@router.get("/system-status")
def get_system_status():
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temps = psutil.sensors_temperatures()

    # CPU temp (depends on Orange Pi kernel sensors)
    cpu_temp = None
    if "cpu_thermal" in temps:
        cpu_temp = temps["cpu_thermal"][0].current
    elif "soc_thermal" in temps:
        cpu_temp = temps["soc_thermal"][0].current

    # Network RX
    net = psutil.net_io_counters()
    rx_today = round(net.bytes_recv / (1024 ** 3), 2)  # GiB

    # Optional: ZRAM (if /dev/zram0 exists)
    zram_total = zram_used = 0
    if os.path.exists("/sys/block/zram0/"):
        try:
            with open("/sys/block/zram0/mem_used_total") as f:
                zram_used = int(f.read().strip()) / 1024**2
            with open("/sys/block/zram0/disksize") as f:
                zram_total = int(f.read().strip()) / 1024**2
        except:
            pass

    return {
        "cpu": cpu_percent,
        "memory": {
            "total": round(memory.total / 1024**3, 2),
            "used": round(memory.used / 1024**3, 2),
            "percent": memory.percent,
        },
        "disk": {
            "total": round(disk.total / 1024**3, 2),
            "used": round(disk.used / 1024**3, 2),
            "percent": disk.percent,
        },
        "temperature": cpu_temp,
        "uptime": get_uptime(),
        "rx_today": f"{rx_today} GiB",
        "zram": {
            "used": round(zram_used / 1024, 1),
            "total": round(zram_total / 1024, 1),
            "percent": round((zram_used / zram_total * 100), 1) if zram_total else 0,
        },
        "system": platform.uname()._asdict(),
    }
