import psutil
import statistics
from datetime import datetime
import os

PROCESS_NAME = "chrome"
BASELINE_SAMPLES = 3      
ABSOLUTE_CPU_THRESHOLD = 30.0   
ABSOLUTE_MEM_THRESHOLD = 1500.0  # Only YouTube + 2+ videos
YOUTUBE_ANOMALY_PROCESS_COUNT = 3  # 3rd YouTube tab triggers anomaly

youtube_process_count = 0  # Track number of Chrome processes (approximate tab count)
FLASK_APP_PID = os.getpid()  # Current Flask app PID (localhost:5000)  

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

def is_protected_process(p):
    """Check if a process should be protected from closure (Flask app)\n    Protected processes:
    - Flask app itself (running localhost dashboard)
    - Any process that is the Flask server
    """
    try:
        # Protect the Flask app process
        if p.pid == FLASK_APP_PID:
            return True
        # Protect any python process (might be Flask)
        if PROCESS_NAME.lower() not in p.name().lower():
            if 'python' in p.name().lower():
                return True
    except:
        pass
    return False

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

def get_visible_tab_count():
    """Count only VISIBLE TABS (filters out background processes like GPU, utility, etc)
    More aggressive filtering: Skip top 5-7 processes which are usually background services,
    and only count processes >50MB as actual tabs.
    """
    procs = get_all_chrome_processes()
    
    if not procs:
        return 0
    
    # Get memory for each process
    memory_data = []
    for p in procs:
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            memory_data.append((p, mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by memory descending
    memory_data.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n[TAB COUNT ANALYSIS] Total Chrome processes: {len(memory_data)}")
    print(f"[PROCESS LIST] Memory breakdown:")
    for i, (p, mem) in enumerate(memory_data):
        proc_type = "BACKGROUND" if i < 5 else "POSSIBLE TAB"
        print(f"  {i+1}. {proc_type}: {mem:.1f}MB")
    
    # AGGRESSIVE FILTERING: Skip top 5-7 processes
    # These are typically: Main Browser, GPU, Utility-1, Utility-2, Service Worker, Extension, etc.
    num_background = min(7, len(memory_data) // 2)  # Skip up to 7, or half the total processes
    
    # Only count processes >50MB as actual tabs (filters out small utility processes)
    visible_tabs = []
    for p, mem in memory_data[num_background:]:
        if mem > 50:  # Min 50MB for a real tab
            visible_tabs.append((p, mem))
    
    visible_tab_count = len(visible_tabs)
    
    print(f"[FILTERING] Skipped top {num_background} background processes")
    print(f"[RESULT] Visible tabs (>50MB after filtering): {visible_tab_count}")
    if visible_tabs:
        for p, mem in visible_tabs:
            print(f"  - TAB: {mem:.1f}MB")
    print()
    
    return visible_tab_count

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
        
        # Count VISIBLE TABS ONLY (filters background processes)
        visible_tab_count = get_visible_tab_count()

        # Simple thresholds
        cpu_anomaly = cpu > ABSOLUTE_CPU_THRESHOLD
        mem_anomaly = mem > ABSOLUTE_MEM_THRESHOLD
        # YouTube tab anomaly: 3+ VISIBLE tabs (not background processes)
        youtube_anomaly = visible_tab_count >= YOUTUBE_ANOMALY_PROCESS_COUNT

        status = "NORMAL"
        reason = "Process operating normally"

        if (cpu_anomaly or mem_anomaly) or (youtube_anomaly and cpu > 20):  # YouTube tab detected
            status = "ANOMALY"
            if cpu_anomaly and mem_anomaly:
                reason = f"HIGH CPU & MEMORY: CPU {cpu:.1f}% + Memory {mem:.1f}MB (Visible tabs: {visible_tab_count})"
            elif cpu_anomaly:
                reason = f"HIGH CPU: {cpu:.1f}% (threshold: {ABSOLUTE_CPU_THRESHOLD}%) - {visible_tab_count} visible tabs"
            elif mem_anomaly:
                reason = f"HIGH MEMORY: {mem:.1f}MB (threshold: {ABSOLUTE_MEM_THRESHOLD}MB) - {visible_tab_count} visible tabs"
            elif youtube_anomaly:
                reason = f"HIGH TAB COUNT: {visible_tab_count} VISIBLE tabs detected (3+ tab anomaly) - Recommended: Close most recent YouTube tab"
            
            print(f"[ANOMALY DETECTED] {reason}")
            print(f"[VISIBLE TAB COUNT] {visible_tab_count} actual tabs detected (background processes excluded)")
        
        return {
            "cpu": round(cpu, 2),
            "memory": round(mem, 2),
            "status": status,
            "reason": reason,
            "process_count": visible_tab_count,
            "note": "Localhost (Flask dashboard) and background processes excluded from monitoring"
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
    """Find the heaviest VISIBLE TAB (filters background processes like GPU, utility, etc)
    EXCLUDES: localhost dashboard tabs and Flask app processes
    Uses aggressive filtering to identify actual tabs vs background services.
    """
    procs = get_all_chrome_processes()
    
    if not procs:
        return None
    
    # Get memory for each process
    memory_data = []
    for p in procs:
        try:
            # Skip protected processes (Flask app, localhost tabs)
            if is_protected_process(p):
                print(f"[PROTECTED] Skipping PID={p.pid} (Flask/localhost protected)")
                continue
            
            mem = p.memory_info().rss / (1024 * 1024)
            memory_data.append((p, mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by memory descending
    memory_data.sort(key=lambda x: x[1], reverse=True)
    
    print(f"[TAB ANALYSIS] Found {len(memory_data)} Chrome processes (excluding localhost):")
    for i, (p, mem) in enumerate(memory_data):
        try:
            label = "(BACKGROUND)" if i < 5 else "(VISIBLE TAB)" if mem > 50 else "(SMALL UTIL)"
            print(f"  Process {i+1}: PID={p.pid}, Memory={mem:.2f}MB {label}")
        except:
            pass
    
    # EXCLUDE TOP 5-7 (background processes: browser, GPU, utilities, service workers)
    # Find heaviest VISIBLE TAB (after skipping background processes)
    num_background = min(7, len(memory_data) // 2)
    
    heaviest = None
    max_mem = 0
    
    for p, mem in memory_data[num_background:]:  # Skip top N
        if mem > 50:  # Tab must be at least 50MB (actual tab, not tiny process)
            heaviest = p
            max_mem = mem
            break
    
    if heaviest:
        try:
            print(f"[TARGET IDENTIFIED] Will close VISIBLE TAB: PID={heaviest.pid}, Memory={max_mem:.2f}MB")
        except:
            pass
    else:
        print(f"[NO VISIBLE TAB FOUND] Only background processes detected or localhost protected")
    
    return heaviest if heaviest and max_mem > 50 else None
