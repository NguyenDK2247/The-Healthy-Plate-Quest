"""
ai_coach.py — LLM integration service for The Healthy Plate Quest.

Uses Groq (free tier, 1000 requests/day) with Llama 3.3 70B.
Get a free API key at: https://console.groq.com

Handles:
  - Conversational AI nutrition coach (Coach Vita)
  - Instant meal feedback after logging
  - Personalised quest generation based on user profile + food history
"""

import os
import json
from flask import current_app
from openai import OpenAI


# ─────────────────────────────────────────────
#  CLIENT + MODEL
# ─────────────────────────────────────────────

GROQ_MODEL = 'llama-3.3-70b-versatile'


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
#  COACH VITA SYSTEM PROMPT BUILDER
# ─────────────────────────────────────────────

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
{nutrition_context}{recent_context}

Guidelines:
- Always personalise advice to their goal ({goal_text}) and dietary preference ({preference})
- Respect dietary restrictions ({restrictions}) — never suggest foods that conflict with them
- Reference their streak or level occasionally to reinforce the gamification motivation
- When suggesting foods or recipes, lean toward their favourite ingredients when possible
- If they ask something outside nutrition/health, gently redirect back to your coaching role
- Never diagnose medical conditions or replace professional medical advice
- Keep the tone positive — this is a game, it should be fun!"""


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

    reply = response.choices[0].message.content

    updated_history = conversation_history + [
        {'role': 'user',      'content': message},
        {'role': 'assistant', 'content': reply},
    ]

    if len(updated_history) > 20:
        updated_history = updated_history[-20:]

    return reply, updated_history


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

    prompt = f"""Give brief, friendly feedback (2-3 sentences max) on this meal for someone focused on {goal_text}.

Meal: {food_log.food_name} ({food_log.quantity_g:.0f}g)
Nutrition: {food_log.calories:.0f} kcal, {food_log.protein_g:.1f}g protein, {food_log.carbs_g:.1f}g carbs, {food_log.fat_g:.1f}g fat, {food_log.fiber_g:.1f}g fiber
Category: {food_log.food_category or 'general'}
Dietary preference: {user.dietary_preference or 'omnivore'}

Be encouraging and specific. Mention one positive and one tip if relevant. Use 1-2 emojis. Keep it short."""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=150,
        messages=[
            {'role': 'system', 'content': 'You are a friendly nutrition coach. Give brief, helpful meal feedback.'},
            {'role': 'user',   'content': prompt},
        ],
    )

    return response.choices[0].message.content


# ─────────────────────────────────────────────
#  PERSONALISED QUEST GENERATION
# ─────────────────────────────────────────────

def generate_personalised_quest(user, recent_foods=None):
    client = get_client()

    favorites    = user.favorite_ingredients or 'not specified'
    goal         = user.nutrition_goal or 'general'
    preference   = user.dietary_preference or 'omnivore'
    restrictions = user.dietary_restrictions or 'none'

    recent_context = ''
    if recent_foods:
        recent_context = f'Recently logged foods: {", ".join(recent_foods[:6])}'

    prompt = f"""Create a personalised weekly nutrition quest for a user with this profile:
- Nutrition goal: {goal}
- Dietary preference: {preference}
- Dietary restrictions: {restrictions}
- Favourite ingredients: {favorites}
{recent_context}

The quest should be creative, specific, and achievable in one week.
It must match their dietary preference and avoid their restrictions.

Respond ONLY with a valid JSON object — no markdown, no explanation, no backticks. Example:
{{"title": "Lentil Lover", "description": "Cook 3 meals using lentils this week", "icon": "🫘", "difficulty": "medium", "xp_reward": 80, "criteria_type": "log_protein", "criteria_target": 3}}

Rules:
- difficulty must be "easy", "medium", or "hard"
- xp_reward: easy=25-40, medium=50-90, hard=100-150
- criteria_type must be one of: log_vegetables, log_fruit, log_protein, log_breakfast, log_meals_week, color_variety, daily_fiber_goal, log_vegetables_week
- criteria_target must be an integer between 1 and 21
- icon must be a single emoji
- title max 30 chars, description max 100 chars"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=200,
        messages=[
            {'role': 'system', 'content': 'You are a nutrition app backend. Respond only with valid JSON.'},
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
    