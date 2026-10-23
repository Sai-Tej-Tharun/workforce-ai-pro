# Architecture, Security & Scalability

## 1. System overview
```
React (Vite, Tailwind, Recharts, Axios)  ──REST /api──►  FastAPI (routers → services → SQLAlchemy)  ──►  MySQL
        ▲   └────── WebSocket /api/ws ───────┘                    │
        │                                                         ├─ ML service (scikit-learn Pipeline, joblib artifacts)
        └── live: notifications · chat · activity feed · risk updates   └─ Risk engine (recalc → alert → intervention → log → push)
```
Layers: **routers** (HTTP, validation, RBAC) → **services** (risk engine, ML, forecasting, recommendations, features) → **models** (SQLAlchemy 2.0 ORM). Pydantic schemas validate every request body.

## 2. The expected flow (implemented in `app/services/risk.py`)
| Step in brief | Implementation |
|---|---|
| Employee activity changes | `POST /monitoring/activity`, attendance check-in/out, leave approval, profile update, performance review |
| AI engine recalculates risk | `risk.recalc()` builds features (profile + last-90-day attendance) → `Predictor.predict()` → stored `Prediction` (score, level, confidence, top factors) |
| High-risk employee detected | level transition `low/medium → high` using thresholds (`HIGH_RISK_THRESHOLD=0.60`, `MEDIUM=0.30`) |
| HR alert triggered | `Alert` row + `Notification` to HR/Admin/line manager + WebSocket push + live-feed event (de-duplicated: one open high-risk alert per employee) |
| Intervention workflow initiated | auto-created `Intervention` (open, follow-up +7 days) with actions mapped from the employee's own risk drivers (`recommend.PLAYBOOK`) |
| Monitoring logs updated | `MonitoringLog` (old→new score/level, trigger) + `InterventionLog` |
| Dashboard refreshed | cache cleared, `risk_update` WebSocket event → dashboard/predictions/risk-monitor pages re-fetch |

Covered end-to-end by `tests/test_ai_engine.py::test_end_to_end_activity_to_alert_flow`.

## 3. AI / ML design
* **Features (21):** age, income, commute, job level, 3 satisfaction scores, tenure, years since promotion, experience, past employers, training, performance, stock options, education, overtime flag, **late days / unplanned absences / avg overtime hours (live, from attendance, 90-day window)**, marital status, department.
* **Training:** stratified 80/20 split → 3 candidates (Logistic Regression, Random Forest, Gradient Boosting) compared by 4-fold CV ROC-AUC → best refit → decision threshold chosen by best F1 on out-of-fold predictions → metrics on the untouched test split → final refit on all rows. Metrics, confusion matrix, permutation importance and the candidate comparison are stored in `ml_models`.
* **Probabilities are not re-weighted** (no `class_weight`), so the score behaves like a probability and risk bands are meaningful.
* **Explainability:** per-employee counterfactual attribution — each feature is replaced by the population reference value and the drop in probability is the driver's impact (percentage points). Powers "top drivers", recommended actions and the **what-if simulator**.
* **Confidence** = `max(p, 1-p)` (probability of the predicted class). It is a model-certainty measure, not a calibrated interval.
* **Dataset pipeline:** CSV/XLSX upload → column aliasing (IBM-HR names work) → required-column check → per-row type/range validation → duplicate detection → failed-record report (downloadable) → versioning per dataset name.
* **Forecast:** each score is read as a 12-month attrition probability; monthly hazard `h = 1-(1-p)^(1/12)`; expected survivors `Σ(1-h)^m`; new hires decay at the mean hazard. This is an *assumption-driven projection*, not a validated time-series forecast.
* **Stability score (0–100):** `100 − 160%·(0.55·avg risk + 0.25·high-risk share + 0.20·low-satisfaction share)`.

