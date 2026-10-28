# Adaptive Resource Quarantine (ARQ)

**An adaptive process-monitoring and resource-quarantine system with rule-based anomaly detection and shadow-mode machine learning.**

ARQ monitors running processes, evaluates resource-usage behavior, and applies graduated responses to anomalous processes. It combines an EWMA-based rule engine with an Isolation Forest machine-learning pipeline that can be evaluated alongside the existing detector.

The rule-based engine remains responsible for quarantine decisions. The ML detector currently operates in **shadow mode**, allowing its outputs to be compared with rule-based decisions without changing process enforcement.

## Key Features

- **Process telemetry collection:** Collects CPU, memory, I/O, and thread-related metrics.
- **Adaptive rule-based scoring:** Uses EWMA baselines and a weighted composite anomaly score.
- **Graduated quarantine:** Supports Normal, Watchlist, Soft Quarantine, Hard Quarantine, and Terminated stages.
- **Resource enforcement:** Uses process-priority adjustment and duty-cycle throttling where supported.
- **Automated restoration:** Uses hysteresis to avoid restoring processes based on a single low-anomaly reading.
- **Web dashboard:** Displays process information, anomaly scores, and quarantine states, with controls for supported operations.
- **Isolation Forest detector:** Provides a machine-learning-based anomaly signal alongside the existing rule-based detector.
- **Model training and evaluation:** Includes scripts for training, evaluating, and comparing detector behavior.
- **Automated tests:** Includes tests for core functionality and the ML pipeline.

## Architecture

```text
Running Processes
       |
       v
Process Telemetry Collector
       |
       v
Telemetry Feature Extraction
       |
       +---------------------------+
       |                           |
       v                           v
Rule-Based Anomaly Scorer     Isolation Forest
       |                           |
       v                           v
Quarantine State Machine     ML Score and Flag
       |                     (Shadow Mode)
       v                           |
Process Enforcement                v
       |                     Evaluation and
       v                     Comparison
Restoration Engine
       |
       v
Web Dashboard and Reports
```

**Important:** The rule-based score drives quarantine and restoration. ML output is used for monitoring and evaluation; it does not independently trigger enforcement.

## Machine-Learning Pipeline

The project includes an Isolation Forest model trained on seven process-telemetry features:

1. `cpu_percent`
2. `memory_rss_mb`
3. `memory_vms_mb`
4. `memory_growth_mb_s`
5. `io_read_kb_s`
6. `io_write_kb_s`
7. `num_threads`

Isolation Forest identifies observations that differ from the learned telemetry patterns. Its raw decision-function output is converted into an anomaly score for dashboard display and compared with a calibration threshold to produce an anomaly flag.

The displayed ML score is a **scaled anomaly score, not a calibrated probability**.

### Current ML Status

- ML inference is integrated into the dashboard backend.
- The existing rule-based detector remains the enforcement authority.
- Training and evaluation utilities are available in the repository.
- Active and candidate model artifacts are kept separate.
- Candidate models must be evaluated against normal and anomalous workloads before being considered for deployment.

## Project Structure

```text
quarant/
├── arq/
│   ├── cli.py
│   ├── core/
│   │   ├── process_model.py
│   │   ├── monitor.py
│   │   ├── anomaly_scorer.py
│   │   ├── quarantine_controller.py
│   │   ├── restoration_engine.py
│   │   ├── ml_pipeline.py
│   │   └── ml_training.py
│   └── web/
│       ├── server.py
│       └── static/
│           └── index.html
├── scripts/
│   ├── compare_detectors.py
│   ├── evaluate_ml_candidate.py
│   └── test_rule_features.py
├── tests/
│   ├── test_ml_pipeline.py
│   └── test_ml_training.py
├── models/
│   └── arq/
├── data/
├── requirements.txt
├── requirements-ml.txt
├── setup.py
└── README.md
```

Additional files and tests may be present in the repository.

## Installation

Clone the repository:

