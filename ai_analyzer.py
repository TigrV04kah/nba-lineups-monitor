"""
AI Analyzer - анализ влияния изменений состава на производительность игроков
Использует OpenAI GPT для генерации инсайтов
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация клиента
client = None


def init_openai():
    """Инициализация OpenAI клиента."""
    global client
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("OPENAI_API_KEY не найден в .env файле")
        return False

    try:
        client = OpenAI(api_key=api_key)
        return True
    except Exception as e:
        print(f"Ошибка инициализации OpenAI: {e}")
        return False


def analyze_lineup_changes(team_abbrev: str, changes: dict, team_stats: dict) -> str:
    """
    Анализ влияния изменений состава на других игроков.

    Args:
        team_abbrev: Аббревиатура команды
        changes: Словарь с изменениями {'new_players': [...], 'removed_players': [...]}
        team_stats: Статистика команды за последние игры

    Returns:
        Текст анализа от AI
    """
    if not client:
        if not init_openai():
            return "AI анализ недоступен: не настроен API ключ"

    # Формируем контекст для AI
    new_players = changes.get('new_players', [])
    removed_players = changes.get('removed_players', [])

    if not new_players and not removed_players:
        return "Нет изменений в составе для анализа"

    # Собираем статистику игроков
    stats_context = ""
    if team_stats and 'games' in team_stats:
        stats_context = "\n\nСтатистика последних игр команды:\n"
        for game in team_stats['games'][:3]:
            stats_context += f"\n{game['matchup']} ({game['result']}):\n"
            for starter in game['starters']:
                stats_context += f"  - {starter['name']} ({starter['position']}): {starter['pts']}pts, {starter['reb']}reb, {starter['ast']}ast\n"

    # Промпт для анализа
    prompt = f"""Ты эксперт по NBA аналитике. Проанализируй изменения в составе команды {team_abbrev} и их влияние на производительность других игроков.

ИЗМЕНЕНИЯ В СОСТАВЕ:
- Выбыли из старта: {', '.join(removed_players) if removed_players else 'нет'}
- Новые в старте: {', '.join(new_players) if new_players else 'нет'}
{stats_context}

ЗАДАЧА:
1. Кратко объясни какую роль играли выбывшие игроки
2. Как это повлияет на оставшихся стартеров:
   - Кто получит больше владений/бросков?
   - У кого может вырасти статистика (очки, передачи, подборы)?
   - Есть ли риски снижения эффективности?
3. Дай конкретные прогнозы по изменению статистики (например: "+3-5 очков", "+2-3 передачи")

Ответ должен быть на русском языке, кратким и структурированным (максимум 200 слов)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Быстрая и дешевая модель
            messages=[
                {"role": "system", "content": "Ты NBA аналитик. Даёшь краткие, конкретные прогнозы на основе данных."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Ошибка AI анализа: {e}"


def analyze_game_matchup(away_team: dict, home_team: dict, away_stats: dict, home_stats: dict) -> str:
    """
    Анализ матчапа двух команд.

    Args:
        away_team: Данные гостевой команды
        home_team: Данные домашней команды
        away_stats: Статистика гостей
        home_stats: Статистика хозяев

    Returns:
        Текст анализа матчапа
    """
    if not client:
        if not init_openai():
            return "AI анализ недоступен: не настроен API ключ"

    away_abbrev = away_team.get('abbrev', '???')
    home_abbrev = home_team.get('abbrev', '???')

    # Собираем стартовые составы
    away_starters = []
    for player in away_team.get('lineup', [])[:5]:
        if player.get('position') in ['PG', 'SG', 'SF', 'PF', 'C']:
            away_starters.append(f"{player.get('name')} ({player.get('position')})")

    home_starters = []
    for player in home_team.get('lineup', [])[:5]:
        if player.get('position') in ['PG', 'SG', 'SF', 'PF', 'C']:
            home_starters.append(f"{player.get('name')} ({player.get('position')})")

    # Формируем статистику
    def format_team_stats(stats):
        if not stats or 'games' not in stats:
            return "Нет данных"
        result = ""
        for game in stats['games'][:2]:
            result += f"\n  {game['matchup']} ({game['result']})"
        return result

    prompt = f"""Проанализируй предстоящий матч NBA:

{away_abbrev} @ {home_abbrev}

ГОСТИ ({away_abbrev}):
Стартовая пятёрка: {', '.join(away_starters) if away_starters else 'не определена'}
Последние игры: {format_team_stats(away_stats)}

ХОЗЯЕВА ({home_abbrev}):
Стартовая пятёрка: {', '.join(home_starters) if home_starters else 'не определена'}
Последние игры: {format_team_stats(home_stats)}

ЗАДАЧА:
1. Ключевые матчапы (какие игроки будут противостоять друг другу)
2. Преимущества каждой команды
3. Кто из игроков может показать выдающуюся статистику и почему

Ответ на русском, кратко (150 слов максимум)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты NBA аналитик. Даёшь краткие превью матчей."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Ошибка AI анализа: {e}"


# Тест
if __name__ == "__main__":
    init_openai()

    # Тестовый анализ
    test_changes = {
        'new_players': ['Test Player'],
        'removed_players': ['LeBron James']
    }

    test_stats = {
        'games': [
            {
                'matchup': 'LAL vs GSW',
                'result': 'W',
                'starters': [
                    {'name': 'LeBron James', 'position': 'F', 'pts': 28, 'reb': 8, 'ast': 10},
                    {'name': 'Anthony Davis', 'position': 'C', 'pts': 32, 'reb': 14, 'ast': 3},
                ]
            }
        ]
    }

    result = analyze_lineup_changes('LAL', test_changes, test_stats)
    print(result)
