"""
Risk Profiler — Subjective + Objective Composite Risk Scoring
==============================================================
Implements the Wealthfront-inspired dual risk assessment:
- Subjective: 10-question Likert-scale quiz (risk willingness)
- Objective: Financial capacity score (risk ability)
- Composite: Weighted blend with conservative bias

Reference: Wealthfront Investment Methodology, Step 4 (Risk Tolerance).
"""

import math
from backend.config import (
    RISK_SCORE_WEIGHTS,
    RISK_BANDS,
    RISK_DECAY_ENABLED,
    RISK_DECAY_HORIZON_YEARS,
    RISK_DECAY_MAX_RISK,
)


# =============================================================
# QUESTION DEFINITIONS
# =============================================================

QUIZ_QUESTIONS = [
    {
        "id": 1,
        "text": "If your portfolio dropped 20% in a month, what would you do?",
        "options": [
            "Sell everything",
            "Sell some holdings",
            "Hold and wait",
            "Buy a little more",
            "Buy aggressively — it's on sale",
        ],
    },
    {
        "id": 2,
        "text": "What is your primary investment goal?",
        "options": [
            "Capital preservation",
            "Steady income",
            "Balanced growth",
            "Capital growth",
            "Maximum growth at any cost",
        ],
    },
    {
        "id": 3,
        "text": "How long is your investment horizon?",
        "options": [
            "Less than 1 year",
            "1–3 years",
            "3–5 years",
            "5–10 years",
            "10+ years",
        ],
    },
    {
        "id": 4,
        "text": "What percentage of your net worth is this investment?",
        "options": [
            "Less than 5%",
            "5–15%",
            "15–30%",
            "30–50%",
            "More than 50%",
        ],
        "inverted": True,  # Higher % = higher risk exposure = LOWER score
    },
    {
        "id": 5,
        "text": "How would you describe your investment knowledge?",
        "options": [
            "None",
            "Basic",
            "Intermediate",
            "Advanced",
            "Expert / Professional",
        ],
    },
    {
        "id": 6,
        "text": "Do you have 6+ months of emergency savings outside this investment?",
        "options": [
            "No, I don't have emergency savings",
            "Partial — only 1–3 months",
            "Yes, I have 6+ months",
            "Yes, I have 12+ months",
            "Yes, well beyond 12 months",
        ],
    },
    {
        "id": 7,
        "text": "How stable is your income?",
        "options": [
            "Very unstable",
            "Somewhat unstable",
            "Moderate stability",
            "Stable",
            "Very stable / multiple sources",
        ],
    },
    {
        "id": 8,
        "text": "Have you invested in equities before?",
        "options": [
            "Never",
            "Tried once",
            "Invested a few times",
            "Invest regularly",
            "Professional / daily trader",
        ],
    },
    {
        "id": 9,
        "text": "What annual return do you expect?",
        "options": [
            "Less than 3%",
            "3–5%",
            "5–8%",
            "8–12%",
            "More than 12%",
        ],
    },
    {
        "id": 10,
        "text": "How do you feel about short-term volatility for long-term gains?",
        "options": [
            "I hate it — I want stable value",
            "I dislike it but can tolerate a bit",
            "Neutral — I understand it's part of investing",
            "I accept it as necessary",
            "I embrace it — higher volatility means opportunity",
        ],
    },
]


def compute_subjective_score(answers: list[dict]) -> float:
    """
    Score the 10-question subjective quiz.

    Each question is scored 1–5 on a Likert scale.
    For 'inverted' questions (e.g., Q4 — higher net worth % = more exposure = less capacity),
    the score is flipped: score = 6 - answer.

    The raw total (10–50) is normalised to a 1–10 scale.

    Parameters:
        answers (list[dict]): List of {"question_id": int, "answer": int (1-5)}.

    Returns:
        float: Subjective risk score on a 1–10 scale.
    """
    question_lookup = {q["id"]: q for q in QUIZ_QUESTIONS}
    total = 0.0

    for ans in answers:
        qid = ans["question_id"]
        raw = ans["answer"]
        question = question_lookup.get(qid, {})

        if question.get("inverted", False):
            raw = 6 - raw  # Invert: 5→1, 4→2, etc.

        total += raw

    # Normalise: 10 (all 1s) → 1.0, 50 (all 5s) → 10.0
    normalised = 1.0 + (total - 10) / (50 - 10) * 9.0
    return round(max(1.0, min(10.0, normalised)), 2)