```bash
git clone https://github.com/vaishnavikarri08-crypto/adaptive-resource-quarantine.git
cd adaptive-resource-quarantine
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the ML dependencies when working with model training or ML evaluation:

```bash
python -m pip install -r requirements-ml.txt
```

If your environment is missing virtual-environment support, install the appropriate Python venv package for your Linux distribution first.

## Usage

### 1. Run the live demo

From the repository root, with the virtual environment activated:

```bash
python -m arq.cli demo
```

The demo exercises the quarantine lifecycle using a simulated workload. Review the terminal output to observe anomaly scoring, quarantine transitions, and restoration behavior.

### 2. Launch the web dashboard

```bash
python -m arq.cli web
```

Open the following address in your browser:

http://127.0.0.1:8080

The dashboard provides a view of monitored processes, telemetry, anomaly scores, and quarantine states. Available controls depend on the implementation and the permissions of the running environment.

### 3. Run the test suite

Run the project's tests using the commands supported by the current environment:

```bash
python -m pytest tests/ -v
```

For ML-specific tests:

```bash
python -m pytest tests/test_ml_pipeline.py tests/test_ml_training.py -v
```

### 4. Evaluate the detectors

The repository includes scripts for comparing detector behavior and evaluating candidate models:

```bash
python scripts/compare_detectors.py
python scripts/evaluate_ml_candidate.py
python scripts/test_rule_features.py
```

Check each script's options and prerequisites before running it. Evaluation results depend on the collected telemetry, workload scenarios, model artifact, and configuration.

## Rule-Based Anomaly Scoring

The rule-based engine uses exponentially weighted moving averages (EWMA) to track changing process behavior:

\[
\mu_t = \alpha x_t + (1-\alpha)\mu_{t-1}
\]

The documented baseline parameter is \(\alpha = 0.25\).

The composite anomaly score combines CPU, memory, I/O, and burst-related components:

\[
S = 0.40S_{\mathrm{cpu}} + 0.35S_{\mathrm{mem}}
+ 0.15S_{\mathrm{io}} + 0.10S_{\mathrm{burst}}
\]

The rule-based score feeds the existing quarantine state machine. State transitions, enforcement, and restoration behavior are determined by the corresponding implementation and configuration.

## Quarantine and Restoration

ARQ implements graduated process responses:

1. **Normal:** Process is monitored without quarantine restrictions.
2. **Watchlist:** Process receives increased attention.
3. **Soft Quarantine:** Initial resource restrictions are applied.
4. **Hard Quarantine:** Stronger restrictions are applied.
5. **Terminated:** A final response may be applied when configured conditions are met.

The restoration engine uses hysteresis to require sustained evidence of recovery before stepping down quarantine restrictions.

Exact thresholds, persistence settings, and enforcement behavior should be verified against the current source code and configuration rather than assumed from illustrative examples.

## Evaluation and Reporting

The project contains tooling to evaluate and compare detector behavior. Useful evaluation measures include:

- False-positive rate on normal workloads.
- Detection rate on anomalous workloads.
- Precision, recall, and F1-score when reliable labels are available.
- Detection delay.
- Agreement and disagreement between rule-based and ML detections.
- Resource and latency impact during quarantine.

Performance figures should be reported only when they have been reproduced using a documented dataset, workload, configuration, and evaluation procedure. Results from a limited telemetry sample should not be treated as general production guarantees.

## Current Limitations

- **Shadow-mode ML:** ML detections do not currently control quarantine enforcement.
- **Generalization:** Models trained on limited telemetry may not recognize every type of anomalous process behavior.
- **False positives and false negatives:** Model thresholds require validation against representative normal and anomalous workloads.
- **Platform differences:** Process telemetry and enforcement capabilities vary across operating systems.
- **Permissions:** Some process-control operations may require additional privileges or may be restricted by the operating system.
- **Safety:** Process termination and signal-based throttling can affect workload availability. Test with controlled processes before using the system on important workloads.

## Future Work

- Improve ML evaluation with broader, labeled workload datasets.
- Validate candidate models across different normal and anomalous process scenarios.
- Measure false-positive rates and detection performance over repeated trials.
- Improve agreement analysis between rule-based and ML detectors.
- Consider ML-assisted enforcement only after sufficient validation and safety testing.
- Improve portability and document platform-specific behavior.

## License

This project uses the MIT License. See [LICENSE](LICENSE) for details.
