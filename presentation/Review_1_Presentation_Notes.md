# Project Review 1: Presentation Transcripts & Speaker Notes

**Project Title:** Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior  
**Degree & Specialization:** B.Tech Computer Science and Engineering & B.Tech CSE with IoT  
**Lab Slot:** L15+16  
**Faculty Guide:** Dr. Anisha M Lal, Department of Computer Science and Engineering  
**Students:**
- **Rithika S** (Reg No: 24BCE2984) · B.Tech CSE
- **K. Vaishnavi** (Reg No: 24BCT0183) · B.Tech CSE IOT

---

## Slide 1: Title & Team Details
- **Heading:** Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior
- **Core Pitch:** A lightweight OS mechanism that scores abnormal process behavior and temporarily restricts its resources instead of killing it, then releases it once it recovers.
- **The Quarantine Loop:**
  1. *Monitor and score:* CPU, memory, I/O continuous multi-metric telemetry.
  2. *Quarantine:* Adaptive throttle (cgroups/scheduling), don't kill.
  3. *Re-evaluate:* Is behavior back to baseline?
  4. *Release or Terminate:* Dynamic auto-recovery or safe termination if abuse persists.
- **Speaker Note:** 
  > "Good morning faculty and panel members. Today we present Review 1 of our project: 'Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior'. Today's multi-tasking operating systems suffer from single rogue processes destabilizing the entire machine. Rather than reacting with blunt termination or rigid static caps, our system implements a closed-loop adaptive quarantine: Restrict first, re-evaluate, and safely release on recovery."

---

## Slide 2: Abstract
- **Core Theme:** Restrict first, terminate only if needed.
- **Key Concepts:**
  - *Anomaly Score:* Multi-metric, not a single static threshold.
  - *Graduated Restriction:* CPU priority, memory growth limits, and I/O rate controlled simultaneously.
  - *Release or Terminate:* Dynamic restoration when anomalous behavior subsides; terminal enforcement only upon persistent unresponsiveness.
- **Speaker Note:**
  > "Our abstract highlights that traditional OS mechanisms treat process containment as binary: either you let the process run unrestricted or you terminate it outright via SIGKILL or OOM-killer. ARQ introduces an intermediate, reversible state: Adaptive Quarantine."

---

## Slide 3: Introduction: Context & Problem Statement
- **Problem Formulation:**
  - *Shared resources, shared fate:* Modern processes share CPU cores, memory buses, cache hierarchies, and storage bandwidth. One runaway process induces severe tail-latency spikes across all neighbor workloads.
  - *Killing is blunt:* Unconditional termination destroys execution state, loses in-flight database transactions, and crashes legitimate processes undergoing transient batch computations.
  - *Static caps are rigid:* Traditional cgroups or ulimit caps cannot differentiate between transient compilation bursts and malicious cryptographic miners.
- **Comparison Diagram:**
  - *Existing:* Process misbehaves → Threshold crossed → Hard Cap or Kill (Open-loop).
  - *Proposed:* Monitor → Composite Score → Adaptive Quarantine → Re-evaluation → Dynamic Release / Termination (Closed-loop).
- **Speaker Note:**
  > "Notice the architectural difference: existing Linux CFS quotas and OOM handlers are open-loop. ARQ establishes a closed-loop feedback controller that constantly re-scores processes under restriction, enabling seamless recovery."

---

## Slide 4: Introduction: Project Objectives
1. **Continuous Monitoring:** Telemetry collection across CPU %, RSS memory rate, I/O ops, and burst dynamics.
2. **Anomaly Scoring:** Multi-dimensional composite anomaly calculation integrating EWMA baselining.
3. **Adaptive Quarantine:** Dynamic multi-stage restriction (nice escalation, CPU duty cycling, I/O prioritization).
4. **Neighbor Protection:** Shield latency-sensitive co-located applications from starvation.
5. **Dynamic Restoration:** Automatic de-quarantine and resource restoration upon behavior normalization.
6. **Empirical Evaluation:** Quantitative benchmarking across latency P95/P99, throughput, and Mean Time to Recovery (MTTR).
7. **Lightweight Alternative:** Low-overhead user-space / kernel-assisted enforcement without kernel recompilation.
- **Core Motto:** *Restrict, don't kill. Release on recovery.*

---

## Slide 5 & 6: Literature Survey (Detection & Containment)
- **Detection Survey:**
  - *Ibidunmoye et al. (ACM CSUR 2015):* Foundational taxonomy of system bottlenecks; established that multi-resource interference cannot be caught by single-vector thresholds.
  - *Zhang et al. (AIPR 2023) & Ma et al. (CCC 2025):* eBPF with Isolation Forest achieves high precision detection, but stops at reporting alerts without automated remediation.
  - *Szabo et al. (IEEE TDSC 2020):* Online SVMs for anomaly identification without historical fault data; lacks process containment.
- **Containment Survey:**
  - *Somayaji (pH, 2002):* Process Homeostasis introduced systematic delays into anomalous syscalls. Proved non-destructive slowdown stabilizes systems, but operated at syscall level rather than CPU/mem/IO resource boundaries.
  - *Nakagawa et al. (IEEE 2015):* Closest prior work on on-the-fly process resource quarantine via dynamic cgroups; focused primarily on fork bombs and static memory limits without automated release policies.
  - *Chen et al. (Alita, SC20 2020):* Throttled polluters in cloud VMs (30,000 nodes); operates at VM scale rather than single OS process level.
  - *Wang et al. (Valve, FGCS 2022):* Kernel resource isolation for containers via system-call filtering; achieved up to 98% isolation improvement.

---

## Slide 7: What the Evidence Says (Meta-Analysis)
- **9 of 9** consensus papers agree that adaptive resource quarantine significantly mitigates system degradation.
- **66%** average CPU utilization increase on 90,000+ Bing servers (PerfIso, 2018) without tail latency penalties.
- **98%** maximum kernel resource isolation improvement (Valve, 2022).
- **6.9 s** recovery ceiling during memory exhaustion events (ROMA, 2026).
- **The Catch:** While detection and throttling are extensively studied, **safe, automatic de-quarantine and restoration** remain virtually unaddressed in current operating systems.

---

## Slide 8 & 9: Gaps of Existing Systems & Comparison
1. **Release is Under-Studied:** Most systems require human/admin intervention or leave processes permanently throttled.
2. **Static, Single-Signal Thresholds:** Bursting applications suffer false positives under rigid CPU caps.
3. **Cross-Resource Blind Spots:** Throttling memory without regulating I/O leads to page thrashing and lockups.
4. **Detection and Control are Disconnected:** State-of-the-art anomaly detectors (eBPF, ML) output alerts, while kernel actuators (cgroups, nice) operate without behavioral feedback.

---

## Slide 10: Summary & Next Steps for Review 2
- **Summary:** ARQ bridges the gap with a closed-loop, reversible, multi-resource quarantine framework.
- **Roadmap for Review 2:**
  - Detailed mathematical formulation of composite anomaly scoring and hysteresis recovery.
  - Complete software architecture (telemetry engine, score pipeline, quarantine controller, restoration daemon).
  - Benchmark testbed, simulation workloads, and initial experimental outputs.
