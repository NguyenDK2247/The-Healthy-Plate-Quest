"""
ai_coach.py — LLM integration service for The Healthy Plate Quest.

Uses Groq (free tier, 1000 requests/day) with Llama 3.3 70B.
Get a free API key at: https://console.groq.com

Handles:
  - Conversational AI nutrition coach (Coach Vita)
  - Instant meal feedback after logging
  - Personalized quest generation based on user profile + food history

Phase feedback update: Added validation layer, including:
  - Red-flag phrase detection
  - Nutritional constraint checks
  - Prompt hardening with explicit safety constraints
  - Mandatory AI disclaimer on all responses
"""

import os
import re
import json
from flask import current_app
from openai import OpenAI


# ─────────────────────────────────────────────
#  CLIENT + MODEL
# ─────────────────────────────────────────────

GROQ_MODEL = 'llama-3.3-70b-versatile'

AI_DISCLAIMER = (
    "\n\n---\n⚠️ *This is AI-generated guidance for informational purposes only "
    "and does not constitute medical or dietary advice. "
    "Please consult a qualified healthcare professional for personalized health decisions.*"
)


def get_client():
    api_key = current_app.config.get('GROQ_API_KEY') or os.environ.get('GROQ_API_KEY')
    if not api_key:
        raise ValueError('GROQ_API_KEY is not set in your .env file. '
                         'Get a free key at https://console.groq.com')
    return OpenAI(
        api_key=api_key,
        base_url='https://api.groq.com/openai/v1',
    )


# ─────────────────────────────────────────────
#  VALIDATION LAYER
# ─────────────────────────────────────────────

# Phrases that indicate potentially harmful advice
RED_FLAG_PHRASES = [
    r'\bstop eating entirely\b',
    r'\bdon\'t eat anything\b',
    r'\bfast for \d+ days\b',
    r'\bstarvation diet\b',
    r'\bcrash diet\b',
    r'\bextreme calorie restriction\b',
    r'\bskip all meals\b',
    r'\bforce yourself to vomit\b',
    r'\bpurge after eating\b',
    r'\btake laxatives to lose\b',
    r'\bdiagnosed with\b',
    r'\bprescribe you\b',
    r'\bguaranteed to lose \d+\b',
    r'\blose \d+ kg in \d+ day\b',
    r'\blose \d+ pounds in \d+ day\b',
]

# Safe calorie ranges per day for advice validation
CALORIE_CONSTRAINTS = {
    'min_daily_safe':   1200,   # Below this is dangerous for most adults
    'max_daily_safe':   4000,   # Above this is excessive for most adults
    'min_meal':         50,     # Below this is unreasonably small for a meal suggestion
    'max_meal':         1500,   # Above this is unreasonably large for a single meal
}

# Safe macro ranges (grams per day)
MACRO_CONSTRAINTS = {
    'protein_min':  10,
    'protein_max':  300,
    'carbs_min':    20,
    'carbs_max':    600,
    'fat_min':      10,
    'fat_max':      200,
}

SAFE_FALLBACK_RESPONSE = (
    "I want to make sure I give you accurate and safe advice! "
    "For your nutrition goals, I'd recommend focusing on balanced meals with plenty of "
    "vegetables, lean protein, whole grains, and healthy fats. "
    "If you have specific health concerns, please consult a registered dietitian or doctor. "
    "What would you like to know about healthy eating today? 🥗"
)


def contains_red_flags(text):
    """Check if AI response contains potentially harmful phrases."""
    text_lower = text.lower()
    for pattern in RED_FLAG_PHRASES:
        if re.search(pattern, text_lower):
            return True, pattern
    return False, None


def validate_calorie_advice(text):
    """
    Only flag if the response explicitly recommends a dangerously
    low daily intake as a target, not just mentions calorie numbers.
    """
    # Only match phrases like "eat only 600 calories a day" or "limit to 800 calories daily"
    dangerous_patterns = [
        r'(?:eat only|limit to|restrict to|consume only)\s+(\d{3,4})\s*(?:calories|kcal)',
        r'(\d{3,4})\s*(?:calories|kcal)\s*(?:per day|a day|daily)\s*(?:is enough|will work|only)',
    ]
    for pattern in dangerous_patterns:
        matches = re.findall(pattern, text.lower())
        for match in matches:
            value = int(match) if isinstance(match, str) else int(match[0])
            if value < CALORIE_CONSTRAINTS['min_daily_safe']:
                return False, f'Recommends dangerously low intake: {value} kcal/day'
    return True, None


def validate_response(response_text):
    """
    Full validation pipeline for an AI response.
    Returns (validated_text, was_modified, reason).
    """
    # 1. Red flag check
    flagged, pattern = contains_red_flags(response_text)
    if flagged:
        return SAFE_FALLBACK_RESPONSE + AI_DISCLAIMER, True, f'Red flag detected: {pattern}'

    # 2. Calorie safety check
    calorie_safe, calorie_reason = validate_calorie_advice(response_text)
    if not calorie_safe:
        return SAFE_FALLBACK_RESPONSE + AI_DISCLAIMER, True, calorie_reason

    # 3. Response passed all checks — append disclaimer and return
    return response_text + AI_DISCLAIMER, False, None


