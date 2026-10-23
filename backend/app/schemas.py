"""Pydantic request/response schemas."""
from datetime import datetime, date, time
from typing import Optional, Literal, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class UserCreateIn(RegisterIn):
    role: Literal["ADMIN", "HR", "MANAGER", "EMPLOYEE"] = "EMPLOYEE"
    employee_id: Optional[int] = None


class UserUpdateIn(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Literal["ADMIN", "HR", "MANAGER", "EMPLOYEE"]] = None
    is_active: Optional[bool] = None
    employee_id: Optional[int] = None


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    employee_id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------- Departments / Roles ----------
class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    budget: float = 0


class DepartmentOut(ORM, DepartmentIn):
    id: int


class JobRoleIn(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    department_id: Optional[int] = None
    level: int = Field(1, ge=1, le=5)
    min_salary: float = 0
    max_salary: float = 0


class JobRoleOut(ORM, JobRoleIn):
    id: int


# ---------- Employees ----------
class EmployeeBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: Optional[str] = None
    gender: Optional[str] = None
    age: int = Field(30, ge=16, le=75)
    marital_status: str = "Single"
    education: int = Field(3, ge=1, le=5)
    address: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    manager_id: Optional[int] = None
    shift_id: Optional[int] = None
    hire_date: date = Field(default_factory=date.today)
    monthly_salary: float = Field(0, ge=0)
    job_level: int = Field(1, ge=1, le=5)
    distance_from_home: float = Field(5, ge=0, le=500)
    years_at_company: float = Field(0, ge=0, le=60)
    years_since_promotion: float = Field(0, ge=0, le=60)
    total_working_years: float = Field(0, ge=0, le=60)
    num_companies_worked: int = Field(1, ge=0, le=30)
    overtime: bool = False
    job_satisfaction: int = Field(3, ge=1, le=4)
    environment_satisfaction: int = Field(3, ge=1, le=4)
    work_life_balance: int = Field(3, ge=1, le=4)
    training_times_last_year: int = Field(2, ge=0, le=20)
    performance_rating: int = Field(3, ge=1, le=4)
    stock_option_level: int = Field(0, ge=0, le=3)


class EmployeeCreate(EmployeeBase):
    employee_code: Optional[str] = None


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = Field(None, ge=16, le=75)
    marital_status: Optional[str] = None
    education: Optional[int] = Field(None, ge=1, le=5)
    address: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    manager_id: Optional[int] = None
    shift_id: Optional[int] = None
    status: Optional[Literal["active", "terminated", "on_leave"]] = None
    monthly_salary: Optional[float] = Field(None, ge=0)
    job_level: Optional[int] = Field(None, ge=1, le=5)
    distance_from_home: Optional[float] = Field(None, ge=0)
    years_at_company: Optional[float] = Field(None, ge=0)
    years_since_promotion: Optional[float] = Field(None, ge=0)
    total_working_years: Optional[float] = Field(None, ge=0)
    num_companies_worked: Optional[int] = Field(None, ge=0)
    overtime: Optional[bool] = None
    job_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    environment_satisfaction: Optional[int] = Field(None, ge=1, le=4)
    work_life_balance: Optional[int] = Field(None, ge=1, le=4)
    training_times_last_year: Optional[int] = Field(None, ge=0)
    performance_rating: Optional[int] = Field(None, ge=1, le=4)
    stock_option_level: Optional[int] = Field(None, ge=0, le=3)


class EmployeeOut(ORM, EmployeeBase):
    id: int
    employee_code: str
    status: str
    termination_date: Optional[date] = None
    department_name: Optional[str] = None
    role_title: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    size: int


# ---------- Attendance / Shifts ----------
class ShiftIn(BaseModel):
    name: str
    start_time: time
    end_time: time
    standard_hours: float = 8.0


class ShiftOut(ORM, ShiftIn):
    id: int


class ShiftAssignIn(BaseModel):
    employee_id: int
    shift_id: int


class CheckIn(BaseModel):
    employee_id: Optional[int] = None  # HR may check in on behalf; employees use self


class AttendanceOut(ORM):
    id: int
    employee_id: int
    work_date: date
    check_in: Optional[datetime]
    check_out: Optional[datetime]
    working_hours: float
    overtime_hours: float
    status: str


# ---------- Leave ----------
class LeavePolicyIn(BaseModel):
    leave_type: str
    annual_quota: int = Field(12, ge=0, le=365)
    carry_forward: bool = False
    description: Optional[str] = None


class LeavePolicyOut(ORM, LeavePolicyIn):
    id: int


class LeaveApplyIn(BaseModel):
    employee_id: Optional[int] = None
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str] = Field(None, max_length=500)


