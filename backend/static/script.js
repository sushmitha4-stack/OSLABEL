let cpuData = [];
let memData = [];
let labels = [];

const ctx = document.getElementById("usageChart").getContext("2d");

const usageChart = new Chart(ctx, {
    type: "line",
    data: {
        labels: labels,
        datasets: [
            {
                label: "CPU %",
                data: cpuData,
                borderColor: "#8b5cf6",
                tension: 0.4
            },
            {
                label: "Memory (MB)",
                data: memData,
                borderColor: "#22c55e",
                tension: 0.4
            }
        ]
    },
    options: {
        responsive: true,
        plugins: {
            legend: {
                labels: {
                    color: "#e5e7eb"
                }
            }
        },
        scales: {
            x: {
                ticks: { color: "#94a3b8" }
            },
            y: {
                ticks: { color: "#94a3b8" }
            }
        }
    }
});

function fetchData() {
    fetch("/data")
        .then(res => res.json())
        .then(data => {
            document.getElementById("cpu").innerText = data.cpu;
            document.getElementById("memory").innerText = data.memory;
            document.getElementById("status").innerText = data.status;
            document.getElementById("reason").innerText = data.reason;

            const statusBox = document.getElementById("statusBox");
            statusBox.className = "status-box " + data.status;

            const time = new Date().toLocaleTimeString();

            if (labels.length > 10) {
                labels.shift();
                cpuData.shift();
                memData.shift();
            }

            labels.push(time);
            cpuData.push(data.cpu);
            memData.push(data.memory);

            usageChart.update();
        });
}

setInterval(fetchData, 2000);
fetchData();
