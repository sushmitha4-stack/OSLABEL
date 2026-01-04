from flask import Flask, jsonify, render_template
import monitor

app = Flask(__name__)

# -------- INITIAL SETUP --------
process = monitor.find_process()

if not process:
    print("Process not found")
    exit()

avg_cpu, avg_mem = monitor.learn_baseline(process)

# -------- ROUTES --------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    data = monitor.get_process_data(process, avg_cpu, avg_mem)
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
