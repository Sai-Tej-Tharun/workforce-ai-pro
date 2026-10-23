# WorkForce AI Pro – API Reference

Base URL: `http://localhost:8000/api` · Interactive docs: `/docs` (Swagger) and `/redoc` · OpenAPI JSON: `docs/openapi.json`

**128 REST endpoints** + 1 WebSocket (`/api/ws?token=<access_token>`).

## Authentication
All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/forgot-password`, `/auth/reset-password` and `/health` require `Authorization: Bearer <access_token>`.
Access tokens live 30 min, refresh tokens 7 days (`POST /auth/refresh`). Login uses `application/x-www-form-urlencoded` (`username` = email, `password`).

## Roles
`ADMIN` > `HR` > `MANAGER` (own team only) > `EMPLOYEE` (self only). Role requirements are enforced server-side on every endpoint (see 🔒 column / Swagger).

## WebSocket events (server → client)
| type | payload | audience |
|---|---|---|
| `notification` | id,title,message,category,priority,link | the recipient |
| `chat` | message + sender_name | receiver |
| `chat_read` | reader_id, message_ids, read_at | sender (read receipts) |
| `typing` | user_id | receiver |
| `activity` | live workforce feed event | ADMIN/HR/MANAGER |
| `risk_update` | employee_ids, trigger | ADMIN/HR/MANAGER |

Client → server: text `ping` (→ `pong`), `typing:<user_id>`.


## AI Prediction Engine
| Method | Path | Summary | Auth |
|---|---|---|---|
| `POST` | `/api/api/ai/predict/all` | Predict All | 🔒 |
| `POST` | `/api/api/ai/predict/employee/{emp_id}` | Predict Employee | 🔒 |
| `POST` | `/api/api/ai/predict/what-if` | What If | 🔒 |
| `GET` | `/api/api/ai/predictions/departments` | Department Predictions | 🔒 |
| `GET` | `/api/api/ai/predictions/employee/{emp_id}` | History | 🔒 |
| `GET` | `/api/api/ai/predictions/latest` | Latest | 🔒 |

## AI Recommendations
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/recommendations/department/{dept_id}` | For Department | 🔒 |
| `GET` | `/api/api/recommendations/employee/{emp_id}` | For Employee | 🔒 |
| `GET` | `/api/api/recommendations/team` | Team Insights | 🔒 |
| `GET` | `/api/api/recommendations/workforce` | Workforce | 🔒 |

## Analytics & Dashboard
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/analytics/attrition` | Attrition | 🔒 |
| `GET` | `/api/api/analytics/dashboard` | Dashboard | 🔒 |
| `GET` | `/api/api/analytics/forecast` | Forecast | 🔒 |
| `GET` | `/api/api/analytics/stability` | Stability | 🔒 |

## Attendance & Shifts
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/attendance` | List Attendance | 🔒 |
| `POST` | `/api/api/attendance/check-in` | Check In | 🔒 |
| `POST` | `/api/api/attendance/check-out` | Check Out | 🔒 |
| `POST` | `/api/api/attendance/manual` | Manual Entry | 🔒 |
| `GET` | `/api/api/attendance/report` | Attendance Report | 🔒 |
| `GET` | `/api/api/attendance/summary` | Attendance Summary | 🔒 |
| `GET` | `/api/api/attendance/today` | Today Status | 🔒 |
| `GET` | `/api/api/shifts` | List Shifts | 🔒 |
| `POST` | `/api/api/shifts` | Create Shift | 🔒 |
| `POST` | `/api/api/shifts/assign` | Assign Shift | 🔒 |

