"""SQLAlchemy ORM models – WorkForce AI Pro database schema (30 modules)."""
from datetime import datetime, date, time
from typing import Optional
from sqlalchemy import (String, Integer, Float, Boolean, Date, DateTime, Time, Text, ForeignKey,
                        UniqueConstraint, Index, JSON, Numeric)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


# ---------- Roles / constants ----------
ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_EMPLOYEE = "ADMIN", "HR", "MANAGER", "EMPLOYEE"
ROLES = (ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_EMPLOYEE)


# ============ MODULE 1/26: Auth & RBAC ============
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_EMPLOYEE, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, unique=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    employee = relationship("Employee", foreign_keys=[employee_id], lazy="joined")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ============ MODULE 3: Departments & Roles ============
class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    budget: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobRole(Base):
    __tablename__ = "job_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    min_salary: Mapped[float] = mapped_column(Float, default=0)
    max_salary: Mapped[float] = mapped_column(Float, default=0)
    __table_args__ = (UniqueConstraint("title", "department_id", name="uq_role_title_dept"),)


# ============ MODULE 4: Shifts ============
class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    standard_hours: Mapped[float] = mapped_column(Float, default=8.0)


# ============ MODULE 2: Employees ============
class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    age: Mapped[int] = mapped_column(Integer, default=30)
    marital_status: Mapped[str] = mapped_column(String(15), default="Single")
    education: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_roles.id", ondelete="SET NULL"), nullable=True, index=True)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    hire_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(15), default="active", index=True)  # active|terminated|on_leave
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    monthly_salary: Mapped[float] = mapped_column(Float, default=0)
    # --- HR attributes used as ML features ---
    job_level: Mapped[int] = mapped_column(Integer, default=1)
    distance_from_home: Mapped[float] = mapped_column(Float, default=5)
    years_at_company: Mapped[float] = mapped_column(Float, default=0)
    years_since_promotion: Mapped[float] = mapped_column(Float, default=0)
    total_working_years: Mapped[float] = mapped_column(Float, default=0)
    num_companies_worked: Mapped[int] = mapped_column(Integer, default=1)
    overtime: Mapped[bool] = mapped_column(Boolean, default=False)
    job_satisfaction: Mapped[int] = mapped_column(Integer, default=3)  # 1-4
    environment_satisfaction: Mapped[int] = mapped_column(Integer, default=3)
    work_life_balance: Mapped[int] = mapped_column(Integer, default=3)
    training_times_last_year: Mapped[int] = mapped_column(Integer, default=2)
    performance_rating: Mapped[int] = mapped_column(Integer, default=3)  # 1-4
    stock_option_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    department = relationship("Department", lazy="joined")
    role = relationship("JobRole", lazy="joined")
    shift = relationship("Shift", lazy="joined")
    manager = relationship("Employee", remote_side=[id], lazy="select")

    __table_args__ = (Index("ix_emp_dept_status", "department_id", "status"),)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ============ MODULE 4: Attendance ============
class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    work_date: Mapped[date] = mapped_column(Date)
    check_in: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    working_hours: Mapped[float] = mapped_column(Float, default=0)
    overtime_hours: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(15), default="present")  # present|late|absent|half_day
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_att_emp_date"),
                      Index("ix_att_date", "work_date"))


# ============ MODULE 5: Leave ============
class LeavePolicy(Base):
    __tablename__ = "leave_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    leave_type: Mapped[str] = mapped_column(String(30), unique=True)
    annual_quota: Mapped[int] = mapped_column(Integer, default=12)
    carry_forward: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="pending", index=True)  # pending|approved|rejected|cancelled
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    employee = relationship("Employee", lazy="joined")


# ============ MODULE 6: Payroll ============
class Payroll(Base):
    __tablename__ = "payroll"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    month: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    basic: Mapped[float] = mapped_column(Float, default=0)
    hra: Mapped[float] = mapped_column(Float, default=0)
    allowances: Mapped[float] = mapped_column(Float, default=0)
    overtime_pay: Mapped[float] = mapped_column(Float, default=0)
    bonus: Mapped[float] = mapped_column(Float, default=0)
    incentive: Mapped[float] = mapped_column(Float, default=0)
    gross: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    pf_deduction: Mapped[float] = mapped_column(Float, default=0)
    other_deductions: Mapped[float] = mapped_column(Float, default=0)
    total_deductions: Mapped[float] = mapped_column(Float, default=0)
    net_pay: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(15), default="generated")  # generated|paid
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    employee = relationship("Employee", lazy="joined")
    __table_args__ = (UniqueConstraint("employee_id", "month", "year", name="uq_payroll_emp_period"),
                      Index("ix_payroll_period", "year", "month"))


