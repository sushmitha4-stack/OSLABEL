// Data storage
let cpuData = [];
let memData = [];
let labels = [];
let baselineCPU = null;
let lastAnomalyShown = null;
let alarmPlaying = false;

// Comprehensive alarm sound function
function playAlarmSound() {
    if (alarmPlaying) return;
    alarmPlaying = true;
    
    // Create a more effective alarm using Web Audio API
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    // Set frequency pattern for alarm sound
    oscillator.frequency.value = 800; // Hz
    oscillator.type = 'sine';
    
    // Volume
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.5);
    
    // Play alarm 3 times with pauses
    setTimeout(() => {
        const osc2 = audioContext.createOscillator();
        const gain2 = audioContext.createGain();
        osc2.connect(gain2);
        gain2.connect(audioContext.destination);
        osc2.frequency.value = 1000;
        osc2.type = 'sine';
        gain2.gain.setValueAtTime(0.3, audioContext.currentTime);
        gain2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        osc2.start(audioContext.currentTime);
        osc2.stop(audioContext.currentTime + 0.5);
    }, 600);
    
    setTimeout(() => {
        const osc3 = audioContext.createOscillator();
        const gain3 = audioContext.createGain();
        osc3.connect(gain3);
        gain3.connect(audioContext.destination);
        osc3.frequency.value = 800;
        osc3.type = 'sine';
        gain3.gain.setValueAtTime(0.3, audioContext.currentTime);
        gain3.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        osc3.start(audioContext.currentTime);
        osc3.stop(audioContext.currentTime + 0.5);
        alarmPlaying = false;
    }, 1200);
}

// Show anomaly modal
function showAnomalyModal(data) {
    // Prevent showing the same anomaly multiple times
    if (lastAnomalyShown && Date.now() - lastAnomalyShown < 30000) {
        return;
    }
    
    lastAnomalyShown = Date.now();
    
    // Update modal content
    document.getElementById("anomalyReason").innerText = data.reason;
    document.getElementById("anomalyProcess").innerText = data.process_name || "Chrome";
    document.getElementById("anomalyPID").innerText = data.pid || "--";
    document.getElementById("anomalyCPU").innerText = data.cpu;
    document.getElementById("anomalyMemory").innerText = data.memory;
    
    // Show modal
    const modal = document.getElementById("anomalyModal");
    modal.classList.add("show");
    
    // Play alarm
    playAlarmSound();
}

// Close anomaly modal
function closeAnomalyModal() {
    const modal = document.getElementById("anomalyModal");
    modal.classList.remove("show");
}

// Setup modal event listeners
document.getElementById("dismissBtn").addEventListener("click", function() {
    closeAnomalyModal();
});

document.getElementById("closeTaskBtn").addEventListener("click", function() {
    const pid = document.getElementById("anomalyPID").innerText;
    const processName = document.getElementById("anomalyProcess").innerText;
    const cpuValue = document.getElementById("anomalyCPU").innerText;
    const memValue = document.getElementById("anomalyMemory").innerText;
    
    console.log("%c=== USER CONFIRMED TAB CLOSURE ===", "color: #00ff00; font-weight: bold; font-size: 14px;");
    console.log(`Timestamp: ${new Date().toLocaleTimeString()}`);
    console.log(`Target Process: ${processName} (PID: ${pid})`);
    console.log(`Current CPU: ${cpuValue}% | Current Memory: ${memValue}MB`);
    console.log("%cSending closure request to backend...","color: #ffff00;");
    
    if (pid && pid !== "--") {
        // Change button text to show loading state
        const btn = document.getElementById("closeTaskBtn");
        const originalText = btn.innerText;
        btn.innerText = "⏳ Closing tab...";
        btn.disabled = true;
        
        // Send request to kill the heaviest child process (tab)
        fetch("/kill_process", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ pid: parseInt(pid) })
        })
        .then(res => {
            console.log(`%cResponse received from backend (Status: ${res.status})`, "color: #00aaff;");
            return res.json();
        })
        .then(data => {
            console.log("%cBackend response data:", "color: #00aaff;", data);
            btn.innerText = originalText;
            btn.disabled = false;
            
            if (data.success) {
                console.log("%c✅ TAB SUCCESSFULLY CLOSED", "color: #00ff00; font-weight: bold; font-size: 14px;");
                console.log(`Closed PID: ${data.closed_pid}`);
                console.log(`Closed Process: ${data.closed_name}`);
                console.log(`Previous Memory Usage: ${data.closed_memory}MB`);
                console.log(`Message: ${data.message}`);
                
                // Success - show which tab was closed
                alert("✅ " + data.message + "\n\nℹ️ Your dashboard tab remains open!\n\nℹ️ Monitoring will continue. If anomaly persists, the next heavy tab will be targeted.");
                closeAnomalyModal();
            } else {
                console.log("%c⚠️ Tab closure attempt failed", "color: #ff6600;");
                console.log(`Error: ${data.message}`);
                alert("⚠️ " + data.message + "\n\n💡 If anomaly continues, click the button again to close the next heavy tab.");
                btn.innerText = originalText;
                btn.disabled = false;
            }
        })
        .catch(err => {
            console.error("%c❌ CRITICAL ERROR", "color: #ff0000; font-weight: bold;", err);
            btn.innerText = originalText;
            btn.disabled = false;
            alert("❌ Could not close the tab: " + err.message);
        });
    } else {
        console.error("%c❌ INVALID PID", "color: #ff0000; font-weight: bold;");
        alert("❌ Process ID not available");
    }
});

