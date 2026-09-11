# Synthetic output impact review

Baseline: engine before this implementation; current: engine 2.0, dataset 2026-09-11. These 36 synthetic cases test mechanics, not market accuracy. A verdict change, unavailable result or numeric movement over 10% flags review.

Twelve M&A cases retain the same headline EPS and verdict. All twelve startup cases lack an actual ask, so their price assessment changes to not_assessed. Recurring-software values change with smooth ARR weighting; hardware excludes ARR valuation. Four VC cases lack revenue and explicit exits, so expected returns become unavailable. The other eight remove previously automatic future-round/IPO dilution and use the corrected scenario mechanics; their larger returns are conditional illustrations, not evidence of improved investment outcomes.

| Case | Before | After | Verdict | Explanation |
| --- | ---: | ---: | --- | --- |
| startup-00 | 13.650 | 13.650 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-00 | 0.561 | Unavailable | pass → insufficient_inputs | No revenue or explicit exit; screening suppressed. |
| startup-01 | 13.790 | 12.480 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-01 | 0.440 | 1.586 | pass → pass | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-02 | 15.360 | 14.840 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-02 | 4.402 | 15.858 | look_deeper → look_deeper | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-03 | 20.470 | 20.470 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-03 | 1.246 | Unavailable | pass → insufficient_inputs | No revenue or explicit exit; screening suppressed. |
| startup-04 | 20.690 | 18.930 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-04 | 1.016 | 3.676 | pass → look_deeper | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-05 | 36.490 | 31.220 | strong → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-05 | 10.165 | 36.758 | look_deeper → look_deeper | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-06 | 15.120 | 15.120 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-06 | 0.457 | Unavailable | pass → insufficient_inputs | No revenue or explicit exit; screening suppressed. |
| startup-07 | 15.280 | 15.280 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-07 | 0.361 | 1.302 | pass → pass | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-08 | 22.900 | 15.280 | strong → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-08 | 3.612 | 13.022 | look_deeper → look_deeper | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-09 | 18.190 | 18.190 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-09 | 0.623 | Unavailable | pass → insufficient_inputs | No revenue or explicit exit; screening suppressed. |
| startup-10 | 18.380 | 18.380 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-10 | 0.508 | 1.838 | pass → pass | Only explicit future rounds dilute ownership; corrected exit scenarios. |
| startup-11 | 18.380 | 18.380 | fair → not_assessed | No actual ask; method applicability and weights govern indication. |
| vc-11 | 5.082 | 18.379 | look_deeper → look_deeper | Only explicit future rounds dilute ownership; corrected exit scenarios. |

Review disposition: changes are explained by the intended economic/input contracts above. Dedicated regression tests cover arithmetic; no empirical calibration inference is made. Full inputs and selected evidence are in current.json.
