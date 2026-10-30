# ARQ Kaggle server-telemetry training study

Completed 30 October 2026. **Offline research only; neither model is eligible for live ARQ enforcement.**

## Data and audit

Source: https://www.kaggle.com/datasets/keshanijayasinghe/cryptojacking-attack-timeseries-dataset
Publisher: Keshani Jayasinghe. Kaggle data-card licence: CC0. Retain attribution and this provenance record.

The archive includes normal, anomalous and combined CSVs. Only the first two are used. The combined CSV is excluded because reusing it would duplicate observations. Labels are assigned from the publisher normal/anomalous file names; they are not independently verified row labels.

- Source rows: 95,312 ({'final-normal-data-set.csv': 80851, 'final-anormal-data-set.csv': 14461}).
- Invalid records rejected: 2.
- Duplicate feature vectors removed: 784.
- Clean unique records: 94,526.
- Boundary-gap records excluded: 2,005.
- Active numeric features: 22; constant columns learned from training only and removed.

| Partition | Rows | Normal | Attack |
|---|---:|---:|---:|
| train | 56,170 | 47,649 | 8,521 |
| calibration | 17,922 | 15,217 | 2,705 |
| test | 18,429 | 15,619 | 2,810 |

## Split and model protocol

Chronological 60/20/20 partitions are constructed separately within each host, with 100 unique timestamps excluded on each side of each boundary. Identical selected-feature vectors are removed before splitting, and contradictory vectors would be excluded entirely. Equal host/timestamp groups stay together. The three fit seeds reuse the same held-out observations; they are not independent workload repetitions.

Isolation Forest: 200 trees, maximum 2,048 normal training samples per tree, trained only on the 47,649 normal training observations. Its decision threshold is the 95th percentile of negative decision scores on normal calibration observations.

Extra Trees: 200 trees, minimum leaf size 5, square-root feature sampling and balanced class weights, trained on all 56,170 training observations. The positive-probability threshold was fixed at 0.5 before test evaluation. Calibration labels and test labels are not used to fit this classifier or tune its threshold.

Hostnames, timestamps, source names, labels, OS metadata, static hardware identity and cumulative counters are excluded from model input. No scaling or artificial conversion to per-process ARQ features is performed.

## Held-out results

Means across seeds 42, 43 and 44 (same test set).

| Model | Accuracy | Precision | Recall | F1 | False-positive rate |
|---|---:|---:|---:|---:|---:|
| isolation_forest | 95.92% | 78.92% | 100.00% | 88.21% | 4.81% |
| extra_trees | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% |

### Critical interpretation

The normal examples come from four VM hosts; attack examples come from a different single host. Collection dates also differ. Therefore class and collection domain are confounded. Removing the hostname and timestamp columns does not remove this problem: memory and other resource distributions can still reveal the host or collection conditions. **The 100% Extra Trees result is dataset separation, not a validated general-purpose cryptojacking detector.** An unseen attack-host study cannot be supported with only one attack host.

No production accuracy, mitigation benefit, quarantine safety, recovery quality or patent novelty follows from these measurements. A balanced collection containing benign and attack workloads on each host, plus genuinely unseen hosts, is needed before deployment claims.

## Artifacts and use

- `evaluation.json`: dataset hashes, cleaning counts, partitions, all fit seeds, per-host errors, versions and limitations.
- `split-manifest.csv.gz`: source line and split for every retained observation.
- `*-test-predictions.csv.gz`: first-seed predictions and source-row provenance.
- `isolation_forest.joblib` / `extra_trees.joblib`: locally trained trusted artifacts with the external-host schema.
- `training.log`: raw training output.
- `tests.log`: new regression-test output.

These models deliberately use schema `arq.external_host_telemetry.v1`. They cannot pass the live ARQ assistance gate. The dashboard, its default shadow mode and the existing seven-feature process models are unchanged. Load joblib only from trusted sources.

## Reproduce

Run from the ARQ repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-evaluation.txt
mkdir -p data/kaggle-cryptojacking
curl -L --fail https://www.kaggle.com/api/v1/datasets/download/keshanijayasinghe/cryptojacking-attack-timeseries-dataset -o data/kaggle-cryptojacking/dataset.zip
.venv/bin/python -m arq.evaluation.kaggle_cryptojacking \
  --archive data/kaggle-cryptojacking/dataset.zip \
  --output output/validation/kaggle-cryptojacking --repeats 3
.venv/bin/python -m unittest tests.test_kaggle_cryptojacking -v
```

Current source archive SHA-256: `fb6277bb1ea73fc431a6162576b8765e68a38a528d9a55ac97672a4867f3069c`. Future Kaggle updates may produce different results; verify the hash before comparing. Numerical results may vary across library versions.

## Future work

Collect both labels on each of several hosts, reserve untouched hosts and dates, examine benign CPU-intensive workloads, pre-register thresholds, measure temporal false alarms and evaluate live process-compatible telemetry separately. Do not enable enforcement using the present external study.

## Publication validation and updated report

The full ARQ regression suite passed 61 tests after adding this study (57 earlier tests plus four new data-validation/deployment-boundary tests). The focused ML subset passed 15 tests. Raw outputs are in `full-tests.log` and `tests.log`.

The updated IDF-B is `output/pdf/ARQ_IDF_B_Updated_Kaggle_25_Papers.pdf`: 37 pages, continuous 25-paper table, horizontal TRL table and seven screenshot spaces. Kaggle data/methods/results are on pages 24-26; paste the qualified Kaggle training screenshot on page 27.