// Close modal when clicking outside
document.getElementById("anomalyModal").addEventListener("click", function(e) {
    if (e.target === this) {
        closeAnomalyModal();
    }
});

// Chart configuration
const ctx = document.getElementById("usageChart").getContext("2d");

const usageChart = new Chart(ctx, {
    type: "line",
    data: {
        labels: labels,
        datasets: [
            {
                label: "CPU %",
                data: cpuData,
                borderColor: "#6366f1",
                backgroundColor: "rgba(99, 102, 241, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: "#6366f1",
                pointBorderColor: "#fff",
                pointBorderWidth: 2
            },
            {
                label: "Memory (MB)",
                data: memData,
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: "#10b981",
                pointBorderColor: "#fff",
                pointBorderWidth: 2
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            intersect: false,
            mode: 'index'
        },
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    color: "#cbd5e1",
                    padding: 15,
                    font: {
                        size: 13,
                        weight: 600
                    },
                    usePointStyle: true
                }
            },
            tooltip: {
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                titleColor: "#f1f5f9",
                bodyColor: "#cbd5e1",
                borderColor: "#475569",
                borderWidth: 1,
                padding: 12,
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 13 }
            }
        },
        scales: {
            x: {
                grid: {
                    color: "rgba(71, 85, 105, 0.2)"
                },
                ticks: {
                    color: "#94a3b8",
                    font: { size: 12 }
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: "rgba(71, 85, 105, 0.2)"
                },
                ticks: {
                    color: "#94a3b8",
                    font: { size: 12 }
                }
            }
        }
    }
});

// Track previous values for trend calculation
let prevCPU = null;
let prevMem = null;

function getTrendIndicator(current, previous) {
    if (previous === null) return "→";
    if (current > previous) return "📈";
    if (current < previous) return "📉";
    return "→";
}

function getStatusColor(status) {
    switch(status) {
        case "NORMAL":
            return "#10b981"; // Green
        case "ANOMALY":
            return "#ef4444"; // Red
        case "WAITING":
            return "#f59e0b"; // Amber
        case "ERROR":
            return "#ef4444"; // Red
        default:
            return "#94a3b8"; // Gray
    }
}

function fetchData() {
    fetch("/data")
        .then(res => res.json())
        .then(data => {
            // Update main metrics
            document.getElementById("cpu").innerText = data.cpu;
            document.getElementById("memory").innerText = data.memory;
            document.getElementById("status").innerText = data.status;
            document.getElementById("reason").innerText = data.reason;
            document.getElementById("timestamp").innerText = "Last updated: " + (data.timestamp || new Date().toLocaleTimeString());
            
            // Update process info
            document.getElementById("processName").innerText = data.process_name || "--";
            document.getElementById("pid").innerText = data.pid || "--";
            document.getElementById("threads").innerText = data.threads || "--";

            // Update status box styling
            const statusBox = document.getElementById("statusBox");
            const statusDot = document.getElementById("statusDot");
            const statusText = document.getElementById("statusText");
            
            statusBox.className = "status-box " + data.status;
            statusDot.className = "status-dot " + data.status;
            statusText.innerText = data.status;
            statusDot.style.borderColor = getStatusColor(data.status);

            // SHOW ANOMALY ALERT AND PLAY ALARM
            if (data.status === "ANOMALY") {
                showAnomalyModal(data);
            }

            // Update trend indicators - only if we have valid data
            if (data.status === "NORMAL" || data.status === "ANOMALY") {
                document.getElementById("cpuTrend").innerText = getTrendIndicator(data.cpu, prevCPU);
                document.getElementById("memTrend").innerText = getTrendIndicator(data.memory, prevMem);
            } else {
                document.getElementById("cpuTrend").innerText = "⏳";
                document.getElementById("memTrend").innerText = "⏳";
            }

            // Store baseline CPU on first load
            if (baselineCPU === null && data.status === "NORMAL") {
                baselineCPU = data.cpu;
            }

            // Update stats
            if (baselineCPU !== null) {
                document.getElementById("baselineCPU").innerText = baselineCPU.toFixed(2) + "%";
                const ratio = (data.cpu / baselineCPU).toFixed(2);
                document.getElementById("cpuRatio").innerText = ratio + "x";
            } else {
                document.getElementById("baselineCPU").innerText = "--";
                document.getElementById("cpuRatio").innerText = "--";
            }
            
            document.getElementById("updateTime").innerText = new Date().toLocaleTimeString();

            // Update chart data only for valid readings
            if (data.status === "NORMAL" || data.status === "ANOMALY") {
                const time = new Date().toLocaleTimeString();

                if (labels.length > 20) {
                    labels.shift();
                    cpuData.shift();
                    memData.shift();
                }

                labels.push(time);
                cpuData.push(data.cpu);
                memData.push(data.memory);

                usageChart.update();

                // Update previous values for next comparison
                prevCPU = data.cpu;
                prevMem = data.memory;
            }
        })
        .catch(err => {
            console.error("Error fetching data:", err);
            document.getElementById("status").innerText = "ERROR";
            document.getElementById("reason").innerText = "Failed to fetch data from server";
            document.getElementById("statusBox").className = "status-box ERROR";
            document.getElementById("statusDot").className = "status-dot ERROR";
        });
}

// Fetch data on page load and then every 2 seconds
document.addEventListener("DOMContentLoaded", function() {
    fetchData();
    setInterval(fetchData, 2000);
});
