"""
Onboarding API Routes — Risk Profiling
========================================
Handles risk questionnaire submission and risk profile retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db, init_db
from backend.db.models import User, RiskProfile
from backend.api.models import RiskProfileRequest, RiskProfileResponse, QuickRiskRequest
from backend.engine.risk_profiler import (
    profile_user, profile_user_minimal, QUIZ_QUESTIONS, MINIMAL_QUIZ_QUESTIONS,
)

router = APIRouter()


@router.get("/quiz-questions")
async def get_quiz_questions():
    """
    Return the 10-question risk assessment quiz.

    Returns:
        list[dict]: Quiz questions with options.
    """
    return QUIZ_QUESTIONS


@router.get("/quiz-questions/minimal")
async def get_minimal_quiz_questions():
    """
    Return the minimal 3-question risk quiz (fastest onboarding).

    Returns:
        list[dict]: Three questions with options.
    """
    return MINIMAL_QUIZ_QUESTIONS


@router.post("/risk-profile/quick", response_model=RiskProfileResponse)
async def submit_quick_risk_profile(
    request: QuickRiskRequest,
    db: Session = Depends(get_db),
):
    """
    Minimal onboarding: compute a risk profile from just 3 answers.

    Parameters:
        request (QuickRiskRequest): 3 Likert answers + investment amount.

    Returns:
        RiskProfileResponse: Computed risk profile with band and description.
    """
    init_db()

    result = profile_user_minimal(
        loss_reaction=request.loss_reaction,
        time_horizon_choice=request.time_horizon_choice,
        financial_cushion=request.financial_cushion,
        investment_amount=request.investment_amount,
    )

    user = db.query(User).filter(User.name == request.name).first()
    if not user:
        user = User(name=request.name)
        db.add(user)
        db.flush()

    minimal_answers = [
        {"question_id": 1, "answer": request.loss_reaction},
        {"question_id": 2, "answer": request.time_horizon_choice},
        {"question_id": 3, "answer": request.financial_cushion},
    ]
    objective_inputs = {
        "investment_amount": request.investment_amount,
        "time_horizon_years": result["time_horizon_years"],
        "onboarding": "minimal",
    }

    existing_profile = db.query(RiskProfile).filter(RiskProfile.user_id == user.id).first()
    if existing_profile:
        existing_profile.subjective_score = result["subjective_score"]
        existing_profile.objective_score = result["objective_score"]
        existing_profile.composite_score = result["composite_score"]
        existing_profile.risk_band = result["risk_band"]
        existing_profile.quiz_answers = minimal_answers
        existing_profile.objective_inputs = objective_inputs
        existing_profile.time_horizon_years = result["time_horizon_years"]
        existing_profile.uses_isa = request.uses_isa
    else:
        db.add(RiskProfile(
            user_id=user.id,
            subjective_score=result["subjective_score"],
            objective_score=result["objective_score"],
            composite_score=result["composite_score"],
            risk_band=result["risk_band"],
            quiz_answers=minimal_answers,
            objective_inputs=objective_inputs,
            time_horizon_years=result["time_horizon_years"],
            uses_isa=request.uses_isa,
        ))

    db.commit()
    db.refresh(user)

    return RiskProfileResponse(
        user_id=user.id,
        subjective_score=result["subjective_score"],
        objective_score=result["objective_score"],
        composite_score=result["composite_score"],
        risk_band=result["risk_band"],
        risk_score_int=result["risk_score_int"],
        time_horizon_years=result["time_horizon_years"],
        uses_isa=request.uses_isa,
        description=result["description"],
    )


@router.post("/risk-profile", response_model=RiskProfileResponse)
async def submit_risk_profile(
    request: RiskProfileRequest,
    db: Session = Depends(get_db),
):
    """
    Submit risk questionnaire answers and financial data.
    Computes subjective, objective, and composite risk scores.

    Parameters:
        request (RiskProfileRequest): Quiz answers + financial inputs.

    Returns:
        RiskProfileResponse: Computed risk profile with band and description.
    """
    init_db()

    # Compute risk profile
    result = profile_user(
        quiz_answers=[{"question_id": a.question_id, "answer": a.answer} for a in request.quiz_answers],
        monthly_income=request.objective_inputs.monthly_income,
        monthly_expenses=request.objective_inputs.monthly_expenses,
        total_investable_assets=request.objective_inputs.total_investable_assets,
        investment_amount=request.objective_inputs.investment_amount,
        employment_type=request.objective_inputs.employment_type,
        has_emergency_fund=request.objective_inputs.has_emergency_fund,
        time_horizon_years=request.objective_inputs.time_horizon_years,
    )

    # Create or update user
    user = db.query(User).filter(User.name == request.name).first()
    if not user:
        user = User(name=request.name)
        db.add(user)
        db.flush()

    # Save risk profile
    existing_profile = db.query(RiskProfile).filter(RiskProfile.user_id == user.id).first()
    if existing_profile:
        existing_profile.subjective_score = result["subjective_score"]
        existing_profile.objective_score = result["objective_score"]
        existing_profile.composite_score = result["composite_score"]
        existing_profile.risk_band = result["risk_band"]
        existing_profile.quiz_answers = [{"question_id": a.question_id, "answer": a.answer} for a in request.quiz_answers]
        existing_profile.objective_inputs = request.objective_inputs.model_dump()
        existing_profile.time_horizon_years = request.objective_inputs.time_horizon_years
        existing_profile.uses_isa = request.uses_isa
    else:
        profile = RiskProfile(
            user_id=user.id,
            subjective_score=result["subjective_score"],
            objective_score=result["objective_score"],
            composite_score=result["composite_score"],
            risk_band=result["risk_band"],
            quiz_answers=[{"question_id": a.question_id, "answer": a.answer} for a in request.quiz_answers],
            objective_inputs=request.objective_inputs.model_dump(),
            time_horizon_years=request.objective_inputs.time_horizon_years,
            uses_isa=request.uses_isa,
        )
        db.add(profile)

    db.commit()
    db.refresh(user)

    return RiskProfileResponse(
        user_id=user.id,
        subjective_score=result["subjective_score"],
        objective_score=result["objective_score"],
        composite_score=result["composite_score"],
        risk_band=result["risk_band"],
        risk_score_int=result["risk_score_int"],
        time_horizon_years=result["time_horizon_years"],
        uses_isa=request.uses_isa,
        description=result["description"],
    )


@router.get("/risk-profile/{user_id}", response_model=RiskProfileResponse)
async def get_risk_profile(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a user's saved risk profile.

    Parameters:
        user_id (int): User ID.

    Returns:
        RiskProfileResponse: Saved risk profile data.
    """
    profile = db.query(RiskProfile).filter(RiskProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Risk profile not found")

    band = profile.risk_band
    from backend.engine.risk_profiler import get_risk_description
    description = get_risk_description(profile.composite_score)

    return RiskProfileResponse(
        user_id=user_id,
        subjective_score=profile.subjective_score,
        objective_score=profile.objective_score,
        composite_score=profile.composite_score,
        risk_band=band,
        risk_score_int=round(profile.composite_score),
        time_horizon_years=profile.time_horizon_years,
        uses_isa=profile.uses_isa,
        description=description,
    )
