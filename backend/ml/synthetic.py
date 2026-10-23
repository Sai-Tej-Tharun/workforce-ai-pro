"""Synthetic HR dataset generator (IBM-HR-like) used to bootstrap the platform.

Attrition is drawn from a hidden logistic model so that the signal is realistic
(overtime, low satisfaction, stagnation, low pay, short tenure ... drive attrition)
while still containing noise, so the trained model has an honest, non-perfect accuracy.
"""
import numpy as np
import pandas as pd

DEPARTMENTS = ["Engineering", "Sales", "Human Resources", "Finance", "Operations", "Customer Support"]


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


def generate(n: int = 3000, seed: int = 7, target_rate: float = 0.19) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    age = np.clip(rng.normal(36, 9, n).round(), 20, 62).astype(int)
    total_years = np.clip(age - 21 - rng.integers(0, 6, n), 0, 40)
    job_level = np.clip(rng.choice([1, 2, 3, 4, 5], n, p=[.33, .33, .17, .1, .07]), 1, 5)
    income = np.clip(rng.normal(3200 + job_level * 2300 + total_years * 90, 1100, n), 2000, 20000).round(0)
    years_at = np.clip((total_years * rng.uniform(0.05, 0.7, n)).round(1), 0, 35)
    since_promo = np.clip((years_at * rng.uniform(0, 0.9, n)).round(1), 0, 15)
    df = pd.DataFrame({
        "employee_number": np.arange(1001, 1001 + n),
        "age": age,
        "monthly_income": income,
        "distance_from_home": rng.integers(1, 30, n),
        "job_level": job_level,
        "job_satisfaction": rng.choice([1, 2, 3, 4], n, p=[.2, .2, .32, .28]),
        "environment_satisfaction": rng.choice([1, 2, 3, 4], n, p=[.2, .2, .32, .28]),
        "work_life_balance": rng.choice([1, 2, 3, 4], n, p=[.06, .24, .52, .18]),
        "years_at_company": years_at,
        "years_since_promotion": since_promo,
        "total_working_years": total_years,
        "num_companies_worked": rng.choice(range(0, 9), n, p=[.14, .35, .12, .1, .09, .07, .06, .04, .03]),
        "training_times_last_year": rng.choice(range(0, 7), n, p=[.04, .06, .3, .35, .13, .08, .04]),
        "performance_rating": rng.choice([2, 3, 4], n, p=[.08, .78, .14]),
        "stock_option_level": rng.choice([0, 1, 2, 3], n, p=[.43, .4, .1, .07]),
        "education": rng.choice([1, 2, 3, 4, 5], n, p=[.12, .19, .39, .27, .03]),
        "overtime": rng.choice(["Yes", "No"], n, p=[.28, .72]),
        "marital_status": rng.choice(["Single", "Married", "Divorced"], n, p=[.32, .46, .22]),
        "department": rng.choice(DEPARTMENTS, n, p=[.25, .2, .05, .1, .25, .15]),
        "late_days_90": np.clip(rng.poisson(2.0, n), 0, 30),
        "unplanned_leave_days_90": np.clip(rng.poisson(1.2, n), 0, 30),
        "avg_overtime_hours": np.clip(rng.gamma(1.5, 0.45, n), 0, 6).round(2),
    })
    ot = (df.overtime == "Yes").astype(int)
    z = (1.15 * ot + 0.55 * (3 - df.job_satisfaction) + 0.35 * (3 - df.environment_satisfaction)
         + 0.40 * (3 - df.work_life_balance) + 0.20 * df.years_since_promotion.clip(0, 8)
         - 0.55 * (df.monthly_income - 5500) / 3000 + 0.75 * (df.years_at_company < 2)
         - 0.06 * df.years_at_company.clip(0, 10) + 0.05 * df.distance_from_home
         + 0.22 * df.num_companies_worked - 0.5 * (df.stock_option_level > 0)
         + 0.45 * (df.marital_status == "Single") - 0.025 * (df.age - 35)
         + 0.12 * df.late_days_90 + 0.22 * df.unplanned_leave_days_90 + 0.30 * df.avg_overtime_hours
         - 0.12 * df.training_times_last_year + (df.department == "Sales") * 0.35
         + 0.9 * ot * (df.job_satisfaction <= 2) + 0.7 * ((df.years_since_promotion >= 4) & (df.job_level <= 2))
         + rng.normal(0, 0.35, n))
    lo, hi = -15.0, 15.0  # bisection on intercept to hit the target attrition rate
    for _ in range(50):
        mid = (lo + hi) / 2
        if _sigmoid(z + mid).mean() > target_rate:
            hi = mid
        else:
            lo = mid
    p = _sigmoid(z + (lo + hi) / 2)
    df["attrition"] = np.where(rng.random(n) < p, "Yes", "No")
    return df


if __name__ == "__main__":
    d = generate()
    print(d.attrition.value_counts(normalize=True))