## Audit Logs
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/audit` | List Logs | 🔒 |
| `GET` | `/api/api/audit/history/{entity}/{entity_id}` | Change History | 🔒 |
| `GET` | `/api/api/audit/my-activity` | My Activity | 🔒 |
| `GET` | `/api/api/audit/summary` | Summary | 🔒 |

## Auth
| Method | Path | Summary | Auth |
|---|---|---|---|
| `POST` | `/api/api/auth/change-password` | Change Password | 🔒 |
| `POST` | `/api/api/auth/forgot-password` | Forgot Password | public |
| `POST` | `/api/api/auth/login` | Login | public |
| `GET` | `/api/api/auth/me` | Me | 🔒 |
| `POST` | `/api/api/auth/refresh` | Refresh | public |
| `POST` | `/api/api/auth/register` | Register | public |
| `POST` | `/api/api/auth/reset-password` | Reset Password | public |
| `GET` | `/api/api/auth/session` | Session | 🔒 |
| `GET` | `/api/api/users` | List Users | 🔒 |
| `POST` | `/api/api/users` | Create User | 🔒 |
| `PATCH` | `/api/api/users/{user_id}` | Update User | 🔒 |

## Chat
| Method | Path | Summary | Auth |
|---|---|---|---|
| `POST` | `/api/api/chat` | Send | 🔒 |
| `GET` | `/api/api/chat/contacts` | Contacts | 🔒 |
| `GET` | `/api/api/chat/history/{other_id}` | History | 🔒 |
| `GET` | `/api/api/chat/logs` | Communication Logs | 🔒 |
| `POST` | `/api/api/chat/read/{other_id}` | Mark Conversation Read | 🔒 |

## Datasets & Models
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/datasets` | List Datasets | 🔒 |
| `GET` | `/api/api/datasets/template` | Template | 🔒 |
| `POST` | `/api/api/datasets/upload` | Upload Dataset | 🔒 |
| `DELETE` | `/api/api/datasets/{did}` | Delete Dataset | 🔒 |
| `GET` | `/api/api/datasets/{did}` | Get Dataset | 🔒 |
| `GET` | `/api/api/datasets/{did}/failed-report` | Failed Report | 🔒 |
| `POST` | `/api/api/datasets/{did}/train` | Train On Dataset | 🔒 |
| `GET` | `/api/api/models` | List Models | 🔒 |
| `GET` | `/api/api/models/active` | Active Model | 🔒 |
| `POST` | `/api/api/models/{mid}/activate` | Activate Model | 🔒 |

## Departments & Roles
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/departments` | List Departments | 🔒 |
| `POST` | `/api/api/departments` | Create Department | 🔒 |
| `GET` | `/api/api/departments/stats` | Department Stats | 🔒 |
| `DELETE` | `/api/api/departments/{dept_id}` | Delete Department | 🔒 |
| `PUT` | `/api/api/departments/{dept_id}` | Update Department | 🔒 |
| `GET` | `/api/api/roles` | List Roles | 🔒 |
| `POST` | `/api/api/roles` | Create Role | 🔒 |
| `DELETE` | `/api/api/roles/{role_id}` | Delete Role | 🔒 |
| `PUT` | `/api/api/roles/{role_id}` | Update Role | 🔒 |

## Documents
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/documents` | List Documents | 🔒 |
| `POST` | `/api/api/documents` | Upload | 🔒 |
| `DELETE` | `/api/api/documents/{did}` | Delete | 🔒 |
| `GET` | `/api/api/documents/{did}/download` | Download | 🔒 |

## Employees
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/employees` | List Employees | 🔒 |
| `POST` | `/api/api/employees` | Create Employee | 🔒 |
| `PATCH` | `/api/api/employees/me/profile` | Update My Profile | 🔒 |
| `DELETE` | `/api/api/employees/{emp_id}` | Delete Employee | 🔒 |
| `GET` | `/api/api/employees/{emp_id}` | Get Employee | 🔒 |
| `PATCH` | `/api/api/employees/{emp_id}` | Update Employee | 🔒 |
| `POST` | `/api/api/employees/{emp_id}/assign` | Assign Department Role | 🔒 |
| `POST` | `/api/api/employees/{emp_id}/terminate` | Terminate | 🔒 |

## HR Interventions
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/interventions` | List Interventions | 🔒 |
| `POST` | `/api/api/interventions` | Create | 🔒 |
| `GET` | `/api/api/interventions/stats` | Stats | 🔒 |
| `GET` | `/api/api/interventions/suggest/{emp_id}` | Suggest | 🔒 |
| `GET` | `/api/api/interventions/{iid}` | Get One | 🔒 |
| `PATCH` | `/api/api/interventions/{iid}` | Update | 🔒 |

