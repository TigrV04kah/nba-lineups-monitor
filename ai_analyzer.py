"""
AI Analyzer - анализ влияния изменений состава на производительность игроков
Использует OpenAI GPT для генерации инсайтов
"""

import os
import re
from openai import OpenAI
from dotenv import load_dotenv

# Импорт для поиска новостей
try:
    from news_scraper import get_relevant_news_for_analysis
except ImportError:
    def get_relevant_news_for_analysis(*args, **kwargs):
        return {'player_news': [], 'team_news': [], 'opponent_news': [], 'has_relevant_news': False}

# Импорт для работы с букмекерскими коэффициентами
try:
    from betting_odds import (
        get_cached_odds, find_player_odds, compare_ai_with_odds,
        odds_to_probability
    )
    BETTING_ODDS_AVAILABLE = True
except ImportError:
    BETTING_ODDS_AVAILABLE = False

# Загружаем переменные окружения
load_dotenv()

# Инициализация клиента
client = None


def parse_ai_prediction_ranges(ai_response: str) -> dict:
    """
    Парсинг диапазонов прогнозов из ответа AI.

    Ищет паттерны вида:
    - Очки: 18-24
    - Подборы: 5-8
    - Передачи: 3-6

    Returns:
        dict с ключами 'points', 'rebounds', 'assists' и значениями (min, max)
    """
    result = {}

    # Паттерны для поиска диапазонов
    # Учитываем возможные ** вокруг слов (markdown bold)
    patterns = {
        'points': [
            r'\*{0,2}[Оо]чки\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'\*{0,2}[Pp]oints\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'(\d+)\s*[-–]\s*(\d+)\s*очк',
            r'(\d+)\s*[-–]\s*(\d+)\s*pts',
        ],
        'rebounds': [
            r'\*{0,2}[Пп]одбор[ыа]\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'\*{0,2}[Rr]ebounds\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'(\d+)\s*[-–]\s*(\d+)\s*подбор',
            r'(\d+)\s*[-–]\s*(\d+)\s*reb',
        ],
        'assists': [
            r'\*{0,2}[Пп]ередач[иа]\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'\*{0,2}[Aa]ssists\*{0,2}[:\s]+(\d+)\s*[-–]\s*(\d+)',
            r'(\d+)\s*[-–]\s*(\d+)\s*передач',
            r'(\d+)\s*[-–]\s*(\d+)\s*ast',
        ],
    }

    for stat_type, stat_patterns in patterns.items():
        for pattern in stat_patterns:
            match = re.search(pattern, ai_response, re.IGNORECASE)
            if match:
                try:
                    min_val = float(match.group(1))
                    max_val = float(match.group(2))
                    result[stat_type] = (min_val, max_val)
                    break
                except (ValueError, IndexError):
                    continue

    return result