def compute_objective_score(
    monthly_income: float,
    monthly_expenses: float,
    total_investable_assets: float,
    investment_amount: float,
    employment_type: str,
    has_emergency_fund: str,
) -> float:
    """
    Compute an objective financial capacity score (1–10).

    Considers:
    - Investment amount as % of total assets (lower % = higher capacity)
    - Savings rate (income - expenses) / income
    - Employment stability modifier
    - Emergency fund status

    Parameters:
        monthly_income (float): Monthly gross income in GBP.
        monthly_expenses (float): Monthly expenses in GBP.
        total_investable_assets (float): Total investable assets in GBP.
        investment_amount (float): Amount being invested in GBP.
        employment_type (str): "employed" | "self_employed" | "retired" | "student".
        has_emergency_fund (str): "no" | "partial" | "yes".

    Returns:
        float: Objective capacity score on a 1–10 scale.
    """
    # Investment concentration score (0–10): lower % = higher score
    if total_investable_assets > 0:
        concentration = investment_amount / total_investable_assets
    else:
        concentration = 1.0

    concentration_score = max(1.0, min(10.0, 10.0 * (1.0 - concentration)))

    # Savings rate score (0–10)
    if monthly_income > 0:
        savings_rate = (monthly_income - monthly_expenses) / monthly_income
        savings_score = max(1.0, min(10.0, 1.0 + savings_rate * 12.0))
    else:
        savings_score = 1.0

    # Employment stability modifier
    employment_modifiers = {
        "employed": 1.0,
        "self_employed": 0.85,
        "retired": 0.7,
        "student": 0.6,
    }
    emp_modifier = employment_modifiers.get(employment_type, 0.8)

    # Emergency fund modifier
    emergency_modifiers = {
        "no": 0.6,
        "partial": 0.8,
        "yes": 1.0,
    }
    emg_modifier = emergency_modifiers.get(has_emergency_fund, 0.7)

    # Weighted combination
    raw_score = (concentration_score * 0.5 + savings_score * 0.5) * emp_modifier * emg_modifier
    return round(max(1.0, min(10.0, raw_score)), 2)


def detect_inconsistency(answers: list[dict]) -> bool:
    """
    Detect contradictory quiz answers.

    Example: Answering Q1 = 1 (sell everything on crash) but Q9 = 5 (expect >12% returns)
    indicates inconsistency between risk behaviour and return expectations.

    Parameters:
        answers (list[dict]): Quiz answer list.

    Returns:
        bool: True if significant inconsistency detected.
    """
    answer_map = {a["question_id"]: a["answer"] for a in answers}

    # Q1 (crash behaviour) vs Q9 (expected returns)
    q1 = answer_map.get(1, 3)
    q9 = answer_map.get(9, 3)
    if abs(q1 - q9) >= 3:
        return True

    # Q10 (volatility tolerance) vs Q1 (crash behaviour)
    q10 = answer_map.get(10, 3)
    if abs(q1 - q10) >= 3:
        return True

    # Q3 (time horizon) vs Q9 (expected returns): short horizon + high returns
    q3 = answer_map.get(3, 3)
    if q3 <= 2 and q9 >= 4:
        return True

    return False


def compute_composite_score(
    subjective: float,
    objective: float,
    time_horizon_years: int,
) -> float:
    """
    Blend subjective and objective scores into a final composite risk score.

    Algorithm:
    1. Weighted blend: composite = subj * w_subj + obj * w_obj
    2. If conservative_bias is enabled AND |subj - obj| > 2:
       composite = min(subj, obj) + 0.5  (Wealthfront approach)
    3. If risk_decay is enabled AND time_horizon < threshold:
       cap the maximum score

    Parameters:
        subjective (float): Subjective quiz score (1–10).
        objective (float): Objective capacity score (1–10).
        time_horizon_years (int): Investment horizon in years.

    Returns:
        float: Final composite risk score (1–10).
    """
    w_subj = RISK_SCORE_WEIGHTS["subjective_quiz"]
    w_obj = RISK_SCORE_WEIGHTS["objective_capacity"]
    conservative_bias = RISK_SCORE_WEIGHTS["conservative_bias"]

    # Step 1: Weighted blend
    composite = subjective * w_subj + objective * w_obj

    # Step 2: Conservative bias if large disagreement
    if conservative_bias and abs(subjective - objective) > 2.0:
        composite = min(subjective, objective) + 0.5

    # Step 3: Risk score decay for short time horizons
    if RISK_DECAY_ENABLED and time_horizon_years < RISK_DECAY_HORIZON_YEARS:
        composite = min(composite, float(RISK_DECAY_MAX_RISK))

    return round(max(1.0, min(10.0, composite)), 1)


