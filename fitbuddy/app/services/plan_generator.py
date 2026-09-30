from dataclasses import dataclass

from ..config import Settings
from ..schemas import UserInput
from .gemini import GeminiService, GeminiServiceError


@dataclass
class GenerationResult:
    text: str
    source: str


def _fallback_plan(profile: UserInput) -> str:
    focus = {
        "weight loss": "low-impact conditioning and steady cardio",
        "muscle gain": "controlled strength work with progressive overload",
        "general wellness": "balanced strength, mobility, and aerobic fitness",
        "flexibility": "mobility, yoga-inspired flows, and gentle core work",
        "endurance": "gradual aerobic volume with supportive strength work",
    }[profile.goal]
    effort = {
        "low": "Keep the effort conversational and stop with energy in reserve.",
        "medium": "Work at a challenging but sustainable pace; leave 2–3 good reps in reserve.",
        "high": "Use the high end only when technique stays crisp; take extra rest as needed.",
    }[profile.intensity]
    days = [
        ("Day 1 — Full-body foundation", "2 rounds: 10 bodyweight squats, 8 incline push-ups, 10 hip hinges, 30-second plank. Rest 60–90 seconds."),
        ("Day 2 — Cardio and mobility", "25–35 minutes of brisk walking, cycling, or another joint-friendly cardio option, then 10 minutes of mobility."),
        ("Day 3 — Upper body and core", "3 rounds: 10 rows, 8–12 push-ups against a comfortable surface, 10 dead bugs per side, 20-second side plank per side."),
        ("Day 4 — Recovery", "Easy walk for 15–25 minutes plus gentle stretching. Keep this day restorative."),
        ("Day 5 — Lower body", "3 rounds: 10 split squats per side, 12 glute bridges, 12 calf raises, 8 bird dogs per side."),
        ("Day 6 — Goal-focused conditioning", f"20–30 minutes centered on {focus}. Alternate 2 minutes steady with 1 minute easy, or use a comfortable continuous pace."),
        ("Day 7 — Rest and review", "Full rest or a gentle walk. Note energy, soreness, and one adjustment for next week."),
    ]
    lines = [
        f"FITBUDDY 7-DAY PLAN FOR {profile.name.upper()}",
        f"Goal: {profile.goal.title()} | Intensity: {profile.intensity.title()} | Profile: age {profile.age}, {profile.weight_kg:g} kg",
        "",
        "Safety note: Warm up for 5–10 minutes, move within a pain-free range, and stop for sharp pain, dizziness, or unusual shortness of breath. This is general wellness guidance, not medical advice.",
        f"Intensity guidance: {effort}",
        "",
    ]
    for title, detail in days:
        lines.extend([title, f"Warm-up: 5–10 minutes of easy movement. {detail}", "Cool-down: 5 minutes of relaxed breathing and comfortable stretches.", ""])
    return "\n".join(lines).strip()


def _fallback_tip(goal: str) -> str:
    tips = {
        "weight loss": "Build meals around vegetables, a protein source, and high-fiber carbohydrates. Hydrate regularly and aim for gradual, sustainable progress rather than aggressive restriction.",
        "muscle gain": "Include a protein-rich food at each meal, eat enough overall to support training, and prioritize a carbohydrate-rich meal or snack around harder sessions.",
        "general wellness": "Use a simple plate pattern: half colorful vegetables or fruit, a quarter protein, and a quarter whole-food carbohydrates, with water as your default drink.",
        "flexibility": "Hydrate, include protein and colorful produce, and pair mobility practice with regular meals so recovery is supported between sessions.",
        "endurance": "Prioritize fluids and carbohydrate-rich foods before longer sessions; include protein afterward and increase training volume gradually.",
    }
    return tips[goal]


def generate_workout_gemini(profile: UserInput, service: GeminiService, settings: Settings) -> GenerationResult:
    prompt = f"""You are a careful fitness-programming assistant. Create a practical, safe 7-day workout plan in plain Markdown for this adult user:
- Name: {profile.name}
- Age: {profile.age}
- Weight: {profile.weight_kg:g} kg
- Goal: {profile.goal}
- Preferred intensity: {profile.intensity}

Include a heading, a short safety disclaimer, and exactly seven day sections. Every day must include a warm-up, main workout with exercise sets/reps or durations, and a cool-down or recovery note. Include at least one recovery day. Do not diagnose, prescribe treatment, or recommend unsafe extreme dieting. Keep the plan easy to scan and do not wrap it in JSON or code fences."""
    try:
        text = service.generate_text(prompt, settings.gemini_workout_model)
        return GenerationResult(text=text, source="gemini")
    except GeminiServiceError:
        return GenerationResult(text=_fallback_plan(profile), source="fallback")


def generate_nutrition_tip_with_flash(goal: str, service: GeminiService, settings: Settings) -> GenerationResult:
    prompt = f"""Give one concise, actionable nutrition or recovery tip for a fitness user whose goal is {goal}. Keep it to 2–4 sentences, use supportive non-medical language, and avoid calorie prescriptions or medical claims."""
    try:
        text = service.generate_text(prompt, settings.gemini_tip_model)
        return GenerationResult(text=text, source="gemini")
    except GeminiServiceError:
        return GenerationResult(text=_fallback_tip(goal), source="fallback")


def update_workout_plan(
    profile: UserInput,
    original_plan: str,
    feedback: str,
    service: GeminiService,
    settings: Settings,
) -> GenerationResult:
    prompt = f"""Revise this 7-day workout plan for the user below using the feedback. Preserve the seven-day structure, include warm-up/main workout/cool-down sections, and keep the plan safe and realistic. Return plain Markdown only.

User: {profile.name}, age {profile.age}, {profile.weight_kg:g} kg, goal {profile.goal}, intensity {profile.intensity}
Feedback: {feedback}

Original plan:
{original_plan}

Do not diagnose or prescribe medical treatment. Add a short note about how the requested change was incorporated."""
    try:
        text = service.generate_text(prompt, settings.gemini_workout_model)
        return GenerationResult(text=text, source="gemini")
    except GeminiServiceError:
        revised = f"{original_plan}\n\nUPDATE NOTES\nFeedback incorporated: {feedback}\n\nAdjust the listed exercises, volume, or recovery days gradually and keep all movements pain-free."
        return GenerationResult(text=revised, source="fallback")

