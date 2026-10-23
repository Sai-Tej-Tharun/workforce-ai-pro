"""Module 6: Payroll (generation, salary breakdown, tax, bonuses, payslip PDF)."""
import io
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Payroll, Employee, Attendance, LeaveRequest, User, ROLE_ADMIN, ROLE_HR
from ..schemas import PayrollGenerateIn, PayrollUpdateIn, PayrollOut
from ..security import get_current_user, hr_admin
from ..services.common import audit, notify

router = APIRouter(prefix="/payroll", tags=["Payroll"])

# Progressive annual tax slabs (illustrative): (upper_limit, rate)
SLABS = [(12_000, 0.0), (36_000, 0.10), (72_000, 0.20), (150_000, 0.30), (float("inf"), 0.35)]
WORK_DAYS, DAY_HOURS = 22, 8


def annual_tax(annual_gross: float) -> float:
    tax, prev = 0.0, 0.0
    for limit, rate in SLABS:
        if annual_gross > prev:
            tax += (min(annual_gross, limit) - prev) * rate
        prev = limit
    return tax


def compute(emp: Employee, overtime_hours: float, unpaid_days: int, bonus: float, incentive: float, other: float = 0.0) -> dict:
    s = emp.monthly_salary
    basic, hra, allow = round(s * 0.50, 2), round(s * 0.20, 2), round(s * 0.30, 2)
    hourly = s / (WORK_DAYS * DAY_HOURS)
    ot_pay = round(overtime_hours * hourly * 1.5, 2)
    gross = round(basic + hra + allow + ot_pay + bonus + incentive, 2)
    tax = round(annual_tax(gross * 12) / 12, 2)
    pf = round(basic * 0.12, 2)
    unpaid = round(unpaid_days * s / WORK_DAYS, 2)
    ded = round(tax + pf + other + unpaid, 2)
    return {"basic": basic, "hra": hra, "allowances": allow, "overtime_pay": ot_pay, "bonus": bonus,
            "incentive": incentive, "gross": gross, "tax": tax, "pf_deduction": pf,
            "other_deductions": round(other + unpaid, 2), "total_deductions": ded, "net_pay": round(gross - ded, 2)}


def _out(p: Payroll) -> dict:
    d = PayrollOut.model_validate(p).model_dump(mode="json")
    d["employee_name"] = p.employee.full_name if p.employee else None
    d["employee_code"] = p.employee.employee_code if p.employee else None
    return d


@router.post("/generate")
def generate(body: PayrollGenerateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    start = date(body.year, body.month, 1)
    end = date(body.year + (body.month == 12), body.month % 12 + 1, 1)
    q = select(Employee).where(Employee.status != "terminated", Employee.hire_date < end)
    if body.employee_id:
        q = q.where(Employee.id == body.employee_id)
    emps = db.scalars(q).unique().all()
    if not emps:
        raise HTTPException(404, "No eligible employees")
    existing = set(db.scalars(select(Payroll.employee_id).where(Payroll.month == body.month, Payroll.year == body.year)))
    ot = dict(db.execute(select(Attendance.employee_id, func.sum(Attendance.overtime_hours))
                         .where(Attendance.work_date >= start, Attendance.work_date < end).group_by(Attendance.employee_id)).all())
    unpaid = dict(db.execute(select(LeaveRequest.employee_id, func.sum(LeaveRequest.days)).where(
        LeaveRequest.status == "approved", LeaveRequest.leave_type == "Unpaid",
        LeaveRequest.start_date >= start, LeaveRequest.start_date < end).group_by(LeaveRequest.employee_id)).all())
    created, skipped = 0, 0
    for e in emps:
        if e.id in existing:
            skipped += 1
            continue
        vals = compute(e, float(ot.get(e.id) or 0), int(unpaid.get(e.id) or 0), body.bonus, body.incentive)
        db.add(Payroll(employee_id=e.id, month=body.month, year=body.year, **vals))
        created += 1
        eu = db.scalar(select(User.id).where(User.employee_id == e.id))
        if eu:
            notify(db, [eu], "Payslip available", f"Your payslip for {body.month:02d}/{body.year} is ready.", "payroll", "low", "/payroll")
    db.commit()
    audit(db, user, "GENERATE", "payroll", f"{body.month}/{body.year}", {"created": created, "skipped": skipped}, request)
    return {"created": created, "skipped_existing": skipped, "month": body.month, "year": body.year}


@router.get("")
def list_payroll(month: Optional[int] = None, year: Optional[int] = None, employee_id: Optional[int] = None,
                 status: Optional[str] = None, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Payroll).join(Employee, Employee.id == Payroll.employee_id)
    if user.role in (ROLE_ADMIN, ROLE_HR):
        if employee_id: q = q.where(Payroll.employee_id == employee_id)
    else:  # MANAGER & EMPLOYEE can see only their own payroll
        q = q.where(Payroll.employee_id == (user.employee_id or -1))
    if month: q = q.where(Payroll.month == month)
    if year: q = q.where(Payroll.year == year)
    if status: q = q.where(Payroll.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Payroll.year.desc(), Payroll.month.desc(), Payroll.id).offset((page - 1) * size).limit(size)).unique().all()
    return {"items": [_out(p) for p in rows], "total": total, "page": page, "size": size}


