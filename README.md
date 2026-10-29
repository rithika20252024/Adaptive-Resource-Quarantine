# Adaptive Resource Quarantine (ARQ)

**An adaptive process-monitoring and resource-quarantine system with rule-based anomaly detection and shadow-mode machine learning.**

ARQ monitors running processes, evaluates resource-usage behavior, and applies graduated responses to anomalous processes. It combines an EWMA-based rule engine with an Isolation Forest machine-learning pipeline that can be evaluated alongside the existing detector.

The rule-based engine remains responsible for quarantine decisions. The ML detector currently operates in **shadow mode**, allowing its outputs to be compared with rule-based decisions without changing process enforcement.

## Key Features

| Feature | Description |
|---|---|
| Process Telemetry Collection | Collects CPU, memory, I/O, and thread-related metrics. |
| Adaptive Rule-Based Scoring | Uses EWMA baselines and a weighted composite anomaly score. |
| Graduated Quarantine | Supports Normal, Watchlist, Soft Quarantine, Hard Quarantine, and Terminated stages. |
| Resource Enforcement | Uses process-priority adjustment and duty-cycle throttling where supported. |
| Automated Restoration | Uses hysteresis to avoid restoring processes based on a single low-anomaly reading. |
| Web Dashboard | Displays process information, anomaly scores, and quarantine states. |
| Isolation Forest Detector | Provides a machine-learning anomaly signal alongside the rule-based detector. |
| Model Training and Evaluation | Includes scripts for training, evaluating, and comparing detector behavior. |
| Automated Tests | Includes tests for core functionality and the ML pipeline. |

## Project Novelty and Contributions

The key contribution of ARQ is its approach to handling anomalous process behavior through graduated resource restrictions and recovery rather than relying only on detection or immediate process termination.

The project's main contributions are:

- **Graduated response mechanism:** Organizes process responses into multiple stages, from normal monitoring to increasingly restrictive quarantine.
- **Adaptive behavioral baselines:** Uses Exponentially Weighted Moving Average (EWMA) baselines to track changing process behavior and support anomaly scoring.
- **Hysteresis-based restoration:** Requires sustained evidence of recovery before reducing quarantine restrictions.
- **Complementary ML evaluation:** Integrates an Isolation Forest detector in shadow mode so its anomaly signals can be compared with the rule-based detector without directly controlling enforcement.

These contributions describe the current implementation and its combination of techniques; they do not imply that each individual technique is novel in isolation.

## Architecture

ARQ follows a modular architecture combining adaptive rule-based anomaly detection with a machine-learning detector operating in shadow mode.

```text
┌─────────────────────────────────────────────┐
│          1. PROCESS MONITORING               │
│       Running and simulated processes        │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│          2. TELEMETRY COLLECTION             │
│       CPU, memory, I/O, thread metrics       │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│          3. FEATURE EXTRACTION               │
│     Prepare process telemetry for analysis   │
└──────────────────────┬──────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────────┐ ┌──────────────────────┐
│ 4A. RULE-BASED       │ │ 4B. ISOLATION FOREST  │
│ ANOMALY SCORER       │ │ ML DETECTOR           │
│                      │ │                      │
│ EWMA baselines and   │ │ Seven telemetry      │
│ composite score      │ │ features, score/flag  │
└──────────┬───────────┘ └──────────┬───────────┘
           │                        │
           ▼                        ▼
┌──────────────────────┐ ┌──────────────────────┐
│ 5. QUARANTINE        │ │ ML EVALUATION        │
│ STATE MACHINE        │ │ AND COMPARISON       │
│                      │ │                      │
│ Rule-based score     │ │ Shadow-mode output   │
│ controls transitions │ │ does not enforce     │
└──────────┬───────────┘ └──────────┬───────────┘
           │                        │
           ▼                        │
┌──────────────────────┐             │
│ 6. ENFORCEMENT       │             │
│ CONTROLLER           │             │
│ Priority adjustment  │             │
│ and CPU throttling   │             │
└──────────┬───────────┘             │
           ▼                        │
┌──────────────────────┐             │
│ 7. RESTORATION       │             │
│ ENGINE               │             │
│ Hysteresis-based     │             │
│ recovery              │             │
└──────────┬───────────┘             │
           └────────────┬────────────┘
                        ▼
┌─────────────────────────────────────────────┐
│          8. WEB DASHBOARD AND REPORTING      │
│  Process status, scores, stages and results  │
└─────────────────────────────────────────────┘
```

**Architecture note:** The rule-based detector controls quarantine, enforcement, and restoration. The Isolation Forest detector runs in shadow mode and provides additional anomaly signals for evaluation without independently triggering enforcement.

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

## System Modules and Inputs/Outputs