class LeaveReviewIn(BaseModel):
    action: Literal["approve", "reject"]
    comment: Optional[str] = None


class LeaveOut(ORM):
    id: int
    employee_id: int
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: Optional[str]
    status: str
    review_comment: Optional[str]
    created_at: datetime
    employee_name: Optional[str] = None


# ---------- Payroll ----------
class PayrollGenerateIn(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    employee_id: Optional[int] = None
    bonus: float = 0
    incentive: float = 0


class PayrollUpdateIn(BaseModel):
    bonus: Optional[float] = Field(None, ge=0)
    incentive: Optional[float] = Field(None, ge=0)
    other_deductions: Optional[float] = Field(None, ge=0)
    status: Optional[Literal["generated", "paid"]] = None


class PayrollOut(ORM):
    id: int
    employee_id: int
    month: int
    year: int
    basic: float
    hra: float
    allowances: float
    overtime_pay: float
    bonus: float
    incentive: float
    gross: float
    tax: float
    pf_deduction: float
    other_deductions: float
    total_deductions: float
    net_pay: float
    status: str
    employee_name: Optional[str] = None


# ---------- Notifications ----------
class NotificationOut(ORM):
    id: int
    title: str
    message: str
    category: str
    priority: str
    is_read: bool
    link: Optional[str]
    created_at: datetime


class NotificationIn(BaseModel):
    user_id: Optional[int] = None  # None = broadcast to all active users
    title: str = Field(max_length=200)
    message: str = Field(max_length=600)
    priority: Literal["low", "medium", "high", "critical"] = "low"


# ---------- Chat ----------
class ChatSendIn(BaseModel):
    receiver_id: int
    content: str = Field(min_length=1, max_length=4000)


class ChatOut(ORM):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime


# ---------- Tasks / Perf ----------
class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    employee_id: Optional[int] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    priority: Optional[Literal["low", "medium", "high", "critical"]] = None
    status: Optional[Literal["todo", "in_progress", "done", "cancelled"]] = None
    due_date: Optional[date] = None


class ReviewIn(BaseModel):
    employee_id: int
    period: str = Field(max_length=20)
    rating: int = Field(ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    comments: Optional[str] = None


class GoalIn(BaseModel):
    employee_id: int
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = None
    progress: int = Field(0, ge=0, le=100)
    due_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[Literal["in_progress", "completed", "at_risk"]] = None
    due_date: Optional[date] = None


# ---------- AI ----------
class InterventionIn(BaseModel):
    employee_id: int
    title: str
    recommendation: str
    priority: Literal["low", "medium", "high", "critical"] = "high"
    assigned_to: Optional[int] = None
    follow_up_date: Optional[date] = None


class InterventionUpdate(BaseModel):
    status: Optional[Literal["open", "in_progress", "completed", "dismissed"]] = None
    outcome: Optional[Literal["retained", "left", "unknown"]] = None
    assigned_to: Optional[int] = None
    follow_up_date: Optional[date] = None
    note: Optional[str] = Field(None, max_length=500)


class ActivityIn(BaseModel):
    """Simulates / ingests an employee activity change that triggers risk recalculation."""
    employee_id: int
    event_type: Literal["overtime_spike", "late_arrival", "unplanned_absence", "satisfaction_drop",
                        "promotion_denied", "salary_change", "training_completed", "manager_change", "custom"]
    value: Optional[float] = None
    note: Optional[str] = None
