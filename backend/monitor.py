import psutil
import statistics
from datetime import datetime

PROCESS_NAME = "chrome"
BASELINE_SAMPLES = 3      
ABSOLUTE_CPU_THRESHOLD = 30.0   
ABSOLUTE_MEM_THRESHOLD = 1500.0  # Only YouTube + 2+ videos
YOUTUBE_ANOMALY_PROCESS_COUNT = 3  # 3rd YouTube tab triggers anomaly

youtube_process_count = 0  # Track number of Chrome processes (approximate tab count)  

def find_process():
    """Find Chrome process (returns any Chrome process - we'll scan all in get_process_data)"""
    try:
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'] and PROCESS_NAME.lower() in p.info['name'].lower():
                    return p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[ERROR] Finding process: {e}")
    return None

def get_all_chrome_processes():
    """Get ALL Chrome processes"""
    chrome_procs = []
    try:
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if p.info['name'] and PROCESS_NAME.lower() in p.info['name'].lower():
                    chrome_procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"[ERROR] Getting Chrome processes: {e}")
    return chrome_procs

def get_total_chrome_metrics():
    """Get TOTAL CPU and memory for ALL Chrome processes"""
    procs = get_all_chrome_processes()
    
    if not procs:
        return 0, 0
    
    total_cpu = 0
    total_mem = 0
    
    for p in procs:
        try:
            total_cpu += p.cpu_percent(interval=0.01)  # Fast sampling
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        try:
            total_mem += p.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return total_cpu, total_mem

def learn_baseline(process):
    """Learn baseline CPU and memory from ALL Chrome processes"""
    cpu_samples = []
    mem_samples = []

    for i in range(BASELINE_SAMPLES):
        try:
            cpu, mem = get_total_chrome_metrics()
            
            cpu_samples.append(cpu)
            mem_samples.append(mem)
            print(f"[BASELINE {i+1}/{BASELINE_SAMPLES}] CPU: {cpu:.2f}%, Memory: {mem:.2f}MB")
        except Exception as e:
            print(f"[ERROR] Baseline sampling: {e}")
            continue

    try:
        avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 5.0
        avg_mem = statistics.mean(mem_samples) if mem_samples else 150.0
        
        # Ensure minimums
        avg_cpu = max(avg_cpu, 5.0)
        avg_mem = max(avg_mem, 300.0)

        print(f"[BASELINE FINAL] Avg CPU: {avg_cpu:.2f}%, Avg Memory: {avg_mem:.2f}MB\n")
        return avg_cpu, avg_mem
    except Exception as e:
        print(f"[ERROR] Calculating baseline: {e}")
        return 5.0, 300.0

def get_process_data(process, avg_cpu, avg_mem):
    """Get current process data and detect anomalies (from ALL Chrome processes)"""
    try:
        # Get TOTAL metrics for all Chrome processes
        cpu, mem = get_total_chrome_metrics()
        
        # Count Chrome processes (approximates number of tabs)
        chrome_procs = get_all_chrome_processes()
        process_count = len(chrome_procs)
        global youtube_process_count
        youtube_process_count = process_count

        # Simple thresholds
        cpu_anomaly = cpu > ABSOLUTE_CPU_THRESHOLD
        mem_anomaly = mem > ABSOLUTE_MEM_THRESHOLD
        # YouTube tab anomaly: 3+ processes (suggests 3+ tabs including YouTube)
        youtube_anomaly = process_count >= YOUTUBE_ANOMALY_PROCESS_COUNT

        status = "NORMAL"
        reason = "Process operating normally"

        if (cpu_anomaly or mem_anomaly) or (youtube_anomaly and cpu > 20):  # YouTube tab detected
            status = "ANOMALY"
            if cpu_anomaly and mem_anomaly:
                reason = f"HIGH CPU & MEMORY: CPU {cpu:.1f}% + Memory {mem:.1f}MB (Tabs: {process_count})"
            elif cpu_anomaly:
                reason = f"HIGH CPU: {cpu:.1f}% (threshold: {ABSOLUTE_CPU_THRESHOLD}%) - {process_count} tabs detected"
            elif mem_anomaly:
                reason = f"HIGH MEMORY: {mem:.1f}MB (threshold: {ABSOLUTE_MEM_THRESHOLD}MB) - {process_count} tabs detected"
            elif youtube_anomaly:
                reason = f"HIGH TAB COUNT: {process_count} tabs detected (3+ tab anomaly) - Recommended: Close most recent YouTube tab"
            
            print(f"[ANOMALY DETECTED] {reason}")
            print(f"[TAB COUNT] {process_count} Chrome processes detected")
        
        return {
            "cpu": round(cpu, 2),
            "memory": round(mem, 2),
            "status": status,
            "reason": reason,
            "process_count": process_count
        }
    except Exception as e:
        print(f"[ERROR] Getting process data: {e}")
        return {
            "cpu": 0,
            "memory": 0,
            "status": "ERROR",
            "reason": f"Error: {str(e)}",
            "process_count": 0
        }

def get_timestamp():
    """Get current timestamp"""
    return datetime.now().strftime("%H:%M:%S")

def find_heaviest_child_process(parent_process):
    """Find the heaviest Chrome process (by memory, excluding obvious non-tab processes)"""
    procs = get_all_chrome_processes()
    
    if not procs:
        return None
    
    heaviest = None
    max_mem = 0
    
    # Sort by memory to find heaviest
    memory_data = []
    for p in procs:
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            memory_data.append((p, mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by memory descending
    memory_data.sort(key=lambda x: x[1], reverse=True)
    
    print(f"[TAB ANALYSIS] Found {len(memory_data)} Chrome processes:")
    for i, (p, mem) in enumerate(memory_data):
        try:
            print(f"  Process {i+1}: PID={p.pid}, Memory={mem:.2f}MB")
        except:
            pass
    
    # Find heaviest with minimum 100MB memory usage (likely a tab, not overhead)
    for p, mem in memory_data:
        if mem > 100:
            heaviest = p
            max_mem = mem
            break
    
    if heaviest:
        try:
            print(f"[TARGET IDENTIFIED] Will close: PID={heaviest.pid}, Memory={max_mem:.2f}MB")
        except:
            pass
    
    return heaviest if heaviest and max_mem > 100 else None
