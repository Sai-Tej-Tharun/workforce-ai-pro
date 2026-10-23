"""Rule-based decision-support: converts model risk drivers into HR actions (Modules 16, 23)."""
from typing import Optional

# feature -> (short action title, detailed recommendation)
PLAYBOOK = {
    "overtime": ("Reduce workload", "Review workload and rebalance tasks; cap overtime and agree a recovery plan with the manager."),
    "avg_overtime_hours": ("Reduce workload", "Sustained overtime detected. Redistribute tasks, consider backfill or comp-off days."),
    "job_satisfaction": ("Stay interview", "Hold a 1:1 stay interview to understand dissatisfaction; agree 2-3 concrete changes to the role."),
    "environment_satisfaction": ("Improve work environment", "Check team dynamics, seating/remote options and manager relationship; act on feedback within 2 weeks."),
    "work_life_balance": ("Flexible work", "Offer flexible hours or hybrid/remote days and review shift assignment."),
    "years_since_promotion": ("Career path discussion", "Clarify promotion criteria and timeline; consider a stretch assignment or title review."),
    "monthly_income": ("Compensation review", "Benchmark salary against market and internal peers; consider an adjustment or retention bonus."),
    "years_at_company": ("Early-tenure engagement", "Assign a mentor/buddy and run 30-60-90 day check-ins to strengthen onboarding."),
    "distance_from_home": ("Commute relief", "Offer remote days, shuttle or relocation support to reduce commute burden."),
    "num_companies_worked": ("Engagement & growth plan", "Frequent job changes in history: emphasise growth opportunities and recognition."),
    "training_times_last_year": ("Learning & development", "Enrol in training aligned with career goals; set a development plan."),
    "stock_option_level": ("Long-term incentives", "Evaluate eligibility for equity/long-term incentive to increase retention."),
    "late_days_90": ("Wellbeing check-in", "Rising lateness is an early disengagement signal; have a supportive conversation about blockers."),
    "unplanned_leave_days_90": ("Wellbeing check-in", "Frequent unplanned absence; check on health, burnout and personal circumstances."),
    "marital_status": ("Engagement check-in", "Hold a regular career check-in and review benefits that fit the employee's situation."),
    "age": ("Engagement check-in", "Tailor growth and benefits conversation to the employee's career stage."),
    "job_level": ("Career path discussion", "Review role scope and level versus experience."),
    "performance_rating": ("Recognition & coaching", "Provide recognition or coaching based on recent performance feedback."),
    "department": ("Team health review", "Department-level attrition drivers should be reviewed with the department head."),
    "education": ("Growth plan", "Discuss education sponsorship and role alignment."),
    "total_working_years": ("Career path discussion", "Discuss next career milestone."),
}


def actions_from_factors(factors: list[dict], limit: int = 3) -> list[dict]:
    seen, out = set(), []
    for f in factors or []:
        title, text = PLAYBOOK.get(f["feature"], ("Retention check-in", "Schedule a retention conversation."))
        if title in seen:
            continue
        seen.add(title)
        out.append({"title": title, "action": text, "driver": f["label"], "impact": f["impact"]})
        if len(out) >= limit:
            break
    return out


def intervention_text(emp_name: str, score: float, factors: list[dict]) -> tuple[str, str, str]:
    actions = actions_from_factors(factors) or [{"title": "Retention check-in", "action": "Schedule a retention conversation.", "driver": "-", "impact": 0}]
    title = f"Retention plan for {emp_name}: {actions[0]['title']}"
    body = "\n".join(f"{i+1}. {a['title']} – {a['action']} (driver: {a['driver']})" for i, a in enumerate(actions))
    priority = "critical" if score >= 0.8 else "high"
    return title, body, priority
