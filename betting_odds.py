"""
Модуль для работы с букмекерскими коэффициентами на статистику игроков NBA.
Загружает данные из CSV файла и сравнивает с прогнозами AI.
"""

import os
import csv
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Путь к файлу с коэффициентами (можно переопределить)
DEFAULT_ODDS_FILE = r"D:\scripts\nba_players"


@dataclass
class PlayerOdds:
    """Коэффициенты на тотал игрока."""
    player_name: str
    team1: str
    team2: str
    game_date: str
    stat_type: str  # 'points', 'rebounds', 'assists', 'pra'
    total_line: float
    over_odds: float  # Коэффициент на "больше"
    under_odds: float  # Коэффициент на "меньше"


# Маппинг русских имён игроков на английские
RUSSIAN_TO_ENGLISH_PLAYERS = {
    # Superstars
    "Леброн Джеймс": "LeBron James",
    "Стефен Карри": "Stephen Curry",
    "Стеф Карри": "Stephen Curry",
    "Кевин Дюрант": "Kevin Durant",
    "Яннис Адетокунбо": "Giannis Antetokounmpo",
    "Никола Йокич": "Nikola Jokic",
    "Лука Дончич": "Luka Doncic",
    "Джоэл Эмбиид": "Joel Embiid",
    "Джейсон Тейтум": "Jayson Tatum",
    "Джимми Батлер": "Jimmy Butler",
    "Энтони Дэвис": "Anthony Davis",
    "Дэмиан Лиллард": "Damian Lillard",
    "Кавай Ленард": "Kawhi Leonard",
    "Пол Джордж": "Paul George",
    "Девин Букер": "Devin Booker",
    "Кайри Ирвинг": "Kyrie Irving",
    "Джа Морант": "Ja Morant",
    "Трэй Янг": "Trae Young",
    "Донован Митчелл": "Donovan Mitchell",
    "Зайон Уильямсон": "Zion Williamson",
    "Энтони Эдвардс": "Anthony Edwards",
    "Виктор Вембаньяма": "Victor Wembanyama",
    "Шай Гилджес-Александер": "Shai Gilgeous-Alexander",
    "Тайриз Халибёртон": "Tyrese Haliburton",
    "Деаарон Фокс": "De'Aaron Fox",
    "Паоло Банкеро": "Paolo Banchero",
    "Чет Хольмгрен": "Chet Holmgren",

    # All-Stars & Key Players
    "Джейлен Браун": "Jaylen Brown",
    "Бэм Адебайо": "Bam Adebayo",
    "Паскаль Сиакам": "Pascal Siakam",
    "Домантас Сабонис": "Domantas Sabonis",
    "Карл-Энтони Таунс": "Karl-Anthony Towns",
    "Руди Гобер": "Rudy Gobert",
    "Джален Брансон": "Jalen Brunson",
    "Джулиус Рэндл": "Julius Randle",
    "Дрэймонд Грин": "Draymond Green",
    "Клэй Томпсон": "Klay Thompson",
    "Крис Пол": "Chris Paul",
    "Расселл Уэстбрук": "Russell Westbrook",
    "Джеймс Харден": "James Harden",
    "Брэдли Бил": "Bradley Beal",
    "Демар Дерозан": "DeMar DeRozan",
    "Зак Лавин": "Zach LaVine",
    "Ламело Болл": "LaMelo Ball",
    "Лонзо Болл": "Lonzo Ball",
    "Брэндон Ингрэм": "Brandon Ingram",
    "Джамал Мюррэй": "Jamal Murray",
    "Майкл Портер": "Michael Porter Jr.",
    "Аарон Гордон": "Aaron Gordon",
    "Скотти Барнс": "Scottie Barnes",
    "Эван Мобли": "Evan Mobley",
    "Джарретт Аллен": "Jarrett Allen",
    "Микал Бриджес": "Mikal Bridges",
    "Джру Холидей": "Jrue Holiday",
    "Крис Миддлтон": "Khris Middleton",
    "Брук Лопес": "Brook Lopez",
    "Тайриз Макси": "Tyrese Maxey",
    "Десмонд Бэйн": "Desmond Bane",
    "Джарен Джексон": "Jaren Jackson Jr.",
    "Фред Ванвлит": "Fred VanVleet",
    "Альперен Шенгюн": "Alperen Sengun",
    "Джален Грин": "Jalen Green",
    "Франц Вагнер": "Franz Wagner",
    "Кейд Каннингем": "Cade Cunningham",
    "Анферни Саймонс": "Anfernee Simons",
    "Деррик Уайт": "Derrick White",
    "Эл Хорфорд": "Al Horford",
    "Кристапс Порзингис": "Kristaps Porzingis",
    "Остин Ривз": "Austin Reaves",
    "Руи Хатимура": "Rui Hachimura",
    "Ди'Анджело Расселл": "D'Angelo Russell",

    # Role Players
    "Тайлер Хирро": "Tyler Herro",
    "Кайл Кузма": "Kyle Kuzma",
    "Алекс Карузо": "Alex Caruso",
    "Диллон Брукс": "Dillon Brooks",
    "Лугенц Дорт": "Lu Dort",
    "Джейден Айви": "Jaden Ivey",
    "Эндрю Уиггинс": "Andrew Wiggins",
    "Джонатан Куминга": "Jonathan Kuminga",
    "Джордан Пул": "Jordan Poole",
    "Богдан Богданович": "Bogdan Bogdanovic",
    "Никола Вучевич": "Nikola Vucevic",
    "Майлс Тёрнер": "Myles Turner",
    "Лаури Маркканен": "Lauri Markkanen",
    "Джордан Кларксон": "Jordan Clarkson",
    "Джош Гидди": "Josh Giddey",
    "Аарон Уиггинс": "Aaron Wiggins",
    "Джейлин Уильямс": "Jalen Williams",
    "Кейсон Уоллес": "Cason Wallace",
    "Исайя Джо": "Isaiah Joe",
    "Де'Андре Хантер": "De'Andre Hunter",
    "Дин Уэйд": "Dean Wade",
    "Аджай Митчелл": "AJ Mitchell",
    "Джейлон Тайсон": "Jaylon Tyson",
    "Крейг Портер-мл.": "Craig Porter Jr.",
    "Кевин Портер-младший": "Kevin Porter Jr.",
    "Майкл Портер-младший": "Michael Porter Jr.",
    "Яннис Адетокунбо": "Giannis Antetokounmpo",
    "Бобби Портис": "Bobby Portis",
    "Дайсон Дэниелс": "Dyson Daniels",
    "Никкиль Александер-Уокер": "Nickeil Alexander-Walker",
    "Джейлен Джонсон": "Jalen Johnson",
    "Майлс Тернер": "Myles Turner",
    "Николас Клэкстон": "Nic Claxton",
    "Марк Уильямс": "Mark Williams",
    "Ной Клоуни": "Noah Clowney",
    "Девин Букер": "Devin Booker",
}