## Leave
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/leave` | List Leave | 🔒 |
| `POST` | `/api/api/leave` | Apply Leave | 🔒 |
| `GET` | `/api/api/leave/balance` | Balance | 🔒 |
| `GET` | `/api/api/leave/policies` | Policies | 🔒 |
| `POST` | `/api/api/leave/policies` | Create Policy | 🔒 |
| `PUT` | `/api/api/leave/policies/{pid}` | Update Policy | 🔒 |
| `GET` | `/api/api/leave/report` | Leave Report | 🔒 |
| `POST` | `/api/api/leave/{leave_id}/cancel` | Cancel Leave | 🔒 |
| `PATCH` | `/api/api/leave/{leave_id}/review` | Review Leave | 🔒 |

## Notifications & Alerts
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/alerts` | List Alerts | 🔒 |
| `PATCH` | `/api/api/alerts/{aid}` | Update Alert | 🔒 |
| `GET` | `/api/api/notifications` | List Notifications | 🔒 |
| `POST` | `/api/api/notifications/read-all` | Mark All Read | 🔒 |
| `POST` | `/api/api/notifications/send` | Send Notification | 🔒 |
| `GET` | `/api/api/notifications/unread-count` | Unread Count | 🔒 |
| `DELETE` | `/api/api/notifications/{nid}` | Delete Notification | 🔒 |
| `PATCH` | `/api/api/notifications/{nid}/read` | Mark Read | 🔒 |

## Payroll
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/payroll` | List Payroll | 🔒 |
| `POST` | `/api/api/payroll/generate` | Generate | 🔒 |
| `GET` | `/api/api/payroll/summary` | Summary | 🔒 |
| `PATCH` | `/api/api/payroll/{pid}` | Update Payroll | 🔒 |
| `GET` | `/api/api/payroll/{pid}/payslip` | Payslip | 🔒 |

## Performance
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/performance/goals` | List Goals | 🔒 |
| `POST` | `/api/api/performance/goals` | Create Goal | 🔒 |
| `DELETE` | `/api/api/performance/goals/{gid}` | Delete Goal | 🔒 |
| `PATCH` | `/api/api/performance/goals/{gid}` | Update Goal | 🔒 |
| `GET` | `/api/api/performance/reviews` | List Reviews | 🔒 |
| `POST` | `/api/api/performance/reviews` | Create Review | 🔒 |
| `GET` | `/api/api/performance/summary/{employee_id}` | Summary | 🔒 |

## Reports & Export
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/reports/attendance` | Attendance Report | 🔒 |
| `GET` | `/api/api/reports/attrition` | Attrition Report | 🔒 |
| `GET` | `/api/api/reports/employees` | Employees Report | 🔒 |
| `GET` | `/api/api/reports/leave` | Leave Report | 🔒 |
| `GET` | `/api/api/reports/payroll` | Payroll Report | 🔒 |

## Risk Monitoring & Live Workforce
| Method | Path | Summary | Auth |
|---|---|---|---|
| `POST` | `/api/api/monitoring/activity` | Ingest Activity | 🔒 |
| `GET` | `/api/api/monitoring/feed` | Feed | 🔒 |
| `GET` | `/api/api/monitoring/high-risk` | High Risk | 🔒 |
| `GET` | `/api/api/monitoring/instability` | Instability | 🔒 |
| `POST` | `/api/api/monitoring/instability/scan` | Instability Scan | 🔒 |
| `GET` | `/api/api/monitoring/logs` | Logs | 🔒 |
| `GET` | `/api/api/monitoring/risk-changes` | Risk Changes | 🔒 |

## System
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/health` | Health | public |

## Tasks & Workflow
| Method | Path | Summary | Auth |
|---|---|---|---|
| `GET` | `/api/api/tasks` | List Tasks | 🔒 |
| `POST` | `/api/api/tasks` | Create | 🔒 |
| `GET` | `/api/api/tasks/stats` | Stats | 🔒 |
| `DELETE` | `/api/api/tasks/{tid}` | Delete | 🔒 |
| `PATCH` | `/api/api/tasks/{tid}` | Update | 🔒 |
