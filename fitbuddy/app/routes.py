import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Plan, User
from .schemas import (
    FeedbackRequest,
    GenerateResponse,
    GOAL_OPTIONS,
    INTENSITY_OPTIONS,
    NutritionTipRequest,
    PlanResponse,
    UserInput,
    UserSummary,
)
from .services.gemini import GeminiService
from .services.plan_generator import (
    generate_nutrition_tip_with_flash,
    generate_workout_gemini,
    update_workout_plan,
)

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _home_context(request: Request, **extra):
    return {
        "request": request,
        "goals": GOAL_OPTIONS,
        "intensities": INTENSITY_OPTIONS,
        **extra,
    }


def _admin_allowed(request: Request) -> bool:
    if not settings.admin_token:
        return True
    supplied = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    return supplied == settings.admin_token


def _require_admin(request: Request) -> None:
    if not _admin_allowed(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin access required")


def _get_user(db: Session, user_id: str) -> User | None:
    return db.scalar(select(User).where(User.user_id == user_id))


def _save_user(db: Session, profile: UserInput) -> User:
    user = _get_user(db, profile.user_id)
    if user is None:
        user = User(
            user_id=profile.user_id,
            name=profile.name,
            age=profile.age,
            weight_kg=profile.weight_kg,
            goal=profile.goal,
            intensity=profile.intensity,
        )
        db.add(user)
    else:
        user.name = profile.name
        user.age = profile.age
        user.weight_kg = profile.weight_kg
        user.goal = profile.goal
        user.intensity = profile.intensity
    db.flush()
    return user


def _profile_from_user(user: User) -> UserInput:
    return UserInput(
        name=user.name,
        user_id=user.user_id,
        age=user.age,
        weight_kg=user.weight_kg,
        goal=user.goal,
        intensity=user.intensity,
    )


def _response_from_plan(plan: Plan) -> PlanResponse:
    return PlanResponse(
        user=UserSummary.model_validate(plan.user),
        original_plan=plan.original_plan,
        updated_plan=plan.updated_plan,
        nutrition_tip=plan.nutrition_tip,
        latest_feedback=plan.latest_feedback,
        feedback_count=plan.feedback_count,
        ai_source=plan.ai_source,
    )


def _result_context(request: Request, plan: Plan, message: str | None = None):
    return {
        "request": request,
        "user": plan.user,
        "plan": plan,
        "display_plan": plan.updated_plan or plan.original_plan,
        "message": message,
    }


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context=_home_context(request))


@router.get("/health", name="health")
def health():
    return {"status": "ok", "service": settings.app_name, "gemini_configured": settings.gemini_configured}


@router.post("/generate-workout", response_class=HTMLResponse, name="generate_workout_form")
def generate_workout_form(
    request: Request,
    name: str = Form(...),
    user_id: str = Form(...),
    age: str = Form(...),
    weight_kg: str = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
    db: Session = Depends(get_db),
):
    raw = {"name": name, "user_id": user_id, "age": age, "weight_kg": weight_kg, "goal": goal, "intensity": intensity}
    try:
        profile = UserInput(**raw)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_home_context(request, values=raw, errors=[item["msg"] for item in exc.errors()]),
            status_code=422,
        )

    service = GeminiService(settings)
    workout = generate_workout_gemini(profile, service, settings)
    tip = generate_nutrition_tip_with_flash(profile.goal, service, settings)
    user = _save_user(db, profile)
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id))
    if plan is None:
        plan = Plan(user_id=user.id, original_plan=workout.text, nutrition_tip=tip.text, ai_source=workout.source)
        db.add(plan)
    else:
        plan.original_plan = workout.text
        plan.updated_plan = None
        plan.latest_feedback = None
        plan.feedback_count = 0
        plan.nutrition_tip = tip.text
        plan.ai_source = workout.source
    db.commit()
    db.refresh(plan)
    source_message = "Gemini generated your plan." if workout.source == "gemini" else "Your plan is ready using the built-in offline starter mode. Add GEMINI_API_KEY for Gemini-generated plans."
    return templates.TemplateResponse(request=request, name="result.html", context=_result_context(request, plan, source_message))