# Обратный словарь
ENGLISH_TO_RUSSIAN_PLAYERS = {v: k for k, v in RUSSIAN_TO_ENGLISH_PLAYERS.items()}


def normalize_player_name(name: str) -> str:
    """Нормализация имени игрока для сравнения."""
    # Убираем лишние пробелы и приводим к нижнему регистру
    name = name.strip().lower()
    # Убираем суффиксы
    for suffix in [" jr.", " jr", " iii", " ii", " sr.", " sr"]:
        name = name.replace(suffix, "")
    return name


def get_english_name(russian_name: str) -> Optional[str]:
    """Получить английское имя по русскому."""
    return RUSSIAN_TO_ENGLISH_PLAYERS.get(russian_name)


def get_russian_name(english_name: str) -> Optional[str]:
    """Получить русское имя по английскому."""
    return ENGLISH_TO_RUSSIAN_PLAYERS.get(english_name)


def load_odds_from_csv(file_path: str = DEFAULT_ODDS_FILE) -> Dict[str, List[PlayerOdds]]:
    """
    Загрузка коэффициентов из CSV файла.

    Returns:
        Словарь {normalized_player_name: [PlayerOdds, ...]}
    """
    if not os.path.exists(file_path):
        print(f"Файл не найден: {file_path}")
        return {}

    odds_by_player = {}

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')

        # Группируем строки по игроку и типу ставки
        rows_by_key = {}

        for row in reader:
            player = row.get('Player', '')
            game_type = row.get('GameType', '')
            event_type = row.get('EventType', '')
            param = row.get('Param', '')
            coef = row.get('Coef', '')
            team1 = row.get('Opp1', '')
            team2 = row.get('Opp2', '')
            game_date = row.get('Start', '')

            if not player or not param or not coef:
                continue

            # Определяем тип статистики
            stat_type = None
            if game_type == 'GoalPlayers' and 'total_player' in event_type:
                stat_type = 'points'
            elif game_type == 'Rebounds' and 'podbor' in event_type.lower():
                stat_type = 'rebounds'
            elif game_type == 'Pass' or 'peredacha' in event_type.lower():
                stat_type = 'assists'
            elif game_type == 'ScoreReboundsTransfer':
                stat_type = 'pra'  # Points + Rebounds + Assists

            if not stat_type:
                continue

            # Определяем больше/меньше
            is_over = event_type.endswith('_B') or 'bolee' in event_type.lower()
            is_under = event_type.endswith('_M')

            try:
                total_line = float(param)
                odds = float(coef)
            except ValueError:
                continue

            # Ключ для группировки
            key = (player, team1, team2, game_date, stat_type, total_line)

            if key not in rows_by_key:
                rows_by_key[key] = {'over': None, 'under': None}

            if is_over:
                rows_by_key[key]['over'] = odds
            elif is_under:
                rows_by_key[key]['under'] = odds

        # Создаём объекты PlayerOdds
        for (player, team1, team2, game_date, stat_type, total_line), odds_data in rows_by_key.items():
            if odds_data['over'] is None and odds_data['under'] is None:
                continue

            player_odds = PlayerOdds(
                player_name=player,
                team1=team1,
                team2=team2,
                game_date=game_date,
                stat_type=stat_type,
                total_line=total_line,
                over_odds=odds_data['over'] or 0,
                under_odds=odds_data['under'] or 0
            )

            # Нормализуем имя для поиска
            norm_name = normalize_player_name(player)
            if norm_name not in odds_by_player:
                odds_by_player[norm_name] = []
            odds_by_player[norm_name].append(player_odds)

    return odds_by_player