| Module | Input | Output |
|---|---|---|
| Process Monitor | Running processes | Process identifiers and telemetry samples |
| Feature Extraction | Raw process metrics | Structured feature vectors |
| Rule-Based Anomaly Scorer | Process metrics and EWMA baselines | Rule-based anomaly score |
| Isolation Forest | Seven telemetry features | ML anomaly score and anomaly flag |
| Quarantine State Machine | Rule-based score and current state | Quarantine stage |
| Enforcement Controller | Quarantine stage | Resource restriction actions |
| Restoration Engine | Current stage and recovery observations | Restoration or step-down decision |
| Dashboard and Reporting | Telemetry, scores, stages, and ML output | Visual status and diagnostic results |

## Machine-Learning Pipeline

The project includes an Isolation Forest model using seven process-telemetry features:

1. `cpu_percent`
2. `memory_rss_mb`
3. `memory_vms_mb`
4. `memory_growth_mb_s`
5. `io_read_kb_s`
6. `io_write_kb_s`
7. `num_threads`

Isolation Forest identifies observations that differ from learned telemetry patterns. Its decision-function output is compared with a calibration threshold to produce an anomaly flag and is scaled for dashboard display.

**The displayed ML score is a scaled anomaly score, not a calibrated probability.**

### Current ML Status

- ML inference is integrated into the dashboard backend.
- The rule-based detector remains the enforcement authority.
- Training and evaluation utilities are available in the repository.
- Active and candidate model artifacts are kept separate.
- Candidate models require evaluation against normal and anomalous workloads before being considered for deployment.

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

## Usage

### 1. Run the Live Demo

```bash
python -m arq.cli demo
```

The demo exercises the quarantine lifecycle using a simulated workload. Review the terminal output to observe anomaly scoring, quarantine transitions, and restoration behavior.

### 2. Launch the Web Dashboard

```bash
python -m arq.cli web
```

Open the dashboard at:

http://127.0.0.1:8080

The dashboard provides a view of monitored processes, telemetry, anomaly scores, and quarantine states. Available controls depend on the implementation and permissions of the running environment.

### 3. Run the Test Suite

```bash
python -m pytest tests/ -v
```

For ML-specific tests:

```bash
python -m pytest tests/test_ml_pipeline.py tests/test_ml_training.py -v
```

### 4. Evaluate the Detectors

```bash
python scripts/compare_detectors.py
python scripts/evaluate_ml_candidate.py
python scripts/test_rule_features.py
```

Evaluation results depend on the collected telemetry, workload scenarios, model artifacts, and configuration.

## Rule-Based Anomaly Scoring

The rule-based engine uses an Exponentially Weighted Moving Average (EWMA) to track changing process behavior:

\[
\mu_t = \alpha x_t + (1-\alpha)\mu_{t-1}
\]

where:

- \(\mu_t\) is the updated baseline at time \(t\).
- \(x_t\) is the current observation.
- \(\mu_{t-1}\) is the previous baseline.
- \(\alpha = 0.25\) is the documented smoothing factor.

The composite anomaly score combines CPU, memory, I/O, and burst-related components:

\[
\begin{aligned}
S ={}& 0.40S_{\mathrm{cpu}} + 0.35S_{\mathrm{mem}}\\
&+ 0.15S_{\mathrm{io}} + 0.10S_{\mathrm{burst}}
\end{aligned}
\]

The rule-based score feeds the quarantine state machine. State transitions, enforcement, and restoration behavior follow the implementation and configuration.

## Quarantine and Restoration

ARQ implements graduated process responses:

1. **Normal:** Process is monitored without quarantine restrictions.
2. **Watchlist:** Process receives increased attention.
3. **Soft Quarantine:** Initial resource restrictions are applied.
4. **Hard Quarantine:** Stronger restrictions are applied.
5. **Terminated:** A final response may be applied when configured conditions are met.

The restoration engine uses hysteresis to require sustained evidence of recovery before stepping down quarantine restrictions.

Exact thresholds, persistence settings, and enforcement behavior should be verified against the current source code and configuration.

## Experimental Benchmark Results

The following results were obtained from a single benchmark run using:

```bash
python -m arq.cli benchmark --duration 6.0 --markdown
```

| Strategy | Median Latency (ms) | P95 Latency (ms) | P99 Latency (ms) | Throughput (req/s) | State Loss | Process Status |
|---|---:|---:|---:|---:|---:|---|
| Unprotected Baseline | 0.09 | 0.16 | 0.43 | 49.2 | 0% | Preserved |
| Static Kill (CFS/OOM) | 0.16 | 0.29 | 0.35 | 48.9 | 100% | Terminated |
| Adaptive Quarantine (ARQ) | 0.13 | 0.26 | 0.37 | 48.9 | 0% | Preserved |

### Benchmark Observations

- **Process preservation:** ARQ recorded 0% state loss in this run, while the static-kill strategy recorded 100%.
- **P95 latency:** ARQ measured 0.26 ms, compared with 0.16 ms for the unprotected baseline and 0.29 ms for static kill.
- **P99 latency:** ARQ measured 0.37 ms, compared with 0.43 ms for the baseline and 0.35 ms for static kill.
- **Throughput:** ARQ and static kill measured 48.9 requests per second, compared with 49.2 for the baseline.