@router.post("/submit-feedback", response_class=HTMLResponse, name="submit_feedback_form")
def submit_feedback_form(
    request: Request,
    user_id: str = Form(...),
    feedback: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        request_data = FeedbackRequest(user_id=user_id, feedback=feedback)
    except ValidationError as exc:
        user = _get_user(db, user_id.strip())
        if user and user.plan:
            return templates.TemplateResponse(
                request=request,
                name="result.html",
                context=_result_context(request, user.plan, "; ".join(item["msg"] for item in exc.errors())),
                status_code=422,
            )
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_home_context(request, errors=[item["msg"] for item in exc.errors()]),
            status_code=422,
        )

    user = _get_user(db, request_data.user_id)
    if user is None or user.plan is None:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=_home_context(request, errors=["No saved plan was found for that User ID."]),
            status_code=404,
        )
    service = GeminiService(settings)
    revised = update_workout_plan(
        _profile_from_user(user), user.plan.original_plan, request_data.feedback, service, settings
    )
    user.plan.updated_plan = revised.text
    user.plan.latest_feedback = request_data.feedback
    user.plan.feedback_count += 1
    user.plan.ai_source = revised.source
    db.commit()
    db.refresh(user.plan)
    message = "Your plan was updated with the feedback." if revised.source == "gemini" else "Your plan was updated in offline starter mode."
    return templates.TemplateResponse(request=request, name="result.html", context=_result_context(request, user.plan, message))


@router.get("/view-all-users", response_class=HTMLResponse, name="view_all_users")
def view_all_users(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    users = list(db.scalars(select(User).order_by(User.created_at.desc())).all())
    return templates.TemplateResponse(request=request, name="all_users.html", context={"request": request, "users": users})


@router.post("/api/plans/generate", response_model=GenerateResponse, status_code=201, name="api_generate_plan")
def api_generate_plan(payload: UserInput, db: Session = Depends(get_db)):
    service = GeminiService(settings)
    workout = generate_workout_gemini(payload, service, settings)
    tip = generate_nutrition_tip_with_flash(payload.goal, service, settings)
    user = _save_user(db, payload)
    plan = db.scalar(select(Plan).where(Plan.user_id == user.id))
    if plan is None:
        plan = Plan(user_id=user.id, original_plan=workout.text, nutrition_tip=tip.text, ai_source=workout.source)
        db.add(plan)
    else:
        plan.original_plan = workout.text
        plan.updated_plan = None
        plan.latest_feedback = None
        plan.feedback_count = 0
        plan.nutrition_tip = tip.text
        plan.ai_source = workout.source
    db.commit()
    db.refresh(plan)
    return GenerateResponse(**_response_from_plan(plan).model_dump(), message="Your personalized plan is ready.")


@router.post("/api/plans/{user_id}/feedback", response_model=PlanResponse, name="api_update_plan")
def api_update_plan(user_id: str, payload: FeedbackRequest, db: Session = Depends(get_db)):
    if user_id != payload.user_id:
        raise HTTPException(status_code=400, detail="Path user_id and payload user_id must match")
    user = _get_user(db, user_id)
    if user is None or user.plan is None:
        raise HTTPException(status_code=404, detail="No saved plan found for this User ID")
    service = GeminiService(settings)
    revised = update_workout_plan(_profile_from_user(user), user.plan.original_plan, payload.feedback, service, settings)
    user.plan.updated_plan = revised.text
    user.plan.latest_feedback = payload.feedback
    user.plan.feedback_count += 1
    user.plan.ai_source = revised.source
    db.commit()
    db.refresh(user.plan)
    return _response_from_plan(user.plan)


@router.post("/api/nutrition-tip", name="api_nutrition_tip")
def api_nutrition_tip(payload: NutritionTipRequest):
    result = generate_nutrition_tip_with_flash(payload.goal, GeminiService(settings), settings)
    return {"goal": payload.goal, "nutrition_tip": result.text, "ai_source": result.source}


@router.get("/api/users", response_model=list[PlanResponse], name="api_users")
def api_users(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    plans = list(db.scalars(select(Plan).join(Plan.user).order_by(User.created_at.desc())).all())
    return [_response_from_plan(plan) for plan in plans]


@router.get("/api/users/{user_id}", response_model=PlanResponse, name="api_user")
def api_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    user = _get_user(db, user_id)
    if user is None or user.plan is None:
        raise HTTPException(status_code=404, detail="User or plan not found")
    return _response_from_plan(user.plan)


@router.delete("/api/users/{user_id}", status_code=204, name="api_delete_user")
def api_delete_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    user = _get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.execute(delete(User).where(User.id == user.id))
    db.commit()

