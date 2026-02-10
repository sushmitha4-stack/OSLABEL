from flask import Flask, jsonify, render_template, request
import psutil
import os
import signal
import time
import subprocess
from monitor import (
    find_process, learn_baseline, get_process_data, 
    get_timestamp, find_heaviest_child_process, is_protected_process
)

app = Flask(__name__, template_folder='templates', static_folder='static')

# Global state
chrome_process = None
baseline_cpu = None
baseline_mem = None
initialized = False

def initialize():
    """Initialize process monitoring"""
    global chrome_process, baseline_cpu, baseline_mem, initialized
    
    if initialized:
        return True
    
    print("\n" + "="*60)
    print("INITIALIZING OS MONITOR")
    print("="*60)
    
    # Find Chrome
    print("\n[1] Searching for Chrome process...")
    chrome_process = find_process()
    
    if not chrome_process:
        print("[ERROR] Chrome not found. Please open Chrome and refresh the page.")
        return False
    
    try:
        pid = chrome_process.pid
        name = chrome_process.name()
        print(f"[SUCCESS] Found Chrome: {name} (PID: {pid})\n")
        
        # Learn baseline
        print("[2] Learning baseline metrics (3 samples)...")
        baseline_cpu, baseline_mem = learn_baseline(chrome_process)
        
        print("[3] Initialization complete!")
        print("="*60 + "\n")
        
        initialized = True
        return True
    except Exception as e:
        print(f"[ERROR] Initialization failed: {e}")
        return False

# -------- ROUTES --------
@app.route('/')
def index():
    """Serve dashboard"""
    if not initialized:
        initialize()
    return render_template('index.html')

@app.route('/data')
def get_data():
    """Get current process data"""
    global chrome_process, baseline_cpu, baseline_mem
    
    # Auto-initialize on first request
    if not initialized:
        if not initialize():
            return jsonify({
                "timestamp": get_timestamp(),
                "status": "ERROR",
                "message": "Chrome not found. Open Chrome and try again.",
                "cpu": 0,
                "memory": 0
            }), 500
    
    try:
        # Check if process still exists
        if chrome_process is None or not chrome_process.is_running():
            print("[WARN] Chrome process died, reinitializing...")
            chrome_process = find_process()
            if chrome_process:
                baseline_cpu, baseline_mem = learn_baseline(chrome_process)
            else:
                return jsonify({
                    "timestamp": get_timestamp(),
                    "status": "ERROR",
                    "message": "Chrome not found",
                    "cpu": 0,
                    "memory": 0
                }), 500
        
        # Get current data
        data = get_process_data(chrome_process, baseline_cpu, baseline_mem)
        data["timestamp"] = get_timestamp()
        
        # Add process info for modal
        if chrome_process:
            try:
                data["pid"] = chrome_process.pid
                data["process_name"] = chrome_process.name()
            except:
                data["pid"] = "unknown"
                data["process_name"] = "Chrome"
        else:
            data["pid"] = "unknown"
            data["process_name"] = "Chrome"
        
        return jsonify(data)
    
    except Exception as e:
        print(f"[ERROR] /data endpoint: {e}")
        return jsonify({
            "timestamp": get_timestamp(),
            "status": "ERROR",
            "message": str(e),
            "cpu": 0,
            "memory": 0
        }), 500