These results represent one short benchmark run. Repeated trials under controlled conditions are needed to establish whether the observed differences are consistent.

## Machine-Learning Evaluation Results

The ML evaluation scripts were run against 1,164 previously collected normal telemetry observations and seven synthetic scenarios. The original and candidate Isolation Forest models use separate calibration thresholds.

### Normal Telemetry Flag Rates

| Model | Normal Observations | Flagged as Anomalous | Flag Rate |
|---|---:|---:|---:|
| Original Isolation Forest | 1,164 | 1,164 | 100.0% |
| Candidate Isolation Forest | 1,164 | 30 | 2.6% |

The candidate model substantially reduced the anomaly flag rate on the collected normal telemetry. However, a lower flag rate alone does not establish better overall detection accuracy; missed anomalies must also be considered.

### Synthetic Scenario Comparison

| Scenario | Original Model | Candidate Model | Rule-Based Score |
|---|---|---|---:|
| Baseline | Flagged | Not flagged | 0.00201 |
| High CPU | Flagged | Not flagged | 0.78552 |
| Rapid memory growth | Flagged | Not flagged | 0.11050 |
| Large memory footprint | Flagged | Flagged | 0.15566 |
| High disk I/O | Flagged | Not flagged | 0.85000 |
| High thread count | Flagged | Not flagged | 0.00201 |
| Combined stress | Flagged | Flagged | 0.85000 |

The rule-based scores are raw composite scores, not probabilities. The threshold context printed by the comparison script is 0.50.

### Interpretation

The candidate model reduced flags on the collected normal telemetry but missed several isolated synthetic stress scenarios. It flagged the large-memory and combined-stress scenarios in this evaluation.

The original model flagged every normal observation in the collected dataset, demonstrating a severe false-positive problem for that dataset and calibration threshold.

These synthetic tests are exploratory and do not establish real-world precision, recall, or F1-score.

## Confusion Matrix and Evaluation Metrics

A confusion matrix can be used to evaluate either detector against labelled test data.

|  | Actual Anomalous | Actual Normal |
|---|---:|---:|
| **Predicted Anomalous** | True Positive (TP) | False Positive (FP) |
| **Predicted Normal** | False Negative (FN) | True Negative (TN) |

The following metrics can be calculated when reliable labels are available:

| Metric | Formula | Purpose |
|---|---|---|
| Precision | TP / (TP + FP) | Proportion of predicted anomalies that are actual anomalies |
| Recall | TP / (TP + FN) | Proportion of actual anomalies detected |
| F1-score | 2TP / (2TP + FP + FN) | Harmonic mean of precision and recall |
| False Positive Rate | FP / (FP + TN) | Proportion of normal samples incorrectly flagged |

Precision, recall, and F1-score are not reported here because the supplied evaluation outputs do not provide a labelled confusion matrix. Unlabelled normal telemetry can estimate a flag rate, but cannot establish the full detection accuracy.

## Current Limitations

- **Shadow-mode ML:** ML detections do not currently control quarantine enforcement.
- **Generalization:** Models trained on limited telemetry may not recognize every type of anomalous process behavior.
- **False positives and false negatives:** Model thresholds require validation against representative normal and anomalous workloads.
- **Platform differences:** Process telemetry and enforcement capabilities vary across operating systems.
- **Permissions:** Some process-control operations may require additional privileges or may be restricted by the operating system.
- **Benchmark scope:** The reported benchmark is a single short run and should not be treated as a general performance guarantee.
- **Synthetic evaluation:** Synthetic scenarios do not replace testing on a representative labelled dataset.
- **Safety:** Process termination and signal-based throttling can affect workload availability. Test with controlled processes before using the system on important workloads.

## Future Work

- Improve ML evaluation with broader, labelled workload datasets.
- Validate candidate models across different normal and anomalous process scenarios.
- Measure false-positive rates and detection performance over repeated trials.
- Improve agreement analysis between rule-based and ML detectors.
- Consider ML-assisted enforcement only after sufficient validation and safety testing.
- Improve portability and document platform-specific behavior.

## License

This project uses the MIT License. See [LICENSE](LICENSE) for details.

## Local recovery-verification research extension

An opt-in bracketed release-probe prototype and synthetic comparison are documented in [research/recovery_probe/README.md](research/recovery_probe/README.md). It checks for restriction-masked CPU demand and protected-service impact before one duty relaxation. It is not enabled in default enforcement, does not establish patentability, and has not been validated as a production recovery mechanism.

## Combined academic report and technical disclosure

[Download Reviews I, II, III and IDF B](output/pdf/ARQ_Combined_Reviews_I_II_III_and_IDF_B.pdf). The 40-page report follows the supplied Arial layout and separates historical outputs, current module tests and synthetic recovery-policy results. See [report guide](docs/REPORT_GUIDE.md) for the page map, evidence limits and rebuild instructions. Patent claims are draft candidates; patentability is not established.
