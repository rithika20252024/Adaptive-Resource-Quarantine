# Adaptive Resource Quarantine (ARQ)

> **Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior**  
> *A closed-loop, lightweight OS framework that detects anomalous multi-resource consumption, applies graduated dynamic quarantine instead of blunt termination, and dynamically restores resources upon behavioral recovery.*

---

## Team & Academic Details
- **Project Title:** Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior
- **Course & Specialization:** B.Tech Computer Science and Engineering & B.Tech CSE (IoT)
- **Lab Slot:** L15 + L16
- **Students:**
  - **Rithika S** (Reg. No: 24BCE2984) · B.Tech CSE
  - **K. Vaishnavi** (Reg. No: 24BCT0183) · B.Tech CSE (IoT)
- **Faculty Guide:** Dr. Anisha M Lal · Department of Computer Science and Engineering

---

## Abstract
Modern operating systems run multiple processes simultaneously, and abnormal resource consumption by a single process can significantly affect overall system performance and stability. This project proposes an **Adaptive Resource Quarantine mechanism** that continuously monitors process behavior using CPU utilization, memory consumption, I/O activity, and execution patterns. When a process exhibits significantly abnormal behavior, the system assigns it an anomaly score and temporarily restricts its access to system resources instead of immediately terminating it. CPU priority, memory usage, and I/O access are dynamically controlled during the quarantine period. The process is continuously monitored and can be released when its behavior returns to normal or terminated if the abnormal behavior persists. The proposed system aims to provide lightweight process isolation while maintaining system availability and minimizing the impact of resource-intensive or potentially malicious processes.

---

## Objectives
1. **Continuous Telemetry:** Continuously monitor CPU, memory, and I/O resource usage of running processes.
2. **Multi-Vector Anomaly Scoring:** Identify abnormal process behavior using resource-consumption patterns and an anomaly scoring mechanism.
3. **Adaptive Quarantine:** Develop an adaptive quarantine mechanism that temporarily restricts resources allocated to abnormal processes.
4. **Neighbor Protection:** Prevent a single misbehaving process from significantly degrading the performance of other processes.
5. **Dynamic Restoration:** Dynamically restore normal resource allocation when the quarantined process returns to acceptable behavior.
6. **Empirical Evaluation:** Evaluate the effectiveness of the proposed mechanism using metrics such as CPU utilization, memory usage, response time, I/O performance, and system recovery time.
7. **Lightweight Alternative:** Provide a lightweight alternative to immediately terminating processes exhibiting abnormal resource behavior.

---

## The Closed-Loop Quarantine Architecture

```
   +------------------+
   |  1. MONITOR &    |  Continuous Telemetry (CPU%, RSS MB/s, IO, Burst)
   |     SCORE        |  Composite Score S ∈ [0.0, 1.0]
   +--------+---------+
            |  Anomaly Score S >= 0.65
            v
   +------------------+
   |  2. ADAPTIVE     |  Graduated Restriction: Nice +10/+19,
   |     QUARANTINE   |  CPU Duty-Cycle Throttling (40% / 15%), I/O priority
   +--------+---------+
            |  Continuous Re-evaluation
            v
   +------------------+
   |  3. CLOSED-LOOP  |  Hysteresis Stability Verification
   |     RE-EVALUATE  |  Is behavior normal (S < 0.40 for H cycles)?
   +--------+---------+
            |
      +-----+-----+
      |           |
      v           v
+-----------+ +------------+
| 4a.RELEASE| |4b.TERMINATE|
|  Restore  | | Persistent |
|  to Normal| | Abuse (T)  |
+-----------+ +------------+
```

---

## Review 1 PowerPoint Presentation
The complete 10-slide PowerPoint presentation formatted with the custom academic warm-cream and terracotta template is located in:
- **Presentation File:** [`presentation/Adaptive_Resource_Quarantine_Review_1.pptx`](presentation/Adaptive_Resource_Quarantine_Review_1.pptx)
- **Speaker Notes & Transcripts:** [`presentation/Review_1_Presentation_Notes.md`](presentation/Review_1_Presentation_Notes.md)
- **PPTX Generator Script:** [`presentation/generate_review1_pptx.py`](presentation/generate_review1_pptx.py)