# ─────────────────────────────────────────────
#  HARDENED SYSTEM PROMPT BUILDER
# ─────────────────────────────────────────────

SAFETY_CONSTRAINTS = """
SAFETY CONSTRAINTS (non-negotiable):
- Never suggest calorie intakes below 1200 kcal/day or above 4000 kcal/day
- Never recommend skipping meals, fasting, crash diets, or extreme restrictions
- Never diagnose medical conditions or suggest medications/supplements as cures
- Never make guarantees about weight loss speed or amounts
- Never give advice that contradicts the user's stated dietary restrictions
- If asked about eating disorders, self-harm, or medical symptoms, always redirect to a healthcare professional
- Always frame advice as suggestions, never as commands
- Do not provide specific supplement dosages
"""


def build_coach_system_prompt(user, today_totals=None, recent_foods=None):
    goal_descriptions = {
        'general':           'general healthy eating',
        'energy':            'improving energy and focus through diet',
        'weight_management': 'weight management',
        'gut_health':        'improving gut health',
        'muscle_building':   'building muscle and increasing protein intake',
    }
    goal_text    = goal_descriptions.get(user.nutrition_goal or 'general', 'general healthy eating')
    restrictions = user.dietary_restrictions or 'none'
    preference   = user.dietary_preference or 'omnivore'
    favorites    = user.favorite_ingredients or 'not specified'
    level_title  = user.level_title
    streak       = user.current_streak or 0

    nutrition_context = ''
    if today_totals and today_totals.get('meal_count', 0) > 0:
        nutrition_context = f"""
Today's nutrition so far:
- Calories: {today_totals.get('calories', 0):.0f} kcal
- Protein: {today_totals.get('protein_g', 0):.1f}g
- Carbs: {today_totals.get('carbs_g', 0):.1f}g
- Fat: {today_totals.get('fat_g', 0):.1f}g
- Fiber: {today_totals.get('fiber_g', 0):.1f}g
- Meals logged today: {today_totals.get('meal_count', 0)}
"""

    recent_context = ''
    if recent_foods:
        recent_context = f'\nRecently logged foods: {", ".join(recent_foods[:8])}'

    # Dynamic behavioral context (Phase feedback Point 1)
    try:
        from app.services.personalization import build_dynamic_context
        dynamic_context = build_dynamic_context(user)
    except Exception:
        dynamic_context = ''

    return f"""You are Coach Vita, a warm, encouraging, and knowledgeable AI nutrition coach inside a gamified healthy eating app called "The Healthy Plate Quest".

Your personality:
- Enthusiastic and motivating, like a supportive friend who happens to know a lot about nutrition
- Use friendly, conversational language — avoid clinical or preachy tones
- Celebrate wins (streaks, quests, milestones) and gently nudge toward improvement
- Keep responses concise and actionable — 2-4 short paragraphs maximum
- Occasionally use relevant food or health emojis to keep things fun

User profile:
- Name: {user.display_name or user.username}
- Level: {user.level} ({level_title})
- Current streak: {streak} days
- Nutrition goal: {goal_text}
- Dietary preference: {preference}
- Dietary restrictions: {restrictions}
- Favourite ingredients: {favorites}
{nutrition_context}{recent_context}{dynamic_context}

Guidelines:
- Always personalize advice to their goal ({goal_text}) and dietary preference ({preference})
- Respect dietary restrictions ({restrictions}) — never suggest foods that conflict with them
- Reference their streak or level occasionally to reinforce the gamification motivation
- When suggesting foods or recipes, lean toward their favourite ingredients when possible
- If they ask something outside nutrition/health, gently redirect back to your coaching role
- Never diagnose medical conditions or replace professional medical advice
- Keep the tone positive — this is a game, it should be fun!

{SAFETY_CONSTRAINTS}"""


# ─────────────────────────────────────────────
#  CHAT — COACH VITA CONVERSATION
# ─────────────────────────────────────────────

def chat_with_coach(user, message, conversation_history, today_totals=None, recent_foods=None):
    client = get_client()
    system_prompt = build_coach_system_prompt(user, today_totals, recent_foods)

    messages = [{'role': 'system', 'content': system_prompt}]
    messages += conversation_history
    messages += [{'role': 'user', 'content': message}]

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=600,
        messages=messages,
    )

    raw_reply = response.choices[0].message.content

    # Run through validation layer
    validated_reply, was_modified, reason = validate_response(raw_reply)

    updated_history = conversation_history + [
        {'role': 'user',      'content': message},
        {'role': 'assistant', 'content': raw_reply},  # store original in history
    ]

    if len(updated_history) > 20:
        updated_history = updated_history[-20:]

    return validated_reply, updated_history


