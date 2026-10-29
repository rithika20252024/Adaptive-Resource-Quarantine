# Combined ARQ course report and IDF-B

The combined PDF is `output/pdf/ARQ_Combined_Reviews_I_II_III_and_IDF_B.pdf`.

| Part | Pages | Contents |
|---|---|---|
| Review I | 1-8 | Title/team, abstract, introduction, problem, objectives, twenty-work literature comparison and gaps |
| Review II | 9-18 | Methodology, architecture, control workflow, implementation, historical dashboard and current functional outputs |
| Review III | 19-29 | Test outcomes, reported benchmark, synthetic comparison, existing-system comparison, conclusion/future work and references |
| IDF-B | 30-40 | Candidate disclosure cover and ten sections, including prior art, components, algorithm, evidence, claim skeleton and TRL |

Formatting follows the user-supplied merged reference: Letter pages, Arial 12 body and table text, bold 18-point cover titles, plain black grids and thin page borders. The supplied ARQ Review I and earlier continued Review II provide project/team information and the historical screenshot. Content is consolidated and corrected against source rather than appended as duplicate historical pages. Unverified older references and the incorrect Flask description were replaced. The source PDFs remain unchanged.

The new policy is opt-in and not enabled in default dashboard restoration. Twelve new tests pass; thirty-two methods pass across five modules. ML training lacks optional joblib in the test environment, and unchanged macOS telemetry tests exit with signal 11. The five-scenario evaluation is synthetic, not a live performance or detection-accuracy study. The existing benchmark figures are README-reported historical results. Proposed patent claims are not established novel, filed or granted.

## Rebuild

Install `reportlab` and `pypdf` in an artifact-authoring environment and run:

```sh
python scripts/build_combined_report.py
```

The default font location is macOS `/System/Library/Fonts/Supplemental`. On another host set `REPORT_FONT_DIR` to a directory containing `Arial.ttf`, `Arial Bold.ttf` and `Arial Italic.ttf`. These report-authoring dependencies are not dependencies of the new core recovery module.

The final 40 pages were rendered and visually inspected. `output/pdf/report-qa.json` records the reviewed PDF hash and structural checks. Historical images are retained in `docs/report_assets`; only the dashboard image is embedded in the current report.

Publication is being performed at the user request. Retain the remote commit and publication date for any patent disclosure review. The project had already been public; commit timestamps do not establish its first public availability.
