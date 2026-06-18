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


# Questions that measure risk WILLINGNESS (psychometric attitude), as opposed to
# capacity/need. Capacity items (Q3 horizon, Q4 net-worth %, Q6 emergency fund,
# Q7 income stability) are EXCLUDED here because they are already captured by the
# objective capacity score — counting them in both would double-count capacity.
WILLINGNESS_QUESTION_IDS: tuple[int, ...] = (1, 2, 5, 8, 9, 10)


def compute_subjective_score(answers: list[dict]) -> float:
    """
    Score the subjective quiz as risk WILLINGNESS only.

    Only the willingness questions (WILLINGNESS_QUESTION_IDS) are scored, so
    capacity items are not double-counted (they live in the objective score).
    Each willingness question is 1–5; the total is normalised to a 1–10 scale
    using only the willingness questions actually answered.

    Parameters:
        answers (list[dict]): List of {"question_id": int, "answer": int (1-5)}.

    Returns:
        float: Subjective (willingness) risk score on a 1–10 scale.
    """
    question_lookup = {q["id"]: q for q in QUIZ_QUESTIONS}
    total = 0.0
    n = 0

    for ans in answers:
        qid = ans["question_id"]
        if qid not in WILLINGNESS_QUESTION_IDS:
            continue  # capacity/need items are handled by the objective score
        raw = ans["answer"]
        question = question_lookup.get(qid, {})
        if question.get("inverted", False):
            raw = 6 - raw
        total += raw
        n += 1

    if n == 0:
        return 5.0  # neutral default if no willingness answers provided

    # Normalise: all 1s → 1.0, all 5s → 10.0 (range n..5n)
    normalised = 1.0 + (total - n) / (5 * n - n) * 9.0
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
    has_inconsistency: bool = False,
) -> float:
    """
    Blend subjective (willingness) and objective (capacity) scores into a final
    composite risk score, taking the suitable risk as the LOWER of willingness
    and ability where they disagree (FCA-style).

    Algorithm:
    1. Weighted blend: composite = subj * w_subj + obj * w_obj
    2. If conservative_bias AND |subj - obj| > 2: composite = min(subj, obj) + 0.5
    3. If answers are internally inconsistent: apply a 1-point conservative
       penalty (contradictory answers → err on the side of caution).
    4. If risk_decay AND time_horizon < threshold: cap the maximum score.

    Parameters:
        subjective (float): Willingness score (1–10).
        objective (float): Capacity score (1–10).
        time_horizon_years (int): Investment horizon in years.
        has_inconsistency (bool): True if quiz answers contradict each other.

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

    # Step 3: Inconsistency penalty — contradictory answers reduce risk taken
    if has_inconsistency:
        composite = composite - 1.0

    # Step 4: Risk score decay for short time horizons
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
    # NOTE: these must describe what the engine ACTUALLY builds under the
    # mandate caps (term bonds ≤ 20%, gold ≤ 10%): de-risking is delivered via
    # the cash/ultrashort sleeve, not via large bond allocations.
    descriptions = {
        1: "Your profile is highly conservative. You prioritise capital preservation. Your portfolio will hold a large cash/ultrashort sleeve plus gilts (within the 20% bond mandate cap) and a modest, diversified equity allocation, targeting the lowest volatility the mandate permits.",
        2: "Your profile is very conservative. Expect a substantial cash/ultrashort allocation, capped bonds and gold, and a minority equity allocation for modest growth.",
        3: "Your profile is conservative. Your portfolio blends a meaningful cash/ultrashort sleeve with capped bonds and a moderate, diversified equity allocation.",
        4: "Your profile is moderately conservative. The cash sleeve shrinks and diversified equities take a larger share, with bonds and gold held within their mandate caps.",
        5: "Your profile is balanced. Expect a mid-ladder volatility target: a majority diversified-equity allocation complemented by cash, capped bonds, and gold.",
        6: "Your profile is moderately aggressive. Equities dominate, with smaller defensive sleeves; volatility targets sit above the middle of the ladder.",
        7: "Your profile is growth-oriented. You are comfortable with significant volatility. Your portfolio is equity-heavy with limited defensive ballast.",
        8: "Your profile is aggressively growth-oriented. You embrace market swings; defensive sleeves are minimal and the volatility target is near the top of the ladder.",
        9: "Your profile is high-risk. Near-maximum equity exposure with only residual defensive holdings.",
        10: "Your profile seeks maximum growth. The portfolio sits at the top of the volatility ladder: effectively all growth assets, with gold capped at 10%.",
    }
    return descriptions.get(rounded, "Your risk profile has been assessed.")


# =============================================================
# MINIMAL ONBOARDING (fewest questions — 3)
# =============================================================
# Responsible risk profiling needs willingness + capacity (horizon) + a capacity
# safety check. This collapses the 10-question quiz + 7 financial fields into 3
# questions while still covering FCA-style suitability (willingness/ability).

MINIMAL_QUIZ_QUESTIONS = [
    {
        "id": 1,
        "key": "loss_reaction",
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
        "key": "time_horizon_choice",
        "text": "When will you need this money?",
        "options": [
            "Within 1 year",
            "1–3 years",
            "3–5 years",
            "5–10 years",
            "10+ years",
        ],
    },
    {
        "id": 3,
        "key": "financial_cushion",
        "text": "How financially secure is this investment? (savings buffer & share of wealth)",
        "options": [
            "No emergency fund; most of my wealth",
            "Small buffer; a large share",
            "Some buffer; a moderate share",
            "6+ months buffer; a modest share",
            "Strong buffer; a small share of wealth",
        ],
    },
]

# Representative horizon (years) for each time_horizon_choice (1–5)
_HORIZON_YEARS_BY_CHOICE = {1: 1, 2: 3, 3: 5, 4: 8, 5: 15}


def _scale_5_to_10(value: int) -> float:
    """Map a 1–5 Likert answer onto the 1–10 risk scale."""
    return 1.0 + (float(value) - 1.0) / 4.0 * 9.0


def profile_user_minimal(
    loss_reaction: int,
    time_horizon_choice: int,
    financial_cushion: int,
    investment_amount: float = 0.0,
) -> dict:
    """
    Minimal 3-question risk profile.

    - Willingness (subjective) = loss_reaction.
    - Capacity (objective)     = mean(time horizon, financial cushion).
    - Composite via the existing blend (conservative bias + short-horizon decay).

    Parameters:
        loss_reaction (int): 1–5 reaction to a 20% drawdown.
        time_horizon_choice (int): 1–5 horizon bucket.
        financial_cushion (int): 1–5 savings buffer / share-of-wealth security.
        investment_amount (float): GBP (carried through for portfolio building).

    Returns:
        dict: same shape as `profile_user` (subjective/objective/composite/band/...).
    """
    horizon_years = _HORIZON_YEARS_BY_CHOICE.get(time_horizon_choice, 5)
    subjective = round(_scale_5_to_10(loss_reaction), 2)
    objective = round(
        (_scale_5_to_10(time_horizon_choice) + _scale_5_to_10(financial_cushion)) / 2.0, 2
    )
    composite = compute_composite_score(subjective, objective, horizon_years)
    band = get_risk_band(composite)
    description = get_risk_description(composite)

    return {
        "subjective_score": subjective,
        "objective_score": objective,
        "composite_score": composite,
        "risk_band": band,
        "risk_score_int": round(composite),
        "description": description,
        "has_inconsistency": False,
        "time_horizon_years": horizon_years,
    }


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
    inconsistency = detect_inconsistency(quiz_answers)
    composite = compute_composite_score(
        subjective, objective, time_horizon_years, has_inconsistency=inconsistency,
    )
    band = get_risk_band(composite)
    description = get_risk_description(composite)

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