# ============ MODULE 7/17: Notifications & Alerts ============
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(600))
    category: Mapped[str] = mapped_column(String(30), default="system")  # system|leave|payroll|risk|task|chat
    priority: Mapped[str] = mapped_column(String(10), default="low")  # low|medium|high|critical
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    link: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_notif_user_read", "user_id", "is_read"),)


class Alert(Base):
    """AI / system generated workforce alert (Module 13 & 17)."""
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(30))  # high_risk|risk_escalation|instability|overtime|absence
    severity: Mapped[str] = mapped_column(String(10), default="medium")  # low|medium|high|critical
    message: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(15), default="open", index=True)  # open|acknowledged|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    employee = relationship("Employee", lazy="joined")


# ============ MODULE 8: Chat ============
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_chat_pair", "sender_id", "receiver_id", "created_at"),
                      Index("ix_chat_recv_read", "receiver_id", "is_read"))


# ============ MODULE 9: Documents ============
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40), default="other")
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ============ MODULE 11/12: Datasets & ML ============
class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(400))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    attrition_rate: Mapped[float] = mapped_column(Float, default=0)
    failed_report: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="validated")  # validated|rejected
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("name", "version", name="uq_dataset_version"),)


class MLModel(Base):
    __tablename__ = "ml_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(60))
    accuracy: Mapped[float] = mapped_column(Float)
    precision_score: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    roc_auc: Mapped[float] = mapped_column(Float)
    cv_roc_auc: Mapped[float] = mapped_column(Float, default=0)
    train_rows: Mapped[int] = mapped_column(Integer, default=0)
    feature_importance: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    comparison: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confusion: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str] = mapped_column(String(400))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trained_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    model_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ml_models.id", ondelete="SET NULL"), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float)  # 0..1
    risk_level: Mapped[str] = mapped_column(String(10))  # low|medium|high
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    top_factors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    employee = relationship("Employee", lazy="joined")
    __table_args__ = (Index("ix_pred_emp_time", "employee_id", "created_at"),)


# ============ MODULE 13: Monitoring ============
class MonitoringLog(Base):
    __tablename__ = "monitoring_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(40))  # risk_changed|entered_high_risk|left_high_risk|recalculated
    old_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_score: Mapped[float] = mapped_column(Float)
    old_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    new_level: Mapped[str] = mapped_column(String(10))
    trigger: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    employee = relationship("Employee", lazy="joined")


# ============ MODULE 18: Live activity ============
class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info|warning|critical
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    employee = relationship("Employee", lazy="joined")


# ============ MODULE 16: Interventions ============
class Intervention(Base):
    __tablename__ = "interventions"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    recommendation: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="high")
    status: Mapped[str] = mapped_column(String(15), default="open", index=True)  # open|in_progress|completed|dismissed
    outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # retained|left|unknown
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    employee = relationship("Employee", lazy="joined")
    logs = relationship("InterventionLog", back_populates="intervention", cascade="all, delete-orphan", order_by="InterventionLog.id")


class InterventionLog(Base):
    __tablename__ = "intervention_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    intervention_id: Mapped[int] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    intervention = relationship("Intervention", back_populates="logs")


# ============ MODULE 20: Audit ============
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)  # CREATE|UPDATE|DELETE|LOGIN|...
    entity: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ============ MODULE 21: Tasks ============
class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(15), default="todo", index=True)  # todo|in_progress|done|cancelled
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assignee = relationship("User", foreign_keys=[assigned_to], lazy="joined")
    employee = relationship("Employee", lazy="joined")


# ============ MODULE 22: Performance ============
class PerformanceReview(Base):
    __tablename__ = "performance_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    period: Mapped[str] = mapped_column(String(20))  # e.g. 2026-Q3
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    strengths: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    improvements: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    employee = relationship("Employee", lazy="joined")


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    status: Mapped[str] = mapped_column(String(15), default="in_progress")  # in_progress|completed|at_risk
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    employee = relationship("Employee", lazy="joined")
