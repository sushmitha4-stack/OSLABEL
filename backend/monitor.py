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

def is_chrome_tab_process(p):
    """Identify if a Chrome process is an actual VISIBLE BROWSER TAB
    Returns True ONLY for renderer processes that are actual user-visible tabs.
    
    Filters:
    - Must be a renderer process (--type=renderer)
    - Must have significant memory (>30MB indicates real tab with content)
    - Not a background service, extension, or utility process
    """
    try:
        # Get command line arguments to check process type
        cmdline = p.cmdline()
        cmdline_str = ' '.join(cmdline).lower()
        
        # Must be a renderer process
        if '--type=renderer' not in cmdline_str:
            return False
        
        # Background process types that we must explicitly exclude even if they're renderers
        background_types = [
            '--type=extension',  # Extension background pages
            '--type=service_worker',  # Service workers (might have --type=renderer too)
            '--type=utility',  # Utility processes
            '--type=plugin',  # Plugins
        ]
        
        for bg_type in background_types:
            if bg_type in cmdline_str:
                return False
        
        # Get memory to filter out tiny background renderers
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            # Real tabs typically have >30MB memory (content + DOM)
            # Tiny renderers (<30MB) are usually PDFs, forms, iframes, etc.
            if mem < 30:
                return False
        except:
            pass
        
        # All checks passed - this is a real visible tab
        return True
    
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    except Exception as e:
        return False

def get_actual_browser_tabs():
    """Get ONLY actual browser tabs (renderer processes visible in taskbar)
    Excludes ALL background processes, utilities, workers, extensions, GPU, etc.
    """
    procs = get_all_chrome_processes()
    
    if not procs:
        return []
    
    actual_tabs = []
    for p in procs:
        try:
            if is_chrome_tab_process(p):
                actual_tabs.append(p)
        except:
            pass
    
    return actual_tabs

def get_visible_tab_count():
    """Count only ACTUAL BROWSER TABS (renderer processes)
    No dummy values, no background processes - ONLY tabs visible in taskbar.
    """
    actual_tabs = get_actual_browser_tabs()
    
    tab_count = len(actual_tabs)
    
    print(f"\n[ACTUAL TABS ONLY] Found {tab_count} real browser tabs (renderer processes)")
    for i, p in enumerate(actual_tabs, 1):
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            print(f"  {i}. Tab: PID={p.pid}, Memory={mem:.1f}MB")
        except:
            pass
    print()
    
    return tab_count

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
    """Get current process data and detect anomalies (from ALL Chrome processes)
    IMPORTANT: Only trigger anomaly if there are actually visible tabs open!
    """
    try:
        # Get TOTAL metrics for all Chrome processes
        cpu, mem = get_total_chrome_metrics()
        
        # Count VISIBLE TABS ONLY (actual browser tabs in taskbar)
        visible_tab_count = get_visible_tab_count()

        status = "NORMAL"
        reason = "Process operating normally"
        
        # RULE 1: If NO visible tabs, never trigger anomaly (nothing to close anyway)
        if visible_tab_count == 0:
            print(f"[NO ANOMALY] 0 visible tabs detected - ignoring CPU/Memory readings")
            reason = "No visible tabs detected (Chrome idle or background only)"
            return {
                "cpu": round(cpu, 2),
                "memory": round(mem, 2),
                "status": status,
                "reason": reason,
                "process_count": visible_tab_count,
                "note": "0 visible tabs = no anomaly possible"
            }
        
        # RULE 2: If visible tabs exist, check for resource anomalies
        cpu_anomaly = cpu > ABSOLUTE_CPU_THRESHOLD
        mem_anomaly = mem > ABSOLUTE_MEM_THRESHOLD
        youtube_anomaly = visible_tab_count >= YOUTUBE_ANOMALY_PROCESS_COUNT

        # Only trigger if there are ACTUAL visible tabs AND high resources
        if (cpu_anomaly or mem_anomaly) or (youtube_anomaly and cpu > 20):
            status = "ANOMALY"
            if cpu_anomaly and mem_anomaly:
                reason = f"HIGH CPU & MEMORY: CPU {cpu:.1f}% + Memory {mem:.1f}MB with {visible_tab_count} visible tabs"
            elif cpu_anomaly:
                reason = f"HIGH CPU: {cpu:.1f}% (threshold: {ABSOLUTE_CPU_THRESHOLD}%) with {visible_tab_count} visible tabs"
            elif mem_anomaly:
                reason = f"HIGH MEMORY: {mem:.1f}MB (threshold: {ABSOLUTE_MEM_THRESHOLD}MB) with {visible_tab_count} visible tabs"
            elif youtube_anomaly:
                reason = f"HIGH TAB COUNT: {visible_tab_count} VISIBLE tabs detected (3+ tab anomaly) - Recommended: Close most recent YouTube tab"
            
            print(f"[ANOMALY DETECTED] {reason}")
            print(f"[VISIBLE TAB COUNT] {visible_tab_count} actual tabs detected")
        
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
    """Find the HEAVIEST BROWSER TAB to close
    ONLY terminates actual browser tabs (renderer processes visible in taskbar)
    EXCLUDES: localhost, background processes, utilities, workers, extensions, GPU, etc.
    """
    print("\n[TAB CLOSURE] Looking for heaviest browser tab to close...")
    
    actual_tabs = get_actual_browser_tabs()
    
    if not actual_tabs:
        print("[NO TABS FOUND] No actual browser tabs available to close")
        print("[PROTECTED] All processes are background services or localhost\n")
        return None
    
    # Get memory for each actual tab
    tab_memory = []
    for p in actual_tabs:
        try:
            if is_protected_process(p):
                print(f"[PROTECTED] Skipping tab PID={p.pid} (localhost protected)")
                continue
            
            mem = p.memory_info().rss / (1024 * 1024)
            tab_memory.append((p, mem))
        except:
            pass
    
    if not tab_memory:
        print("[NO CLOSEABLE TABS] All tabs are protected\n")
        return None
    
    # Sort by memory (find heaviest tab)
    tab_memory.sort(key=lambda x: x[1], reverse=True)
    
    print(f"[ACTUAL TABS] Found {len(tab_memory)} real browser tabs:")
    for i, (p, mem) in enumerate(tab_memory, 1):
        try:
            label = "← WILL CLOSE" if i == 1 else ""
            print(f"  {i}. {mem:.1f}MB {label}")
        except:
            pass
    
    # Return the heaviest tab
    if tab_memory:
        heaviest_p, heaviest_mem = tab_memory[0]
        try:
            print(f"[TARGET] Closing heaviest tab: PID={heaviest_p.pid}, Memory={heaviest_mem:.1f}MB")
        except:
            pass
        print()
        return heaviest_p
    
    print()
    return None