def compare_with_bookmaker_odds(player_name: str, ai_predictions: dict) -> str:
    """
    Сравнение прогнозов AI с букмекерскими линиями.

    Args:
        player_name: Имя игрока
        ai_predictions: Словарь с прогнозами AI {stat_type: (min, max)}

    Returns:
        Форматированная строка с результатами сравнения
    """
    if not BETTING_ODDS_AVAILABLE:
        return ""

    if not ai_predictions:
        return ""

    try:
        odds_data = get_cached_odds()
        if not odds_data:
            return ""
    except Exception as e:
        return f"\n\n⚠️ Ошибка загрузки букмекерских данных: {e}"

    # Ищем коэффициенты для игрока
    all_player_odds = find_player_odds(player_name, odds_data)

    if not all_player_odds:
        return ""

    # Группируем по типу статистики и выбираем основные линии
    odds_by_type = {}
    for odds in all_player_odds:
        stat_type = odds.stat_type
        if stat_type not in odds_by_type:
            odds_by_type[stat_type] = []
        odds_by_type[stat_type].append(odds)

    comparisons = []
    stat_names = {
        'points': 'Очки',
        'rebounds': 'Подборы',
        'assists': 'Передачи',
        'pra': 'О+П+П'
    }

    for stat_type, ai_range in ai_predictions.items():
        if stat_type not in odds_by_type:
            continue

        # Берём основную линию (ближайшую к среднему прогнозу AI)
        ai_mid = (ai_range[0] + ai_range[1]) / 2

        # Сортируем линии по близости к прогнозу AI
        sorted_odds = sorted(
            odds_by_type[stat_type],
            key=lambda x: abs(x.total_line - ai_mid)
        )

        # Берём ближайшую линию
        if sorted_odds:
            main_odds = sorted_odds[0]

            comparison = compare_ai_with_odds(
                ai_prediction_range=ai_range,
                total_line=main_odds.total_line,
                over_odds=main_odds.over_odds,
                under_odds=main_odds.under_odds
            )
            comparison['stat_type'] = stat_type
            comparison['stat_name'] = stat_names.get(stat_type, stat_type)
            comparisons.append(comparison)

    if not comparisons:
        return ""

    # Форматируем вывод
    lines = ["\n\n📊 СРАВНЕНИЕ С БУКМЕКЕРСКИМИ ЛИНИЯМИ:"]

    for comp in comparisons:
        stat_emoji = {'points': '🏀', 'rebounds': '📊', 'assists': '🎯', 'pra': '📈'}.get(
            comp['stat_type'], '•'
        )

        line = comp['total_line']
        ai_pred = comp['ai_prediction']
        over = comp['over_odds']
        under = comp['under_odds']
        diff = comp['diff_from_line']

        over_prob = odds_to_probability(over) * 100 if over > 1 else 0
        under_prob = odds_to_probability(under) * 100 if under > 1 else 0

        direction_ru = "больше" if comp['ai_direction'] == 'over' else "меньше"
        bookie_favors = comp['bookie_favors']
        bookie_ru = "больше" if bookie_favors == 'over' else ("меньше" if bookie_favors == 'under' else "неопределено")

        lines.append(f"\n{stat_emoji} {comp['stat_name']} (линия {line}):")
        lines.append(f"   Прогноз AI: {ai_pred} → ставит на {direction_ru}")
        lines.append(f"   Букмекер: Б{line}={over} ({over_prob:.0f}%), М{line}={under} ({under_prob:.0f}%)")

        if bookie_favors == "neutral":
            lines.append(f"   ℹ️ Нет достаточных данных от букмекера")
        elif comp['ai_agrees_with_bookie']:
            lines.append(f"   ✅ AI согласен с букмекером ({bookie_ru})")
        else:
            lines.append(f"   ⚠️ AI НЕ согласен с букмекером (бук ставит на {bookie_ru})")
            lines.append(f"   💡 Потенциальная value ставка на {direction_ru}!")

    return "\n".join(lines)


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
        stats_context = "\n\nСтатистика последних 5 игр команды:\n"
        for game in team_stats['games'][:5]:
            stats_context += f"\n{game['matchup']} ({game['result']}):\n"
            for starter in game['starters']:
                stats_context += f"  - {starter['name']} ({starter['position']}): {starter['pts']}pts, {starter['reb']}reb, {starter['ast']}ast\n"

    # Промпт для анализа
    prompt = f"""Ты эксперт по NBA аналитике. Проанализируй изменения в стартовом составе команды {team_abbrev} по сравнению с их ПОСЛЕДНЕЙ СЫГРАННОЙ игрой.

ИЗМЕНЕНИЯ В СОСТАВЕ НА СЕГОДНЯ:
- НЕ БУДУТ в старте сегодня (были в прошлой игре): {', '.join(removed_players) if removed_players else 'нет изменений'}
- ВЕРНУЛИСЬ/НОВЫЕ в старте сегодня (не играли в прошлой игре): {', '.join(new_players) if new_players else 'нет изменений'}
{stats_context}

ЗАДАЧА:
1. Если есть выбывшие - объясни их роль и как их отсутствие повлияет на команду
2. Если есть вернувшиеся/новые игроки - объясни как их ПРИСУТСТВИЕ изменит игру:
   - Как перераспределятся владения и броски?
   - У кого может СНИЗИТЬСЯ статистика из-за возвращения ключевых игроков?
   - Какие позитивные эффекты даст возвращение игроков?
3. Дай конкретные прогнозы по изменению статистики для ключевых игроков

Ответ должен быть на русском языке, кратким и структурированным (максимум 250 слов)."""

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