@app.route("/system")
def system_info():
    """Get system-wide info"""
    try:
        return jsonify({
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_percent": psutil.virtual_memory().percent,
            "processes": len(psutil.pids())
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug")
def debug():
    """Debug thresholds"""
    return jsonify({
        "baseline_cpu": baseline_cpu,
        "baseline_mem": baseline_mem,
        "absolute_cpu_threshold": 80.0,
        "absolute_mem_threshold": 3500.0,
        "initialized": initialized,
        "chrome_found": chrome_process is not None
    })

@app.route("/kill_process", methods=["POST"])
def kill_process():
    """Kill the heaviest Chrome tab process - Windows compatible"""
    global chrome_process
    
    try:
        print("\n" + "="*60)
        print("[USER CONFIRMED] Closing anomalous tab/process")
        print("="*60)
        
        if not chrome_process or not chrome_process.is_running():
            chrome_process = find_process()
        
        if not chrome_process:
            print("[ERROR] Chrome process not found")
            return jsonify({"success": False, "message": "Chrome not found"}), 404
        
        # Find the heaviest Chrome process to close
        target = find_heaviest_child_process(chrome_process)
        
        if not target:
            print("[ERROR] No suitable tab process found to close")
            return jsonify({"success": False, "message": "No tab process found"}), 404
        
        # SAFETY CHECK: Don't kill protected processes (Flask app, localhost)
        if is_protected_process(target):
            print("[BLOCKED] Target is a protected process (Flask/localhost)")
            print(f"[BLOCKED] Cannot close PID {target.pid} - dashboard protection active")
            return jsonify({"success": False, "message": "Cannot close localhost/Flask processes"}), 403
        
        try:
            target_name = target.name()
            target_pid = target.pid
            target_mem = target.memory_info().rss / (1024 * 1024)
            
            print(f"[CLOSING TAB] Target identified:")
            print(f"  Name: {target_name}")
            print(f"  PID: {target_pid}")
            print(f"  Memory: {target_mem:.2f}MB")
            
            # METHOD 1: Use Windows taskkill command (most reliable on Windows)
            print(f"[ACTION] Using taskkill to terminate PID {target_pid}...")
            result = subprocess.run(
                ["taskkill", "/PID", str(target_pid), "/F"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"[SUCCESS] Taskkill succeeded for PID {target_pid}")
                print("="*60)
                print("[RESULT] Tab successfully closed")
                print("="*60 + "\n")
                
                return jsonify({
                    "success": True,
                    "message": f"Tab closed successfully",
                    "closed_pid": target_pid,
                    "closed_name": target_name,
                    "closed_memory": round(target_mem, 2)
                })
            else:
                print(f"[WARN] Taskkill failed: {result.stderr}")
                print("[FALLBACK] Attempting psutil.kill()...")
                
                # Fallback to psutil
                try:
                    target.kill()
                    time.sleep(0.3)
                    print(f"[SUCCESS] psutil.kill() succeeded")
                    print("="*60)
                    print("[RESULT] Tab successfully closed")
                    print("="*60 + "\n")
                    
                    return jsonify({
                        "success": True,
                        "message": f"Tab closed successfully",
                        "closed_pid": target_pid,
                        "closed_name": target_name,
                        "closed_memory": round(target_mem, 2)
                    })
                except Exception as fallback_error:
                    print(f"[ERROR] psutil.kill() also failed: {fallback_error}")
                    raise fallback_error
        
        except ProcessLookupError:
            print("[SUCCESS] Process was already terminated")
            print("="*60 + "\n")
            return jsonify({"success": True, "message": "Tab was already closed"})
        
        except Exception as e:
            print(f"[ERROR] All termination methods failed: {e}")
            print(f"[ERROR TYPE] {type(e).__name__}")
            
            # Last resort: try gentle terminate
            try:
                print("[FINAL FALLBACK] Attempting gentle terminate()...")
                target.terminate()
                target.wait(timeout=1)
                print("[SUCCESS] Gentle terminate worked")
                print("="*60 + "\n")
                return jsonify({"success": True, "message": "Tab closed (gentle terminate)"})
            except Exception as final_error:
                print(f"[FAILED] Even gentle terminate failed: {final_error}")
                print("="*60 + "\n")
                return jsonify({
                    "success": False,
                    "message": f"Failed to close tab: {str(e)}"
                }), 500
    
    except Exception as e:
        print(f"[CRITICAL ERROR] Kill process endpoint: {e}")
        print("="*60 + "\n")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    print("\nStarting OS Monitor Dashboard...\n")
    app.run(debug=True, host='localhost', port=5000)
