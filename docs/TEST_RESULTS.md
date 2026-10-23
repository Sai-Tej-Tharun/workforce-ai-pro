# Test Results

Executed 2026-10-23 with `pytest` (36 tests: API, RBAC, validation, ML quality, real-time WebSocket, end-to-end alert flow).

| Database | Result |
|---|---|
| SQLite (in-memory) | **36/36 passed** |
| MariaDB 10.11 (MySQL-compatible, real server, strict mode) | **36/36 passed** |

> Running on a real MySQL-family server caught one defect SQLite hid (a temporary `employee_code` exceeded `VARCHAR(20)`); it was fixed and the suite re-run. MySQL 8.0 itself was not available in the build environment.

## Test cases
| Suite | Test | SQLite | MariaDB |
|---|---|---|---|
| ai_engine | `test_model_beats_baseline_on_holdout` | ✅ | ✅ |
| ai_engine | `test_explanations_are_directionally_sensible` | ✅ | ✅ |
| ai_engine | `test_validation_reports_failures_and_duplicates` | ✅ | ✅ |
| ai_engine | `test_validation_missing_required_and_ibm_aliases` | ✅ | ✅ |
| ai_engine | `test_dataset_upload_versioning_and_train` | ✅ | ✅ |
| ai_engine | `test_prediction_endpoints` | ✅ | ✅ |
| ai_engine | `test_what_if_reduces_risk` | ✅ | ✅ |
| ai_engine | `test_batch_predict` | ✅ | ✅ |
| ai_engine | `test_end_to_end_activity_to_alert_flow` | ✅ | ✅ |
| ai_engine | `test_intervention_workflow` | ✅ | ✅ |
| ai_engine | `test_alert_priority_and_ack` | ✅ | ✅ |
| ai_engine | `test_forecast_properties` | ✅ | ✅ |
| ai_engine | `test_stability_and_attrition_analytics` | ✅ | ✅ |
| ai_engine | `test_dashboards_per_role` | ✅ | ✅ |
| ai_engine | `test_instability_scan` | ✅ | ✅ |
| ai_engine | `test_recommendations` | ✅ | ✅ |
| ai_engine | `test_reports_export` | ✅ | ✅ |
| auth_rbac | `test_health` | ✅ | ✅ |
| auth_rbac | `test_register_login_session_refresh` | ✅ | ✅ |
| auth_rbac | `test_weak_password_and_bad_login` | ✅ | ✅ |
| auth_rbac | `test_login_throttle` | ✅ | ✅ |
| auth_rbac | `test_forgot_reset_password` | ✅ | ✅ |
| auth_rbac | `test_expired_and_missing_token` | ✅ | ✅ |
| auth_rbac | `test_rbac_matrix` | ✅ | ✅ |
| auth_rbac | `test_admin_user_management` | ✅ | ✅ |
| core_modules | `test_employee_crud_search_filter` | ✅ | ✅ |
| core_modules | `test_manager_and_employee_scope` | ✅ | ✅ |
| core_modules | `test_departments_roles` | ✅ | ✅ |
| core_modules | `test_attendance_flow` | ✅ | ✅ |
| core_modules | `test_leave_workflow` | ✅ | ✅ |
| core_modules | `test_payroll_generation_and_payslip` | ✅ | ✅ |
| core_modules | `test_documents_validation` | ✅ | ✅ |
| core_modules | `test_notifications_and_chat` | ✅ | ✅ |
| core_modules | `test_websocket_auth_and_push` | ✅ | ✅ |
| core_modules | `test_tasks_and_performance` | ✅ | ✅ |
| core_modules | `test_audit_trail` | ✅ | ✅ |

## AI model quality (held-out test split, synthetic IBM-HR-style dataset, 3,000 rows)

| Metric | Value |
|---|---|
| Selected algorithm | LogisticRegression (best 4-fold CV ROC-AUC of 3 candidates) |
| ROC-AUC (test) | **0.8915** |
| ROC-AUC (cross-val) | 0.8288 |
| Accuracy | **84.7%** (majority-class baseline 81.7%) |
| Precision / Recall / F1 | 57.9% / 60.0% / 0.5893 |
| Confusion matrix [[TN,FP],[FN,TP]] | [[442, 48], [44, 66]] |

Candidates (CV ROC-AUC): LogisticRegression 0.8288, RandomForest 0.8104, GradientBoosting 0.8117.

`test_model_beats_baseline_on_holdout` additionally trains on one synthetic sample and scores a *different-seed* sample, asserting AUC ≥ 0.80 and accuracy above the majority baseline.

**Caveat:** the data is synthetic (generated from a hidden logistic process with noise), so these numbers show the pipeline works end-to-end, not what accuracy you will get on your own HR data. Upload your dataset in *Datasets & Models* to retrain.

## Browser verification
A headless-Chromium (Playwright) sweep visited all 23 pages as HR, 19 as Manager and 12 as Employee: **0 console errors, 0 uncaught exceptions, 0 failed API calls**; restricted pages show *Access denied* and are hidden from the sidebar. This sweep found and fixed one real UI crash (sortable-table header). Screenshots are in `docs/screenshots/`.

## Load sanity check
200 requests per endpoint, 20 concurrent clients, **one uvicorn worker, SQLite, 111 employees** (a deliberately small setup):

| Endpoint | Success | p50 | p95 |
|---|---|---|---|
| `/employees?size=20` | 200/200 | 561 ms | 637 ms |
| `/analytics/dashboard` | 200/200 | 303 ms | 545 ms |
| `/ai/predictions/latest?size=20` | 200/200 | 546 ms | 646 ms |
| `/monitoring/high-risk` | 200/200 | 401 ms | 566 ms |
| `/analytics/attrition` | 200/200 | 698 ms | 967 ms |

These are single-process numbers; see `docs/ARCHITECTURE.md` → *Scalability* for the multi-worker / MySQL / Redis path. No claim is made about larger loads.