def odds_to_probability(odds: float) -> float:
    """Конвертация коэффициента в вероятность (без учёта маржи)."""
    if odds <= 1:
        return 0
    return 1 / odds


def find_player_odds(
    player_name: str,
    odds_data: Dict[str, List[PlayerOdds]],
    stat_type: str = None
) -> List[PlayerOdds]:
    """
    Поиск коэффициентов для игрока.

    Args:
        player_name: Имя игрока (английское или русское)
        odds_data: Загруженные данные
        stat_type: Тип статистики ('points', 'rebounds', 'assists', 'pra')

    Returns:
        Список найденных коэффициентов
    """
    # Пробуем найти по английскому имени
    norm_name = normalize_player_name(player_name)

    # Пробуем русское имя если есть
    russian_name = get_russian_name(player_name)
    if russian_name:
        norm_russian = normalize_player_name(russian_name)
    else:
        norm_russian = None

    # Фамилия для дополнительного поиска
    last_name = player_name.split()[-1].lower() if ' ' in player_name else player_name.lower()

    results = []

    for key, odds_list in odds_data.items():
        # Ключ может быть составным (игрок1/игрок2), разбиваем
        key_parts = key.split('/')

        found = False
        for part in key_parts:
            part = part.strip()
            # Точное совпадение с нормализованным именем
            if part == norm_name or (norm_russian and part == norm_russian):
                found = True
                break
            # Частичное совпадение (имя содержится в ключе)
            if norm_name in part or (norm_russian and norm_russian in part):
                found = True
                break

        if found:
            for odds in odds_list:
                if stat_type is None or odds.stat_type == stat_type:
                    results.append(odds)

    return results


