import psutil
import statistics

PROCESS_NAME = "chrome"
ANOMALY_THRESHOLD = 3.0
BASELINE_SAMPLES = 10



def find_process():
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and PROCESS_NAME.lower() in p.info['name'].lower():
            return p
    return None

def learn_baseline(process):
    cpu_samples = []
    mem_samples = []

    for _ in range(BASELINE_SAMPLES):
        cpu_samples.append(process.cpu_percent(interval=1))
        mem_samples.append(process.memory_info().rss / (1024 * 1024))

    avg_cpu = statistics.mean(cpu_samples)
    avg_mem = statistics.mean(mem_samples)

    return avg_cpu, avg_mem

def get_process_data(process, avg_cpu, avg_mem):
    cpu = process.cpu_percent(interval=1)
    mem = process.memory_info().rss / (1024 * 1024)

    cpu_anomaly = cpu > avg_cpu * ANOMALY_THRESHOLD
    mem_anomaly = mem > avg_mem * ANOMALY_THRESHOLD

    status = "NORMAL"
    reason = "Process operating normally"

    if cpu_anomaly and mem_anomaly:
        status = "ANOMALY"
        reason = "High CPU and memory usage due to heavy workload or multiple tabs"
    elif cpu_anomaly:
        status = "ANOMALY"
        reason = "High CPU due to multithreading or heavy background tasks"
    elif mem_anomaly:
        status = "ANOMALY"
        reason = "High memory usage due to multiple tabs or memory leak"

    return {
        "cpu": round(cpu, 2),
        "memory": round(mem, 2),
        "status": status,
        "reason": reason
    }