## 4. Database design (25 tables, 3NF-style)
Full DDL: `database/schema.sql` · ER diagram: `docs/ERD.md`.
* Core HR: `users`, `employees`, `departments`, `job_roles`, `shifts`
* Time & money: `attendance` (unique employee+date), `leave_policies`, `leave_requests`, `payroll` (unique employee+month+year)
* AI: `datasets`, `ml_models`, `predictions` (full history), `monitoring_logs`, `alerts`, `interventions`, `intervention_logs`, `activity_events`
* Collaboration & governance: `notifications`, `chat_messages`, `documents`, `tasks`, `performance_reviews`, `goals`, `audit_logs`, `password_reset_tokens`
* Integrity: foreign keys with `ON DELETE` rules, unique constraints, composite indexes on hot paths (`predictions(employee_id, created_at)`, `attendance(work_date)`, `notifications(user_id,is_read)`, `chat(sender,receiver,created_at)`, `employees(department_id,status)`).

## 5. Security implementation
| Area | Implementation |
|---|---|
| Authentication | JWT access (30 min) + refresh (7 d) with distinct `type` claims; refresh cannot be used as access and vice-versa; silent refresh in the Axios interceptor |
| Passwords | PBKDF2-HMAC-SHA256, 210k iterations, per-user salt, constant-time compare; strength policy |
| Brute force | 8 failed logins / 15 min per email+IP → HTTP 429; failures audit-logged |
| Reset flow | single-use, 30-min tokens stored **hashed**; no account enumeration |
| RBAC | `ADMIN > HR > MANAGER (own team) > EMPLOYEE (self)` enforced server-side on every route; row-level scoping via `employee_scope_filter`; employees never receive risk data; payroll limited to HR + owner |
| Self-registration | always creates EMPLOYEE; only ADMIN can grant roles; admin cannot demote/deactivate self |
| Input validation | Pydantic bounds on every field; parameterised SQL via ORM; LIKE inputs bound as parameters |
| Uploads | extension allow-list, **magic-byte check**, size cap, sanitised name, random stored name outside web root, ownership checks on download/delete |
| Audit | every create/update/delete/login/export/train recorded with user, IP, and field-level diffs |
| Transport/headers | CORS allow-list, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`, gzip |
| WebSocket | token verified on connect (close code 4401 if invalid/expired) |

**Known gaps (deliberate scope limits):** tokens are kept in `localStorage` (a production hardening step is httpOnly cookies + CSRF); no email delivery (dev mode echoes the reset token, switch off with `EXPOSE_RESET_TOKEN=false`); no TLS termination (use the reverse proxy); no refresh-token revocation list; no MFA.

## 6. Scalability approach
Implemented now: SQLAlchemy connection pooling (`pool_size=10, max_overflow=20, pre_ping`), server-side pagination and `size` caps on every list endpoint, indexed filters, batched ML inference (all employees in one `predict_proba` call per batch), batched feature SQL (grouped aggregates, not N+1), 15-second TTL cache on dashboards (invalidated by risk recalculation), gzip, route-level code splitting and vendor chunking on the frontend, stateless API (JWT) so it can be replicated.

Documented path for production scale (not built here):
1. Run `uvicorn --workers N` / gunicorn behind nginx; MySQL read replica for analytics endpoints.
2. Replace in-process pieces with **Redis**: login throttle, TTL cache, and WebSocket fan-out (pub/sub) — these three are the only per-process state.
3. Move batch prediction and report generation to a worker queue (Celery/RQ) triggered by the same `risk.recalc()` function.
4. Partition `predictions`/`audit_logs`/`activity_events` by month; archive old rows.
5. Alembic migrations (the project currently uses `create_all`).

## 7. Real-time handling
`/api/ws?token=` → `ConnectionManager` (per-user socket sets, role-based broadcast, thread-safe publish from sync endpoints). Events: `notification`, `chat`, `chat_read` (read receipts), `typing`, `activity`, `risk_update`. Client reconnects with exponential back-off and refreshes an expired token on close code 4401; a 25-second heartbeat keeps proxies open.