def compare_ai_with_odds(
    ai_prediction_range: Tuple[float, float],
    total_line: float,
    over_odds: float,
    under_odds: float
) -> Dict:
    """
    Сравнение прогноза AI с линией букмекера.

    Args:
        ai_prediction_range: (min, max) прогноз AI
        total_line: Линия тотала
        over_odds: Коэффициент на больше
        under_odds: Коэффициент на меньше

    Returns:
        Словарь с результатами сравнения
    """
    ai_min, ai_max = ai_prediction_range
    ai_mid = (ai_min + ai_max) / 2

    over_prob = odds_to_probability(over_odds) if over_odds > 1 else 0
    under_prob = odds_to_probability(under_odds) if under_odds > 1 else 0

    # Оценка: насколько прогноз AI выше/ниже линии
    diff_from_line = ai_mid - total_line

    # Определяем направление прогноза AI
    if ai_min > total_line:
        ai_direction = "over"
        ai_confidence = "high"
    elif ai_max < total_line:
        ai_direction = "under"
        ai_confidence = "high"
    elif ai_mid > total_line:
        ai_direction = "over"
        ai_confidence = "medium"
    else:
        ai_direction = "under"
        ai_confidence = "medium"

    # Проверяем согласованность с коэффициентами
    # Меньший коэффициент = более вероятный исход по мнению букмекера
    if over_odds > 0 and under_odds > 0:
        bookie_favors = "over" if over_odds < under_odds else "under"
    elif over_odds > 0:
        bookie_favors = "over"  # Только коэф на больше доступен
    elif under_odds > 0:
        bookie_favors = "under"  # Только коэф на меньше доступен
    else:
        bookie_favors = "neutral"  # Нет данных

    agreement = ai_direction == bookie_favors if bookie_favors != "neutral" else True

    return {
        'total_line': total_line,
        'ai_prediction': f"{ai_min}-{ai_max}",
        'ai_midpoint': ai_mid,
        'diff_from_line': diff_from_line,
        'ai_direction': ai_direction,
        'ai_confidence': ai_confidence,
        'over_odds': over_odds,
        'under_odds': under_odds,
        'over_probability': f"{over_prob*100:.1f}%",
        'under_probability': f"{under_prob*100:.1f}%",
        'bookie_favors': bookie_favors,
        'ai_agrees_with_bookie': agreement,
        'value_bet': not agreement  # Потенциальная value ставка если AI не согласен с букмекером
    }


def format_odds_comparison(player_name: str, comparisons: List[Dict]) -> str:
    """Форматирование сравнения для вывода."""
    if not comparisons:
        return f"Нет данных о коэффициентах для {player_name}"

    lines = [f"\n📊 СРАВНЕНИЕ С БУКМЕКЕРСКИМИ ЛИНИЯМИ для {player_name}:\n"]

    for comp in comparisons:
        stat_emoji = {
            'points': '🏀',
            'rebounds': '📊',
            'assists': '🎯',
            'pra': '📈'
        }.get(comp.get('stat_type', ''), '•')

        stat_name = {
            'points': 'Очки',
            'rebounds': 'Подборы',
            'assists': 'Передачи',
            'pra': 'О+П+П'
        }.get(comp.get('stat_type', ''), 'Стат')

        line = comp['total_line']
        ai_pred = comp['ai_prediction']
        over = comp['over_odds']
        under = comp['under_odds']

        direction_emoji = "⬆️" if comp['ai_direction'] == 'over' else "⬇️"
        agree_emoji = "✅" if comp['ai_agrees_with_bookie'] else "⚠️"

        lines.append(f"{stat_emoji} {stat_name} (линия {line}):")
        lines.append(f"   AI прогноз: {ai_pred} {direction_emoji}")
        lines.append(f"   Коэфы: Б{line} = {over}, М{line} = {under}")
        lines.append(f"   Букмекер ставит на: {'больше' if comp['bookie_favors'] == 'over' else 'меньше'}")
        lines.append(f"   AI {'согласен' if comp['ai_agrees_with_bookie'] else 'НЕ согласен'} с букмекером {agree_emoji}")

        if comp['value_bet']:
            lines.append(f"   💡 Потенциальная value ставка!")
        lines.append("")

    return "\n".join(lines)


# Глобальный кэш загруженных данных
_odds_cache = None


def get_cached_odds() -> Dict[str, List[PlayerOdds]]:
    """Получить закэшированные данные или загрузить."""
    global _odds_cache
    if _odds_cache is None:
        _odds_cache = load_odds_from_csv()
    return _odds_cache


def reload_odds():
    """Перезагрузить данные."""
    global _odds_cache
    _odds_cache = load_odds_from_csv()
    return _odds_cache


# Тест
if __name__ == "__main__":
    print("Загрузка коэффициентов...")
    odds = load_odds_from_csv()
    print(f"Загружено данных для {len(odds)} игроков")

    # Показать примеры
    for player_norm, player_odds in list(odds.items())[:3]:
        print(f"\n{player_norm}:")
        for po in player_odds[:2]:
            print(f"  {po.stat_type}: {po.total_line} (Б:{po.over_odds}, М:{po.under_odds})")

    # Тест поиска
    print("\n\nПоиск для Donovan Mitchell:")
    results = find_player_odds("Donovan Mitchell", odds, "points")
    for r in results:
        print(f"  Points: {r.total_line} (O:{r.over_odds}, U:{r.under_odds})")
