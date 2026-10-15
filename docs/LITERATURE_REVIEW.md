# Literature Review: Adaptive Resource Quarantine

## 1. Survey of Anomaly Detection Mechanisms

| Work | Target Vector | Primary Technique | Finding & Gap |
| :--- | :--- | :--- | :--- |
| **Ibidunmoye et al.** (*ACM CSUR 2015*) | Multi-resource bottlenecks | Observability taxonomy across CPU, Memory, Disk, Network | Shows problem complexity; provides survey taxonomy but no autonomous process actuator. |
| **Zhang et al.** (*AIPR 2023*) | Process usage telemetry | eBPF + Isolation Forest | High detection accuracy in hybrid systems; stops at alerting without throttling or recovery. |
| **Ma et al.** (*CCC 2025*) | Operating system memory | eBPF + Isolation Forest | Diagnostics for memory anomalies; lacks dynamic containment or self-healing release. |
| **Szabo et al.** (*IEEE TDSC 2020*) | Performance metrics | Online Support Vector Machines (SVM) | Learns unseen anomalies ($F > 0.70$); lacks single-OS process quarantine loop. |

---

## 2. Survey of Containment & Isolation Mechanisms

| System | Granularity | Mechanism | Limitation / Gap |
| :--- | :--- | :--- | :--- |
| **pH (Somayaji 2002)** | Process | System call delay injection | Intercepts syscalls rather than controlling direct CPU/Mem/IO resource quotas. |
| **Nakagawa et al. (IEEE 2015)** | Process | Dynamic cgroup limit assignment | Centered on memory limits & fork bombs; lacks multi-metric scoring and automated release. |
| **Alita (Chen et al. SC20 2020)** | Cloud VM | Bias resource management & throttling | Tested on 30,000 nodes; cloud/VM-level rather than granular OS process level. |
| **Valve (Wang et al. FGCS 2022)** | Container | Kernel-object isolation via syscall limiting | Achieves up to 98% isolation; no adaptive release or behavioral scoring pipeline. |

---

## 3. Quantitative Evidence Synthesis

A meta-analysis across systems literature reveals strong empirical consensus:
- **100% (9 of 9)** peer-reviewed papers taking a stance affirm that adaptive quarantine mitigates system-wide performance degradation.
- **PerfIso (2018):** Increased server CPU utilization from 21% to 66% across 90,000+ servers without tail latency harm.
- **ROMA (2026):** Maintained recovery ceiling under 6.9 seconds during memory exhaustion attacks.
- **The Core Literature Gap:** While telemetry and throttling are mature, **closed-loop restoration** (de-quarantine) and **burst-aware scoring** remain unaddressed in existing desktop and server operating systems.
