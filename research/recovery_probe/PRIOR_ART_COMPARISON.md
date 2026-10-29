# Preliminary prior-art comparison

Search date: 30 October 2026. This is a bounded technical search, not a novelty opinion, freedom-to-operate opinion or exhaustive claim search. Publication dates and priority entitlement must be checked for the eventual filing. Expired patents can still be prior art.

| Reference | Established overlap | Candidate distinction to investigate, not proven novelty |
|---|---|---|
| [US7530072B1](https://patents.google.com/patent/US7530072B1/en), published 2009 | Quarantine suspicious threads, throttle CPU, lower priority, test exit criteria and restore priority | Does the complete record teach restricted–release–restricted measurements coupled to grant-normalized consumption, control drift and protected-service checks? Broad recovery/quarantine claims overlap strongly. |
| [US9280662B2](https://patents.google.com/patent/US9280662B2/en), published 2016 | Keep misbehaving processes operating in isolation and perform remediation | New prototype does not migrate into a quarantine partition; its proposed focus is verification before relaxing an existing CPU restriction. Mere implementation differences may be obvious. |
| [cpulimit](https://github.com/opsengine/cpulimit) | CPU restriction with SIGSTOP/SIGCONT | No novelty claim for the signal actuator. |
| [Heracles, Lo et al.](https://research.google/pubs/improving-resource-efficiency-at-scale-with-heracles/), 2016 journal version | Feedback control of colocated resource allocations using protected-service latency | Latency-aware allocation and hysteresis are already known. The candidate focus is checking restriction-masked recovery using bracketing and normalized consumption; obviousness remains a substantial concern. |
| [Caladan, Fried et al., OSDI 2020](https://www.usenix.org/conference/osdi20/presentation/fried) | Fast contention-aware scheduling, performance isolation and dynamic CPU management | This user-space experiment is slower and narrower; no claim of outperforming Caladan or inventing interference-aware scheduling. |
| [US20230128059A1](https://patents.google.com/patent/US20230128059A1/en), 2023 | Dynamic resource allocation for latency-sensitive application SLOs | Broad resource adjustment based on SLOs is insufficient. Full claims/family review is still necessary. |

## Search assessment

The expanded search weakens the original proposal of simply adding protected-service latency to recovery: that is already a well-developed area. The implemented research candidate is a precise conjunction of restricted–release–restricted observations, grant-normalized consumption, nuisance-change rejection and restore-before-commit semantics. This search did not establish that conjunction as novel. Absence of an exact search hit is not evidence that prior art does not exist.

Additional search should cover experimental/perturbation-based resource control, interference attribution, admission control, recovery probes, AIMD controllers and safe online optimization, including non-patent publications and patent families. Compare each proposed limitation against full disclosures, not titles alone.

## India

[Section 3(k)](https://www.ipindia.gov.in/acts/patent-act-1970/section-3) excludes algorithms and computer programmes per se. The candidate's actual processor-allocation control and measurable workload effects are the relevant technical subject matter to examine, rather than a new label or ML model. Technical character alone does not establish novelty or inventive step. Consult the [official CRI guideline collection](https://ipindia.gov.in/resource/patents-resources-guidelines) and an Indian patent agent.

The existing public repository creates a separate disclosure issue if its relevant contents predate a valid filing. First public availability, earlier filings, inventorship and any applicable statutory exception require evidence and professional review. A local extension does not restore novelty to material already disclosed.