---

## Experimental Benchmark Results

Running the comparative evaluation suite (`python -m arq.cli benchmark`) yields:

| Strategy | P95 Latency (ms) | P99 Latency (ms) | Throughput (req/s) | State Loss (%) | Process Preserved |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Unprotected Baseline** | 0.10 ms | 0.12 ms | 39.4 rps | 0% | Yes (Starves neighbors) |
| **Static Kill (CFS / OOM)** | 0.10 ms | 0.11 ms | 39.2 rps | **100%** | **No (Abruptly killed)** |
| **Adaptive Quarantine (ARQ)** | **0.13 ms** | **0.15 ms** | **40.0 rps** | **0%** | **Yes (Preserved & throttled)** |

---

## Quickstart & Usage

### 1. Requirements & Installation
ARQ is designed to be zero-dependency out-of-the-box (uses native `libproc` on macOS and `/proc` on Linux). Optional enhancements can be installed:

```bash
git clone https://github.com/rithika20252024/Adaptive-Resource-Quarantine.git
cd Adaptive-Resource-Quarantine
```

### 2. Run the Interactive CLI Demo
Experience real-time closed-loop detection, multi-stage throttling, and automatic restoration:

```bash
python3 -m arq.cli demo
```

### 3. Run the Comparative Evaluation Suite
Evaluate neighbor tail latency protection and state preservation:

```bash
python3 -m arq.cli benchmark --duration 4.0 --markdown
```

### 4. Launch the Real-Time Web Dashboard
Launch the live interactive web dashboard:

```bash
python3 -m arq.cli web --port 8080
```
Then open `http://localhost:8080` in any web browser to inject test workloads, inspect live anomaly scores, and test quarantine controls.

### 5. Regenerate Review 1 Presentation
Re-generate the 10-slide PowerPoint presentation anytime:

```bash
python3 -m arq.cli pptx
```

### 6. Run Automated Test Suite

```bash
python3 -m unittest discover tests
```

---

## Project Structure

```
Adaptive-Resource-Quarantine/
├── README.md                          # Main project guide & documentation
├── LICENSE                            # MIT License
├── setup.py                           # Python package definition
├── requirements.txt                   # Dependency definitions
├── presentation/
│   ├── Adaptive_Resource_Quarantine_Review_1.pptx  # Review 1 Presentation
│   ├── generate_review1_pptx.py       # Deterministic PPTX generator
│   └── Review_1_Presentation_Notes.md # Speaker script and slide transcripts
├── arq/
│   ├── core/
│   │   ├── monitor.py                 # Multi-vector telemetry collector
│   │   ├── anomaly_scorer.py          # Composite anomaly scoring engine
│   │   ├── quarantine_controller.py   # Graduated throttling actuator
│   │   ├── restoration_engine.py      # Closed-loop recovery & hysteresis
│   │   └── process_model.py           # Process profiles & lifecycle stages
│   ├── simulation/
│   │   ├── workloads.py               # Stress generator (CPU, Mem, IO, Burst)
│   │   └── noisy_neighbor.py          # Latency probe service
│   ├── evaluation/
│   │   ├── benchmark_runner.py        # 3-way comparative evaluation runner
│   │   ├── metrics.py                 # P95/P99 latency & MTTR metrics
│   │   └── report_generator.py        # Table and Markdown formatter
│   ├── web/
│   │   ├── server.py                  # Real-time HTTP dashboard server
│   │   └── static/
│   │       └── index.html             # Real-time monitoring UI
│   └── cli.py                         # Unified command line tool
├── tests/
│   ├── test_monitor.py
│   ├── test_anomaly_scorer.py
│   ├── test_quarantine.py
│   └── test_restoration.py
└── docs/
    ├── ARCHITECTURE.md                # Component diagrams and data flow
    ├── MATHEMATICAL_MODEL.md          # Anomaly scoring and EWMA formulas
    └── LITERATURE_REVIEW.md           # Review of 37 literature papers
```

---

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