# ─────────────────────────────────────────────
#  MEAL FEEDBACK
# ─────────────────────────────────────────────

def generate_meal_feedback(user, food_log):
    client = get_client()

    goal_text = {
        'general':           'general healthy eating',
        'energy':            'energy and focus',
        'weight_management': 'weight management',
        'gut_health':        'gut health',
        'muscle_building':   'muscle building',
    }.get(user.nutrition_goal or 'general', 'general healthy eating')

    # Validate meal nutrition values are within plausible ranges
    calories = food_log.calories or 0
    if calories < CALORIE_CONSTRAINTS['min_meal'] or calories > CALORIE_CONSTRAINTS['max_meal']:
        calorie_note = f"Note: the logged calorie value ({calories:.0f} kcal) is unusual — give general feedback only."
    else:
        calorie_note = ""

    prompt = f"""Give brief, friendly feedback (2-3 sentences max) on this meal for someone focused on {goal_text}.

Meal: {food_log.food_name} ({food_log.quantity_g:.0f}g)
Nutrition: {calories:.0f} kcal, {food_log.protein_g:.1f}g protein, {food_log.carbs_g:.1f}g carbs, {food_log.fat_g:.1f}g fat, {food_log.fiber_g:.1f}g fiber
Category: {food_log.food_category or 'general'}
Dietary preference: {user.dietary_preference or 'omnivore'}
{calorie_note}

Be encouraging and specific. Mention one positive and one tip if relevant. Use 1-2 emojis. Keep it short.
Never suggest dangerous dietary practices. Frame all advice as friendly suggestions."""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=150,
        messages=[
            {'role': 'system', 'content': f'You are a friendly nutrition coach. Give brief, helpful meal feedback.\n{SAFETY_CONSTRAINTS}'},
            {'role': 'user',   'content': prompt},
        ],
    )

    raw = response.choices[0].message.content
    validated, _, _ = validate_response(raw)

    # For meal feedback, strip the long disclaimer and use a shorter one
    short_disclaimer = "\n*AI-generated — not medical advice.*"
    validated_short = raw
    flagged, _ = contains_red_flags(raw)
    calorie_ok, _ = validate_calorie_advice(raw)
    if flagged or not calorie_ok:
        validated_short = SAFE_FALLBACK_RESPONSE
    validated_short += short_disclaimer

    return validated_short


# ─────────────────────────────────────────────
#  PERSONALIZED QUEST GENERATION
# ─────────────────────────────────────────────

def generate_personalized_quest(user, recent_foods=None):
    client = get_client()

    favorites    = user.favorite_ingredients or 'not specified'
    goal         = user.nutrition_goal or 'general'
    preference   = user.dietary_preference or 'omnivore'
    restrictions = user.dietary_restrictions or 'none'

    recent_context = ''
    if recent_foods:
        recent_context = f'Recently logged foods: {", ".join(recent_foods[:6])}'

    prompt = f"""Create a personalized weekly nutrition quest for a user with this profile:
- Nutrition goal: {goal}
- Dietary preference: {preference}
- Dietary restrictions: {restrictions}
- Favourite ingredients: {favorites}
{recent_context}

The quest should be creative, specific, and achievable in one week.
It must match their dietary preference and avoid their restrictions.
It must promote genuinely healthy eating habits — no extreme restriction or unhealthy practices.

Respond ONLY with a valid JSON object — no markdown, no explanation, no backticks. Example:
{{"title": "Lentil Lover", "description": "Cook 3 meals using lentils this week", "icon": "🫘", "difficulty": "medium", "xp_reward": 80, "criteria_type": "log_protein", "criteria_target": 3}}

Rules:
- difficulty must be "easy", "medium", or "hard"
- xp_reward: easy=25-40, medium=50-90, hard=100-150
- criteria_type must be one of: log_vegetables, log_fruit, log_protein, log_breakfast, log_meals_week, color_variety, daily_fiber_goal, log_vegetables_week
- criteria_target must be an integer between 1 and 21
- icon must be a single emoji
- title max 30 chars, description max 100 chars
- The quest must encourage adding nutritious foods, never restricting or removing food groups"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=200,
        messages=[
            {'role': 'system', 'content': 'You are a nutrition app backend. Respond only with valid JSON. Never suggest harmful dietary practices.'},
            {'role': 'user',   'content': prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace('```json', '').replace('```', '').strip()

    try:
        quest_data = json.loads(raw)
        required = ['title', 'description', 'icon', 'difficulty',
                    'xp_reward', 'criteria_type', 'criteria_target']
        for key in required:
            if key not in quest_data:
                raise ValueError(f'Missing key: {key}')
        return quest_data
    except (json.JSONDecodeError, ValueError):
        return {
            'title':           'Veggie Boost',
            'description':     'Log 10 vegetable servings this week.',
            'icon':            '🥦',
            'difficulty':      'medium',
            'xp_reward':       70,
            'criteria_type':   'log_vegetables_week',
            'criteria_target': 10,
        }
    