def analyze_player_projection(
    player_name: str,
    player_position: str,
    team_abbrev: str,
    player_stats: list,
    opponent_abbrev: str,
    opponent_stats: dict,
    is_home: bool
) -> str:
    """
    AI анализ и прогноз статистики конкретного игрока на следующую игру.

    Args:
        player_name: Имя игрока
        player_position: Позиция игрока
        team_abbrev: Аббревиатура команды игрока
        player_stats: Статистика игрока за последние 5 игр
        opponent_abbrev: Аббревиатура команды соперника
        opponent_stats: Статистика соперника за последние игры
        is_home: Домашняя игра или нет

    Returns:
        Текст с прогнозом статистики
    """
    if not client:
        if not init_openai():
            return "AI анализ недоступен: не настроен API ключ"

    # Функция конвертации минут из строки "MM:SS" в число
    def parse_minutes(min_val):
        if min_val is None:
            return 0
        if isinstance(min_val, (int, float)):
            return float(min_val)
        if isinstance(min_val, str) and ':' in min_val:
            try:
                parts = min_val.split(':')
                return int(parts[0]) + int(parts[1]) / 60
            except:
                return 0
        try:
            return float(min_val)
        except:
            return 0

    # Форматируем статистику игрока
    player_stats_text = ""
    if player_stats:
        avg_pts = sum(g.get('pts', 0) for g in player_stats) / len(player_stats)
        avg_reb = sum(g.get('reb', 0) for g in player_stats) / len(player_stats)
        avg_ast = sum(g.get('ast', 0) for g in player_stats) / len(player_stats)
        avg_min = sum(parse_minutes(g.get('min')) for g in player_stats) / len(player_stats)
        avg_stl = sum(g.get('stl', 0) for g in player_stats) / len(player_stats)
        avg_blk = sum(g.get('blk', 0) for g in player_stats) / len(player_stats)

        player_stats_text = f"""
СРЕДНЯЯ СТАТИСТИКА ЗА 5 ИГР:
- Минуты: {avg_min:.1f}
- Очки: {avg_pts:.1f}
- Подборы: {avg_reb:.1f}
- Передачи: {avg_ast:.1f}
- Перехваты: {avg_stl:.1f}
- Блоки: {avg_blk:.1f}

ПОСЛЕДНИЕ 5 ИГР (от самой последней к более ранним - игра #1 это ПОСЛЕДНЯЯ сыгранная):"""
        for i, game in enumerate(player_stats, 1):
            matchup = game.get('matchup', 'N/A')
            game_date = game.get('date', '')
            pts = game.get('pts', 0)
            reb = game.get('reb', 0)
            ast = game.get('ast', 0)
            mins = game.get('min', 'N/A')
            player_stats_text += f"\n  {i}. [{game_date}] {matchup}: {pts}pts, {reb}reb, {ast}ast ({mins}мин)"

    # Форматируем информацию о сопернике
    opponent_text = ""
    if opponent_stats and 'games' in opponent_stats:
        opp_games = opponent_stats['games'][:5]

        # Считаем средние очки соперника
        opp_pts_list = [g.get('team_pts', 0) for g in opp_games if g.get('team_pts')]
        avg_opp_pts = sum(opp_pts_list) / len(opp_pts_list) if opp_pts_list else 0

        opponent_text = f"\n\nИНФОРМАЦИЯ О СОПЕРНИКЕ ({opponent_abbrev}):"
        if avg_opp_pts > 0:
            opponent_text += f"\nСредние очки за 5 игр: {avg_opp_pts:.1f}"
        opponent_text += f"\nПоследние 5 результатов:"
        for game in opp_games[:5]:
            pts = game.get('team_pts', 0)
            pts_str = f" - {pts}pts" if pts else ""
            opponent_text += f"\n  - {game.get('matchup', 'N/A')} ({game.get('result', 'N/A')}){pts_str}"

    venue = "дома" if is_home else "на выезде"

    # Получаем релевантные новости
    news_data = get_relevant_news_for_analysis(
        player_name=player_name,
        team_abbrev=team_abbrev,
        opponent_abbrev=opponent_abbrev,
        days=3
    )

    # Формируем блок новостей для промпта
    news_text = ""
    if news_data['has_relevant_news']:
        news_text = "\n\nАКТУАЛЬНЫЕ НОВОСТИ (последние 3 дня):"

        if news_data['player_news']:
            news_text += "\n\nНовости об игроке:"
            for news in news_data['player_news'][:3]:
                title = news.get('title', '')
                content = news.get('content', '')[:150] if news.get('content') else ''
                news_text += f"\n• {title}"
                if content:
                    news_text += f"\n  {content}..."

        if news_data['team_news']:
            news_text += "\n\nНовости о команде:"
            for news in news_data['team_news'][:2]:
                news_text += f"\n• {news.get('title', '')}"
    else:
        news_text = "\n\nАКТУАЛЬНЫЕ НОВОСТИ: За последние 3 дня релевантных новостей об этом игроке или команде не найдено."

    prompt = f"""Ты эксперт по NBA аналитике. Дай прогноз статистики игрока на предстоящую игру.

ИГРОК: {player_name} ({player_position})
КОМАНДА: {team_abbrev}
СОПЕРНИК: {opponent_abbrev} ({venue})
{player_stats_text}
{opponent_text}
{news_text}

ВАЖНО: Игры отсортированы от ПОСЛЕДНЕЙ (№1) к более РАННИМ (№5). Игра №1 - это самая свежая игра!
Если статистика в игре №1 хуже чем в №5 - это ПАДЕНИЕ формы, не рост!

ЗАДАЧА:
1. Проанализируй ТРЕНД: сравни игру №1 (последнюю) с играми №4-5 (более ранними). Растёт или падает форма?
2. Учитывая соперника и домашний/выездной матч, дай КОНКРЕТНЫЙ прогноз:
   - Очки: диапазон (например: 18-24)
   - Подборы: диапазон
   - Передачи: диапазон
   - Общая оценка перспектив (хороший матч / средний / сложный)
3. Если в новостях есть информация о травмах, отдыхе, конфликтах - учти в прогнозе
4. Укажи ключевые факторы

Ответ на русском, кратко (максимум 200 слов)."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты NBA аналитик. Даёшь точные прогнозы статистики игроков на основе данных и актуальных новостей."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.7
        )

        ai_response = response.choices[0].message.content

        # Парсим прогнозы AI и сравниваем с букмекерскими линиями
        ai_predictions = parse_ai_prediction_ranges(ai_response)
        odds_comparison = compare_with_bookmaker_odds(player_name, ai_predictions)

        return ai_response + odds_comparison

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