def get_risk_band(score: float) -> str:
    """
    Map a composite score to a named risk band.

    Parameters:
        score (float): Composite risk score (1–10).

    Returns:
        str: Risk band name (e.g., "Balanced").
    """
    rounded = max(1, min(10, round(score)))
    return RISK_BANDS.get(rounded, "Unknown")


def get_risk_description(score: float) -> str:
    """
    Generate a brief human-readable description of the risk profile.

    Parameters:
        score (float): Composite risk score (1–10).

    Returns:
        str: Description paragraph.
    """
    rounded = round(score)
    descriptions = {
        1: "Your profile is highly conservative. You prioritise capital preservation above all else. Your portfolio will lean heavily toward UK Gilts, bonds, and cash equivalents with minimal equity exposure.",
        2: "Your profile is very conservative. You seek stability with only modest growth. Your portfolio will be bond-heavy with a small allocation to diversified equities.",
        3: "Your profile is conservative. You want steady, reliable returns with limited downside risk. Expect a majority bond allocation with some equity diversification.",
        4: "Your profile is moderately conservative. You accept some volatility for better returns. Your portfolio balances bonds and equities, tilting slightly toward fixed income.",
        5: "Your profile is balanced. You seek a healthy mix of growth and stability. Your portfolio will maintain roughly equal exposure to equities and fixed income.",
        6: "Your profile is moderately aggressive. You favour growth and accept meaningful short-term fluctuations. Equity allocation will outweigh bonds.",
        7: "Your profile is growth-oriented. You are comfortable with significant volatility for superior long-term returns. Your portfolio will be equity-heavy.",
        8: "Your profile is aggressively growth-oriented. You embrace market swings and focus on maximum capital appreciation over the long term.",
        9: "Your profile is high-risk. You are very comfortable with large drawdowns and expect to hold for the long term. Near-maximum equity allocation.",
        10: "Your profile seeks maximum growth. You accept the highest level of volatility for the possibility of the greatest returns. Your portfolio will be almost entirely equity-focused.",
    }
    return descriptions.get(rounded, "Your risk profile has been assessed.")


def profile_user(
    quiz_answers: list[dict],
    monthly_income: float,
    monthly_expenses: float,
    total_investable_assets: float,
    investment_amount: float,
    employment_type: str,
    has_emergency_fund: str,
    time_horizon_years: int,
) -> dict:
    """
    Full risk profiling pipeline: subjective + objective → composite.

    Parameters:
        quiz_answers: List of {"question_id": int, "answer": int (1-5)}.
        monthly_income: GBP.
        monthly_expenses: GBP.
        total_investable_assets: GBP.
        investment_amount: GBP being invested.
        employment_type: "employed" | "self_employed" | "retired" | "student".
        has_emergency_fund: "no" | "partial" | "yes".
        time_horizon_years: Years.

    Returns:
        dict: {
            "subjective_score", "objective_score", "composite_score",
            "risk_band", "risk_score_int", "description",
            "has_inconsistency", "time_horizon_years"
        }
    """
    subjective = compute_subjective_score(quiz_answers)
    objective = compute_objective_score(
        monthly_income, monthly_expenses, total_investable_assets,
        investment_amount, employment_type, has_emergency_fund,
    )
    composite = compute_composite_score(subjective, objective, time_horizon_years)
    band = get_risk_band(composite)
    description = get_risk_description(composite)
    inconsistency = detect_inconsistency(quiz_answers)

    return {
        "subjective_score": subjective,
        "objective_score": objective,
        "composite_score": composite,
        "risk_band": band,
        "risk_score_int": round(composite),
        "description": description,
        "has_inconsistency": inconsistency,
        "time_horizon_years": time_horizon_years,
    }
