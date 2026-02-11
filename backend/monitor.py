import psutil
import statistics
from datetime import datetime
import os
import time

PROCESS_NAME = "chrome"
BASELINE_SAMPLES = 3      
ABSOLUTE_CPU_THRESHOLD = 500.0   
ABSOLUTE_MEM_THRESHOLD = 3000.0  # Only YouTube + 2+ videos
YOUTUBE_ANOMALY_PROCESS_COUNT = 8  # 8th YouTube tab triggers anomaly

non_localhost_tab_count = 0  # Track number of non-localhost Chrome processes (approximate tab count)
FLASK_APP_PID = os.getpid()  # Current Flask app PID (localhost:5000)
last_anomaly_time = 0  # Track last anomaly time to prevent spam  

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
    """Check if a process should be protected from closure (Flask app + localhost tabs)
    Protected processes:
    - Flask app itself (running localhost dashboard)
    - Any Python process (might be Flask)
    - Chrome tabs displaying localhost:5000 (the dashboard itself)
    """
    try:
        # Protect the Flask app process
        if p.pid == FLASK_APP_PID:
            return True
        
        # Protect any python process (might be Flask)
        if PROCESS_NAME.lower() not in p.name().lower():
            if 'python' in p.name().lower():
                return True
        
        # Protect Chrome tabs displaying localhost (the dashboard)
        if PROCESS_NAME.lower() in p.name().lower():
            try:
                cmdline = p.cmdline()
                cmdline_str = ' '.join(cmdline).lower()
                
                # Check for localhost URLs in various formats
                localhost_patterns = [
                    'localhost:5000',
                    '127.0.0.1:5000',
                    'localhost%3a5000',  # URL encoded
                    '127.0.0.1%3a5000',
                    'http://localhost',
                    'http://127.0.0.1',
                ]
                
                for pattern in localhost_patterns:
                    if pattern in cmdline_str:
                        print(f"[PROTECTED] Tab PID={p.pid} is displaying localhost dashboard")
                        return True
            except:
                pass
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
    """Identify if a Chrome process is an actual BROWSER TAB (renderer process)
    VERY STRICT filtering - only count actual user-visible tabs
    """
    try:
        # Get command line arguments to check process type
        cmdline = p.cmdline()
        cmdline_str = ' '.join(cmdline).lower()
        
        # MUST be a renderer process to be considered a tab
        if '--type=renderer' not in cmdline_str:
            return False
        
        # Background process types - EXCLUDE these even if they're renderers
        background_types = [
            '--type=gpu',
            '--type=utility', 
            '--type=plugin',
            '--type=service_worker',
            '--type=network',
            '--type=storage',
            '--type=zygote',
            '--type=ppapi',
            '--type=extension',
            '--type=crash-handler',
            '--type=broker',
            '--type=watcher',
            '--type=devtools',
            '--type=print',
        ]
        
        # Check if it's a background process type
        for bg_type in background_types:
            if bg_type in cmdline_str:
                return False
        
        # Only count if it has significant memory usage (real tabs use memory)
        try:
            mem_mb = p.memory_info().rss / (1024 * 1024)
            if mem_mb < 50:  # Less than 50MB is likely a background renderer
                return False
        except:
            return False
        
        # If we get here, it's likely a real browser tab
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
    EXCLUDES localhost tabs from anomaly detection.
    """
    actual_tabs = get_actual_browser_tabs()
    
    # Filter out localhost tabs for anomaly detection
    non_localhost_tabs = []
    for p in actual_tabs:
        try:
            if not is_protected_process(p):
                non_localhost_tabs.append(p)
        except:
            pass
    
    tab_count = len(non_localhost_tabs)
    
    print(f"\n[DEBUG] Total Chrome processes found: {len(get_all_chrome_processes())}")
    print(f"[DEBUG] Actual browser tabs (renderer): {len(actual_tabs)}")
    print(f"[DEBUG] Protected tabs (localhost): {len(actual_tabs) - len(non_localhost_tabs)}")
    print(f"[DEBUG] Non-localhost tabs for anomaly: {tab_count}")
    
    print(f"\n[ACTUAL TABS ONLY] Found {len(actual_tabs)} real browser tabs (renderer processes)")
    print(f"[ANOMALY DETECTION] {tab_count} non-localhost tabs counted (localhost excluded)")
    for i, p in enumerate(actual_tabs, 1):
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            protected = " (localhost - protected)" if is_protected_process(p) else ""
            print(f"  {i}. Tab: PID={p.pid}, Memory={mem:.1f}MB{protected}")
        except:
            pass
    print()
    
    return tab_count

def get_total_chrome_metrics():
    """Get TOTAL CPU, memory, and threads for ALL Chrome processes"""
    procs = get_all_chrome_processes()
    
    if not procs:
        return 0, 0, 0
    
    total_cpu = 0
    total_mem = 0
    total_threads = 0
    
    # Call cpu_percent() once first to initialize, then again for actual value
    for p in procs:
        try:
            p.cpu_percent()  # Initialize
        except:
            pass
    
    time.sleep(0.1)  # Small delay for accurate CPU measurement
    
    for p in procs:
        try:
            total_cpu += p.cpu_percent()  # Get actual CPU usage
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        try:
            total_mem += p.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        try:
            total_threads += p.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return total_cpu, total_mem, total_threads

def learn_baseline(process):
    """Learn baseline CPU and memory from ALL Chrome processes"""
    cpu_samples = []
    mem_samples = []

    for i in range(BASELINE_SAMPLES):
        try:
            cpu, mem, threads = get_total_chrome_metrics()
            
            cpu_samples.append(cpu)
            mem_samples.append(mem)
            print(f"[BASELINE {i+1}/{BASELINE_SAMPLES}] CPU: {cpu:.2f}%, Memory: {mem:.2f}MB, Threads: {threads}")
            
            if i < BASELINE_SAMPLES - 1:  # Don't sleep after last sample
                time.sleep(1.0)  # Wait 1 second between samples
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
    global last_anomaly_time
    try:
        # Get TOTAL metrics for all Chrome processes
        cpu, mem, threads = get_total_chrome_metrics()
        
        # Count VISIBLE TABS ONLY (filters background processes and localhost)
        visible_tab_count = get_visible_tab_count()

        # Simple thresholds
        cpu_anomaly = cpu > ABSOLUTE_CPU_THRESHOLD
        mem_anomaly = mem > ABSOLUTE_MEM_THRESHOLD
        # YouTube tab anomaly: 3+ VISIBLE tabs (not background processes, excludes localhost)
        youtube_anomaly = visible_tab_count >= YOUTUBE_ANOMALY_PROCESS_COUNT

        status = "NORMAL"
        reason = "Process operating normally"

        current_time = time.time()
        # Prevent anomaly spam - wait 30 seconds between tab count anomalies
        time_since_last = current_time - last_anomaly_time
        
        if (cpu_anomaly and mem_anomaly) or (youtube_anomaly and time_since_last > 30):  # Add cooldown
            status = "ANOMALY"
            if cpu_anomaly and mem_anomaly:
                reason = f"HIGH CPU & MEMORY: CPU {cpu:.1f}% + Memory {mem:.1f}MB (Visible tabs: {visible_tab_count})"
            elif cpu_anomaly:
                reason = f"HIGH CPU: {cpu:.1f}% (threshold: {ABSOLUTE_CPU_THRESHOLD}%) - {visible_tab_count} visible tabs"
            elif mem_anomaly:
                reason = f"HIGH MEMORY: {mem:.1f}MB (threshold: {ABSOLUTE_MEM_THRESHOLD}MB) - {visible_tab_count} visible tabs"
            elif youtube_anomaly:
                reason = f"HIGH TAB COUNT: {visible_tab_count} VISIBLE tabs detected (8+ tab anomaly) - Recommended: Close most recent YouTube tab"
                last_anomaly_time = current_time  # Update last anomaly time
            
            print(f"[ANOMALY DETECTED] {reason}")
            print(f"[VISIBLE TAB COUNT] {visible_tab_count} actual tabs detected (background processes excluded)")
        
        return {
            "cpu": round(cpu, 2),
            "memory": round(mem, 2),
            "threads": threads,
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
            "threads": 0,
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
