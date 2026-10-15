# System Architecture: Adaptive Resource Quarantine (ARQ)

## Executive Summary
Modern operating systems lack a middle ground between unconstrained multi-tenant process execution and destructive process termination (`SIGKILL`, OOM-killer). **Adaptive Resource Quarantine (ARQ)** introduces a lightweight, closed-loop, kernel-informed feedback architecture that scores multi-vector resource anomalies, enforces graduated dynamic constraints, and safely releases processes when behavioral normality returns.

---

## Architecture Diagram

```
+-----------------------------------------------------------------------------------------+
|                                    USER WORKSPACE                                       |
|  +------------------------+      +------------------------+      +-------------------+  |
|  | Benign Workload (Probe)|      | Transient Spike (gcc)  |      | Malicious / Rogue |  |
|  |  (Latency Sensitive)   |      |   (Burst Tolerant)     |      |  (CPU/Mem/IO)     |  |
|  +-----------+------------+      +-----------+------------+      +---------+---------+  |
+--------------|-------------------------------|-----------------------------|------------+
               |                               |                             |
               +-------------------------------+-----------------------------+
                                               |
                                     [Continuous Telemetry]
                                               v
+-----------------------------------------------------------------------------------------+
|                                   ARQ TELEMETRY CORE                                    |
|   - Linux: /proc/<pid>/stat, /proc/<pid>/status, /proc/<pid>/io                         |
|   - macOS: libproc.proc_pidinfo (PROC_PIDTASKINFO), mach_timebase                      |
|   - Multi-metric Observation Vector: [CPU%, RSS MB/s, Total RSS, IO KB/s, Burst Δ]      |
+----------------------------------------------+------------------------------------------+
                                               |
                                     [Raw Telemetry Vector]
                                               v
+-----------------------------------------------------------------------------------------+
|                           ANOMALY SCORING & FILTERING ENGINE                            |
|   - EWMA Baseline Tracker: μ_t = α · x_t + (1 - α) · μ_(t-1)                            |
|   - Multi-Vector Normalizer (Sigmoidal CPU, Saturation Memory, IO bounds)               |
|   - Burst Dynamics Filter (Suppresses false alarms for short compile/render spikes)     |
|   - Dominant-Resource Convex Scorer: S_eff ∈ [0.0, 1.0]                                 |
+----------------------------------------------+------------------------------------------+
                                               |
                                     [Effective Anomaly Score]
                                               v
+-----------------------------------------------------------------------------------------+
|                          ADAPTIVE CLOSED-LOOP STATE MACHINE                             |
|                                                                                         |
|      +------------+   S >= 0.40   +-------------+   S >= 0.65   +--------------------+  |
|      |   NORMAL   | ------------> |  WATCHLIST  | ------------> |  SOFT_QUARANTINE   |  |
|      | (Standard) | <------------ | (Telemetry) | <------------ |  (Nice+10, 40% CPU)|  |
|      +------------+  Hysteresis   +-------------+  Hysteresis   +---------+----------+  |
|                                                                           |  S >= 0.85  |
|                                                                           v             |
|                                   +-------------------+         +--------------------+  |
|                                   |    TERMINATED     | <------ |  HARD_QUARANTINE   |  |
|                                   | (Persistent Abuse)| T_persist| (Nice+19, 15% CPU)|  |
|                                   +-------------------+         +--------------------+  |
+----------------------------------------------+------------------------------------------+
                                               |
                                     [Actuation Commands]
                                               v
+-----------------------------------------------------------------------------------------+
|                                ENFORCEMENT ACTUATORS                                    |
|   - CPU Duty-Cycle Pulser: High-resolution POSIX SIGSTOP/SIGCONT pacing                 |
|   - Priority Modulation: Nice / renice / setpriority dynamic shifting                   |
|   - cgroup v2 Hooks: cpu.max and memory.high throttling (where supported)               |
|   - I/O Scheduling: POSIX ionice / scheduling class adjustment                          |
+-----------------------------------------------------------------------------------------+
```

---

## Core Components

### 1. Telemetry Collector (`arq.core.monitor`)
- Cross-platform process telemetry without third-party kernel driver requirements.
- Zero-overhead kernel inspection via `libproc` on Darwin and `/proc` on Linux.
- Collects metrics every $\Delta t = 200\text{ms} - 500\text{ms}$.

### 2. Multi-Dimensional Scorer (`arq.core.anomaly_scorer`)
- Combines continuous metric vectors to detect asymmetric abuse (e.g. high memory growth without CPU usage, or I/O flooding).
- Transient burst tolerance preserves user interactivity during legitimate workloads like software compilation or photo exporting.

### 3. Adaptive Quarantine Controller (`arq.core.quarantine_controller`)
- Executes reversible throttling without losing process state, virtual memory mappings, or unsaved files.
- Modulates CPU duty cycle with millisecond precision, ensuring rogue processes consume only their allocated time slice.

### 4. Dynamic Restoration Engine (`arq.core.restoration_engine`)
- Solves the open research gap identified in literature: **automated recovery**.
- Employs hysteresis counters ($H = 4$ cycles) to verify behavioral stability before stepping down restriction tiers.
- Safeguards system stability with a persistence watchdog timer ($T_{persist}$).