@router.patch("/{pid}")
def update_payroll(pid: int, body: PayrollUpdateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(hr_admin)):
    p = db.get(Payroll, pid)
    if not p:
        raise HTTPException(404, "Payroll record not found")
    data = body.model_dump(exclude_unset=True)
    if p.status == "paid" and set(data) - {"status"}:
        raise HTTPException(409, "Paid payroll cannot be modified")
    e = p.employee
    bonus = data.get("bonus", p.bonus)
    inc = data.get("incentive", p.incentive)
    other = data.get("other_deductions", p.other_deductions)
    vals = compute(e, p.overtime_pay / (e.monthly_salary / (WORK_DAYS * DAY_HOURS) * 1.5) if e.monthly_salary else 0, 0, bonus, inc, other)
    for k, v in vals.items():
        setattr(p, k, v)
    if "status" in data:
        p.status = data["status"]
    db.commit()
    audit(db, user, "UPDATE", "payroll", pid, data, request)
    return _out(p)


@router.get("/summary")
def summary(year: int = Query(default_factory=lambda: date.today().year), db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    rows = db.execute(select(Payroll.month, func.count(), func.sum(Payroll.gross), func.sum(Payroll.total_deductions),
                             func.sum(Payroll.net_pay), func.sum(Payroll.bonus + Payroll.incentive), func.sum(Payroll.overtime_pay))
                      .where(Payroll.year == year).group_by(Payroll.month).order_by(Payroll.month)).all()
    return [{"month": m, "employees": n, "gross": round(g or 0, 2), "deductions": round(d or 0, 2), "net": round(nt or 0, 2),
             "bonus_incentive": round(b or 0, 2), "overtime_pay": round(o or 0, 2)} for m, n, g, d, nt, b, o in rows]


@router.get("/{pid}/payslip")
def payslip(pid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    p = db.get(Payroll, pid)
    if not p:
        raise HTTPException(404, "Payroll record not found")
    if user.role not in (ROLE_ADMIN, ROLE_HR) and p.employee_id != user.employee_id:
        raise HTTPException(403, "Not allowed")
    e, st = p.employee, getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Payslip {p.month:02d}-{p.year}")
    money = lambda v: f"{v:,.2f}"  # noqa: E731
    earn = [["Earnings", "Amount"], ["Basic", money(p.basic)], ["HRA", money(p.hra)], ["Allowances", money(p.allowances)],
            ["Overtime pay", money(p.overtime_pay)], ["Bonus", money(p.bonus)], ["Incentive", money(p.incentive)], ["Gross", money(p.gross)]]
    ded = [["Deductions", "Amount"], ["Income tax", money(p.tax)], ["Provident fund", money(p.pf_deduction)],
           ["Other / unpaid leave", money(p.other_deductions)], ["Total deductions", money(p.total_deductions)]]
    style = TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")])
    t1, t2 = Table(earn, colWidths=[300, 120]), Table(ded, colWidths=[300, 120])
    t1.setStyle(style); t2.setStyle(style)
    net = Table([["NET PAY", money(p.net_pay)]], colWidths=[300, 120])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                             ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 13)]))
    doc.build([Paragraph("WorkForce AI Pro – Payslip", st["Title"]),
               Paragraph(f"<b>{e.full_name}</b> ({e.employee_code}) &nbsp;|&nbsp; {e.department.name if e.department else '-'} &nbsp;|&nbsp; "
                         f"Period: {p.month:02d}/{p.year}", st["Normal"]), Spacer(1, 14), t1, Spacer(1, 10), t2, Spacer(1, 10), net])
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="payslip_{e.employee_code}_{p.year}_{p.month:02d}.pdf"'})
