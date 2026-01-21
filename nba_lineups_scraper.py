"""
NBA Lineups Scraper - получение составов команд NBA с Rotowire
+ исторические данные с Basketball Reference
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
import re
import urllib3
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Отключаем предупреждения о непроверенных SSL сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Получаем прокси из переменных окружения
PROXY_HTTP = os.getenv('PROXY_HTTP')
PROXY_HTTPS = os.getenv('PROXY_HTTPS')

# Настройка прокси для requests
PROXIES = None
if PROXY_HTTP and PROXY_HTTPS:
    PROXIES = {
        'http': PROXY_HTTP,
        'https': PROXY_HTTPS
    }
    print(f"[INFO] Используется прокси: {PROXY_HTTP.split('@')[1] if '@' in PROXY_HTTP else PROXY_HTTP}")

# URL страницы с составами
ROTOWIRE_URL = "https://www.rotowire.com/basketball/nba-lineups.php"

# Basketball Reference base URL
BBREF_BASE_URL = "https://www.basketball-reference.com"

# Headers для имитации браузера
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def fetch_page(url: str) -> BeautifulSoup:
    """Загрузка и парсинг страницы."""
    try:
        # Добавляем timeout, verify=False и прокси если доступен
        response = requests.get(url, headers=HEADERS, timeout=30, verify=False, proxies=PROXIES)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.SSLError as e:
        print(f"SSL Error при подключении к {url}: {e}")
        # Пробуем еще раз без проверки сертификата
        response = requests.get(url, headers=HEADERS, timeout=30, verify=False, proxies=PROXIES)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error при подключении к {url}: {e}")
        raise Exception(f"Не удалось подключиться к {url}. Проверьте интернет-соединение или настройки прокси.")
    except Exception as e:
        print(f"Error при загрузке {url}: {e}")
        raise


def parse_lineups(soup: BeautifulSoup) -> list:
    """
    Парсинг составов команд из HTML.
    Возвращает список игр с составами.
    """
    games = []

    # Ищем основные контейнеры игр - класс "lineup is-nba"
    game_containers = soup.find_all('div', class_='lineup')

    print(f"Найдено контейнеров: {len(game_containers)}")

    valid_games = 0
    for container in game_containers:
        # Проверяем что это NBA игра
        classes = container.get('class', [])
        if 'is-nba' not in classes:
            continue

        # Пропускаем рекламные блоки
        if container.find(class_='picks-logo') or container.find(class_='picks-headline'):
            continue

        # Проверяем что это реальная игра (есть команды)
        if not container.find(class_='lineup__abbr'):
            continue

        game_data = parse_game_container(container)
        if game_data and game_data['away_team']['abbrev']:
            games.append(game_data)
            valid_games += 1

    print(f"Валидных игр: {valid_games}")

    return games


def parse_game_container(container) -> dict:
    """Парсинг контейнера игры (включая meta информацию)."""
    try:
        game = {
            'game_time': None,
            'away_team': {'abbrev': None, 'record': None, 'lineup': [], 'injuries': []},
            'home_team': {'abbrev': None, 'record': None, 'lineup': [], 'injuries': []},
            'away_injuries': [],  # Для удобного доступа
            'home_injuries': [],  # Для удобного доступа
        }

        # Время игры (класс lineup__time в lineup__meta)
        time_elem = container.find(class_='lineup__time')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            # Фильтруем нежелательные значения
            if 'interested' not in time_text.lower() and time_text:
                game['game_time'] = time_text

        # Теперь ищем lineup__box внутри контейнера
        box = container.find('div', class_='lineup__box')
        if box:
            # Команды (класс lineup__abbr)
            teams = box.find_all(class_='lineup__abbr')
            if len(teams) >= 2:
                game['away_team']['abbrev'] = teams[0].get_text(strip=True)
                game['home_team']['abbrev'] = teams[1].get_text(strip=True)

            # Записи W-L (класс lineup__wl)
            records = box.find_all(class_='lineup__wl')
            if len(records) >= 2:
                game['away_team']['record'] = records[0].get_text(strip=True)
                game['home_team']['record'] = records[1].get_text(strip=True)

            # Списки игроков (класс lineup__list)
            lineup_lists = box.find_all('ul', class_='lineup__list')

            if len(lineup_lists) >= 2:
                # Первый список - away team, второй - home team
                game['away_team']['lineup'] = parse_lineup_list(lineup_lists[0])
                game['home_team']['lineup'] = parse_lineup_list(lineup_lists[1])

                # Извлекаем травмированных игроков из линапа в отдельный список
                # Только OUT и DOUBTFUL считаются реальными травмами
                # PROBABLE и QUESTIONABLE - игрок скорее всего будет играть
                for player in game['away_team']['lineup']:
                    if player.get('status') in ['out', 'doubtful']:
                        game['away_team']['injuries'].append(player['name'])

                for player in game['home_team']['lineup']:
                    if player.get('status') in ['out', 'doubtful']:
                        game['home_team']['injuries'].append(player['name'])

        # Копируем травмы на уровень игры для удобного доступа
        game['away_injuries'] = game['away_team']['injuries']
        game['home_injuries'] = game['home_team']['injuries']

        return game

    except Exception as e:
        print(f"Ошибка при парсинге контейнера: {e}")
        return None


def parse_game_block(block) -> dict:
    """Парсинг одного блока игры."""
    try:
        game = {
            'game_time': None,
            'away_team': {'abbrev': None, 'record': None, 'lineup': [], 'injuries': []},
            'home_team': {'abbrev': None, 'record': None, 'lineup': [], 'injuries': []},
        }

        # Время игры (класс lineup__time)
        time_elem = block.find(class_='lineup__time')
        if time_elem:
            game['game_time'] = time_elem.get_text(strip=True)

        # Команды (класс lineup__abbr)
        teams = block.find_all(class_='lineup__abbr')
        if len(teams) >= 2:
            game['away_team']['abbrev'] = teams[0].get_text(strip=True)
            game['home_team']['abbrev'] = teams[1].get_text(strip=True)

        # Записи W-L (класс lineup__wl)
        records = block.find_all(class_='lineup__wl')
        if len(records) >= 2:
            game['away_team']['record'] = records[0].get_text(strip=True)
            game['home_team']['record'] = records[1].get_text(strip=True)

        # Списки игроков (класс lineup__list)
        lineup_lists = block.find_all('ul', class_='lineup__list')

        if len(lineup_lists) >= 2:
            # Первый список - away team, второй - home team
            game['away_team']['lineup'] = parse_lineup_list(lineup_lists[0])
            game['home_team']['lineup'] = parse_lineup_list(lineup_lists[1])

            # Извлекаем травмированных игроков из линапа в отдельный список
            for player in game['away_team']['lineup']:
                if player.get('status') != 'active':
                    game['away_team']['injuries'].append(player['name'])

            for player in game['home_team']['lineup']:
                if player.get('status') != 'active':
                    game['home_team']['injuries'].append(player['name'])

        # Ищем также секцию с травмированными (может быть отдельно)
        injury_sections = block.find_all(class_='lineup__inj')
        # Парсим травмы если есть

        return game

    except Exception as e:
        print(f"Ошибка при парсинге блока: {e}")
        return None


def parse_lineup_list(ul_elem) -> list:
    """Парсинг списка игроков из ul элемента."""
    players = []

    # Каждый игрок в li с классом lineup__player
    player_elems = ul_elem.find_all('li', class_='lineup__player')

    for player_elem in player_elems:
        player = parse_player(player_elem)
        if player:
            players.append(player)

    return players


def parse_player(player_elem) -> dict:
    """Парсинг данных одного игрока."""
    try:
        player = {
            'name': None,
            'position': None,
            'status': 'active',  # active, out, gtd (game-time decision)
            'injury_note': None,
        }

        # Позиция (класс lineup__pos)
        pos_elem = player_elem.find(class_='lineup__pos')
        if pos_elem:
            player['position'] = pos_elem.get_text(strip=True)

        # Имя игрока (обычно в теге <a>)
        name_elem = player_elem.find('a')
        if name_elem:
            player['name'] = name_elem.get_text(strip=True)

        # Статус травмы (класс lineup__inj)
        inj_elem = player_elem.find(class_='lineup__inj')
        if inj_elem:
            inj_text = inj_elem.get_text(strip=True).lower()
            player['injury_note'] = inj_elem.get_text(strip=True)

            if 'out' in inj_text:
                player['status'] = 'out'
            elif 'gtd' in inj_text or 'doubtful' in inj_text or 'doub' in inj_text:
                player['status'] = 'doubtful'
            elif 'ques' in inj_text or 'questionable' in inj_text:
                player['status'] = 'questionable'
            elif 'prob' in inj_text or 'probable' in inj_text:
                player['status'] = 'probable'

        # Проверяем класс элемента на статус
        elem_classes = player_elem.get('class', [])
        class_str = ' '.join(elem_classes).lower()
        if 'is-out' in class_str:
            player['status'] = 'out'
        elif 'is-gtd' in class_str:
            player['status'] = 'gtd'

        return player if player['name'] else None

    except Exception as e:
        print(f"Ошибка при парсинге игрока: {e}")
        return None


def get_nba_lineups() -> pd.DataFrame:
    """
    Основная функция - получает составы NBA.
    Возвращает DataFrame с данными.
    """
    print(f"Загрузка данных с {ROTOWIRE_URL}...")

    soup = fetch_page(ROTOWIRE_URL)

    # Парсим составы
    games = parse_lineups(soup)

    # Преобразуем в плоский DataFrame
    rows = []
    for game in games:
        game_time = game.get('game_time')

        for team_type in ['away_team', 'home_team']:
            team = game.get(team_type, {})
            team_abbrev = team.get('abbrev')
            team_record = team.get('record')

            for player in team.get('lineup', []):
                rows.append({
                    'game_time': game_time,
                    'team': team_abbrev,
                    'team_record': team_record,
                    'team_type': 'away' if team_type == 'away_team' else 'home',
                    'player_name': player.get('name'),
                    'position': player.get('position'),
                    'status': player.get('status'),
                    'injury_note': player.get('injury_note'),
                })

    df = pd.DataFrame(rows)
    return df


def get_nba_lineups_detailed() -> list:
    """
    Возвращает детальную структуру с играми.
    """
    print(f"Загрузка данных с {ROTOWIRE_URL}...")

    soup = fetch_page(ROTOWIRE_URL)
    games = parse_lineups(soup)

    return games


def print_lineups(games: list):
    """Красивый вывод составов."""
    for i, game in enumerate(games, 1):
        print(f"\n{'='*60}")
        print(f"GAME {i}: {game['game_time'] or 'TBD'}")
        print(f"{'='*60}")

        away = game['away_team']
        home = game['home_team']

        print(f"\n{away['abbrev']} ({away['record']}) @ {home['abbrev']} ({home['record']})")

        print(f"\n--- {away['abbrev']} Lineup ---")
        for p in away['lineup']:
            status_icon = ""
            if p['status'] == 'out':
                status_icon = " [OUT]"
            elif p['status'] == 'gtd':
                status_icon = " [GTD]"
            print(f"  {p['position']}: {p['name']}{status_icon}")

        print(f"\n--- {home['abbrev']} Lineup ---")
        for p in home['lineup']:
            status_icon = ""
            if p['status'] == 'out':
                status_icon = " [OUT]"
            elif p['status'] == 'gtd':
                status_icon = " [GTD]"
            print(f"  {p['position']}: {p['name']}{status_icon}")


# ===== NBA API для исторических данных =====

def get_team_last_n_games_stats(team_abbrev: str, n_games: int = 3, season: str = '2025-26') -> dict:
    """
    Получение статистики стартеров за последние N игр команды.

    Args:
        team_abbrev: Аббревиатура команды (например, 'LAL', 'BOS')
        n_games: Количество последних игр
        season: Сезон в формате '2025-26'

    Returns:
        dict с информацией о последних играх и статистикой стартеров
    """
    try:
        from nba_api.stats.endpoints import teamgamelog, boxscoretraditionalv3
        from nba_api.stats.static import teams
        import time

        # Находим ID команды
        nba_teams = teams.get_teams()
        team = None
        for t in nba_teams:
            if t['abbreviation'] == team_abbrev:
                team = t
                break

        if not team:
            print(f"Команда {team_abbrev} не найдена")
            return None

        # Получаем лог игр команды
        time.sleep(1.0)
        gamelog = teamgamelog.TeamGameLog(team_id=team['id'], season=season)
        df = gamelog.get_data_frames()[0]

        if df.empty:
            print(f"Нет игр для {team_abbrev}")
            return None

        # Берём последние N игр
        last_games = df.head(n_games)

        games_data = []

        for _, game_row in last_games.iterrows():
            game_id = game_row['Game_ID']
            game_date = game_row['GAME_DATE']
            matchup = game_row['MATCHUP']
            result = game_row['WL']
            team_pts = int(game_row['PTS']) if pd.notna(game_row['PTS']) else 0

            # Получаем boxscore (используем V3 - работает для сезона 2025-26)
            time.sleep(1.0)
            boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            player_df = boxscore.get_data_frames()[0]

            # Фильтруем игроков нашей команды (V3 использует 'teamTricode' и 'position')
            team_players = player_df[player_df['teamTricode'] == team_abbrev]
            # В V3 стартеры - это те у кого position не пустая (F, C, G)
            starters_df = team_players[team_players['position'] != '']
            bench_df = team_players[team_players['position'] == '']

            # Собираем имена стартеров для проверки
            starter_names = set()
            for _, row in starters_df.iterrows():
                starter_names.add(f"{row['firstName']} {row['familyName']}")

            starters_stats = []
            bench_stats = []

            # Стартеры
            for _, row in starters_df.iterrows():
                player_name = f"{row['firstName']} {row['familyName']}"
                starters_stats.append({
                    'name': player_name,
                    'position': row['position'],
                    'min': row['minutes'],
                    'pts': int(row['points']) if pd.notna(row['points']) else 0,
                    'reb': int(row['reboundsTotal']) if pd.notna(row['reboundsTotal']) else 0,
                    'ast': int(row['assists']) if pd.notna(row['assists']) else 0,
                    'stl': int(row['steals']) if pd.notna(row['steals']) else 0,
                    'blk': int(row['blocks']) if pd.notna(row['blocks']) else 0,
                    'fgm': int(row['fieldGoalsMade']) if pd.notna(row['fieldGoalsMade']) else 0,
                    'fga': int(row['fieldGoalsAttempted']) if pd.notna(row['fieldGoalsAttempted']) else 0,
                    'fg3m': int(row['threePointersMade']) if pd.notna(row['threePointersMade']) else 0,
                    'fg3a': int(row['threePointersAttempted']) if pd.notna(row['threePointersAttempted']) else 0,
                    'to': int(row['turnovers']) if pd.notna(row['turnovers']) else 0,
                    'is_starter': True,
                })

            # Скамейка (только те кто играл - минуты > 0)
            for _, row in bench_df.iterrows():
                mins = row['minutes']
                # Пропускаем игроков которые не играли
                if not mins or mins == '0:00' or mins == 'PT00M00.00S':
                    continue
                player_name = f"{row['firstName']} {row['familyName']}"
                bench_stats.append({
                    'name': player_name,
                    'position': 'BENCH',  # Помечаем как скамейку
                    'min': mins,
                    'pts': int(row['points']) if pd.notna(row['points']) else 0,
                    'reb': int(row['reboundsTotal']) if pd.notna(row['reboundsTotal']) else 0,
                    'ast': int(row['assists']) if pd.notna(row['assists']) else 0,
                    'stl': int(row['steals']) if pd.notna(row['steals']) else 0,
                    'blk': int(row['blocks']) if pd.notna(row['blocks']) else 0,
                    'fgm': int(row['fieldGoalsMade']) if pd.notna(row['fieldGoalsMade']) else 0,
                    'fga': int(row['fieldGoalsAttempted']) if pd.notna(row['fieldGoalsAttempted']) else 0,
                    'fg3m': int(row['threePointersMade']) if pd.notna(row['threePointersMade']) else 0,
                    'fg3a': int(row['threePointersAttempted']) if pd.notna(row['threePointersAttempted']) else 0,
                    'to': int(row['turnovers']) if pd.notna(row['turnovers']) else 0,
                    'is_starter': False,
                })

            # Сортируем стартеров по позиции (G -> F -> C) и затем по имени
            position_order = {'G': 0, 'F': 1, 'C': 2}
            starters_stats.sort(key=lambda x: (position_order.get(x['position'], 9), x['name']))

            games_data.append({
                'game_id': game_id,
                'date': game_date,
                'matchup': matchup,
                'result': result,
                'team_pts': team_pts,
                'starters': starters_stats,
                'bench': bench_stats,  # Добавляем статистику скамейки
                'all_players': starters_stats + bench_stats,  # Все игроки
            })

        return {
            'team': team_abbrev,
            'team_name': team['full_name'],
            'games': games_data
        }

    except Exception as e:
        print(f"Ошибка получения статистики для {team_abbrev}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_team_last_game_starters_nba_api(team_abbrev: str, season: str = '2025-26') -> dict:
    """
    Получение стартового состава команды в последней игре через NBA API.

    Args:
        team_abbrev: Аббревиатура команды (например, 'LAL', 'BOS')
        season: Сезон в формате '2025-26'

    Returns:
        dict с информацией о последней игре и стартерах
    """
    try:
        from nba_api.stats.endpoints import teamgamelog, boxscoretraditionalv3
        from nba_api.stats.static import teams
        import time

        # Находим ID команды
        nba_teams = teams.get_teams()
        team = None
        for t in nba_teams:
            if t['abbreviation'] == team_abbrev:
                team = t
                break

        if not team:
            print(f"Команда {team_abbrev} не найдена")
            return None

        # Получаем лог игр команды
        time.sleep(1.0)  # Rate limiting
        gamelog = teamgamelog.TeamGameLog(team_id=team['id'], season=season)
        df = gamelog.get_data_frames()[0]

        if df.empty:
            print(f"Нет игр для {team_abbrev}")
            return None

        # Последняя игра
        last_game = df.iloc[0]
        game_id = last_game['Game_ID']
        game_date = last_game['GAME_DATE']
        matchup = last_game['MATCHUP']
        result = last_game['WL']

        # Получаем boxscore для стартеров (V3 для сезона 2025-26)
        time.sleep(1.0)
        boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
        player_df = boxscore.get_data_frames()[0]

        # Фильтруем игроков нужной команды и стартеров (V3 названия колонок)
        team_players = player_df[player_df['teamTricode'] == team_abbrev]
        starters = team_players[team_players['position'] != '']

        starters_list = []
        for _, row in starters.iterrows():
            player_name = f"{row['firstName']} {row['familyName']}"
            starters_list.append({
                'name': player_name,
                'position': row['position']
            })

        # Сортируем по позиции (G -> F -> C) и затем по имени
        position_order = {'G': 0, 'F': 1, 'C': 2}
        starters_list.sort(key=lambda x: (position_order.get(x['position'], 9), x['name']))

        return {
            'team': team_abbrev,
            'game_id': game_id,
            'date': game_date,
            'matchup': matchup,
            'result': result,
            'starters': starters_list,
            'starters_names': [s['name'] for s in starters_list]
        }

    except Exception as e:
        print(f"Ошибка получения данных NBA API для {team_abbrev}: {e}")
        return None


def get_multiple_teams_last_starters(team_abbrevs: list, season: str = '2025-26') -> dict:
    """
    Получение последних стартовых составов для нескольких команд.
    """
    results = {}
    for abbrev in team_abbrevs:
        print(f"Загрузка {abbrev}...")
        data = get_team_last_game_starters_nba_api(abbrev, season)
        if data:
            results[abbrev] = data
    return results


# ===== Basketball Reference (backup, требует обход блокировки) =====

# Маппинг аббревиатур команд для Basketball Reference
TEAM_ABBREV_MAP = {
    'ATL': 'ATL', 'BOS': 'BOS', 'BKN': 'BRK', 'CHA': 'CHO', 'CHI': 'CHI',
    'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN', 'DET': 'DET', 'GSW': 'GSW',
    'HOU': 'HOU', 'IND': 'IND', 'LAC': 'LAC', 'LAL': 'LAL', 'MEM': 'MEM',
    'MIA': 'MIA', 'MIL': 'MIL', 'MIN': 'MIN', 'NOP': 'NOP', 'NYK': 'NYK',
    'OKC': 'OKC', 'ORL': 'ORL', 'PHI': 'PHI', 'PHX': 'PHO', 'POR': 'POR',
    'SAC': 'SAC', 'SAS': 'SAS', 'TOR': 'TOR', 'UTA': 'UTA', 'WAS': 'WAS',
}


def get_team_last_game_starters(team_abbrev: str, season: int = 2025) -> dict:
    """
    Получение стартового состава команды в последней игре с Basketball Reference.

    Args:
        team_abbrev: Аббревиатура команды (например, 'LAL', 'BOS')
        season: Сезон (год окончания, например 2025 для сезона 2024-25)

    Returns:
        dict с информацией о последней игре и стартерах
    """
    # Конвертируем аббревиатуру
    bbref_abbrev = TEAM_ABBREV_MAP.get(team_abbrev, team_abbrev)

    url = f"{BBREF_BASE_URL}/teams/{bbref_abbrev}/{season}_start.html"

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем таблицу стартовых составов
        table = soup.find('table', {'id': 'starting_lineups'})
        if not table:
            print(f"Таблица стартовых составов не найдена для {team_abbrev}")
            return None

        # Получаем последнюю строку (последняя игра)
        tbody = table.find('tbody')
        if not tbody:
            return None

        rows = tbody.find_all('tr')
        if not rows:
            return None

        # Берём последнюю строку
        last_row = rows[-1]

        # Парсим данные
        result = {
            'team': team_abbrev,
            'game_number': None,
            'date': None,
            'opponent': None,
            'result': None,
            'starters': []
        }

        cells = last_row.find_all(['th', 'td'])

        for cell in cells:
            data_stat = cell.get('data-stat', '')

            if data_stat == 'g':
                result['game_number'] = cell.get_text(strip=True)
            elif data_stat == 'date_game':
                date_link = cell.find('a')
                if date_link:
                    result['date'] = date_link.get_text(strip=True)
            elif data_stat == 'opp_id':
                opp_link = cell.find('a')
                if opp_link:
                    result['opponent'] = opp_link.get_text(strip=True)
            elif data_stat == 'game_result':
                result['result'] = cell.get_text(strip=True)
            elif data_stat == 'gs':
                # Стартовый состав - несколько ссылок на игроков
                player_links = cell.find_all('a')
                for player_link in player_links:
                    player_name = player_link.get_text(strip=True)
                    if player_name:
                        result['starters'].append(player_name)

        return result

    except Exception as e:
        print(f"Ошибка получения данных для {team_abbrev}: {e}")
        return None


def get_all_teams_last_starters(team_abbrevs: list = None) -> dict:
    """
    Получение последних стартовых составов для списка команд.

    Args:
        team_abbrevs: Список аббревиатур команд. Если None - все команды.

    Returns:
        dict: {team_abbrev: last_game_data}
    """
    if team_abbrevs is None:
        team_abbrevs = list(TEAM_ABBREV_MAP.keys())

    results = {}

    for abbrev in team_abbrevs:
        print(f"Загрузка данных для {abbrev}...")
        data = get_team_last_game_starters(abbrev)
        if data:
            results[abbrev] = data
        # Небольшая задержка чтобы не перегружать сервер
        import time
        time.sleep(0.5)

    return results


def compare_with_previous_game(current_starters: list, previous_starters: list) -> dict:
    """
    Сравнение текущего состава с предыдущим.

    Returns:
        dict с изменениями: новые игроки, выбывшие игроки
    """
    current_set = set(current_starters)
    previous_set = set(previous_starters)

    return {
        'new_starters': list(current_set - previous_set),
        'removed_starters': list(previous_set - current_set),
        'unchanged': list(current_set & previous_set),
        'has_changes': current_set != previous_set
    }


if __name__ == "__main__":
    # Получаем данные
    games = get_nba_lineups_detailed()

    if games:
        # Выводим красиво
        print_lineups(games)

        # Также создаем DataFrame
        print("\n\n=== DataFrame ===")
        df = get_nba_lineups()
        print(df.to_string())

        # Сохраняем в CSV
        df.to_csv("d:/scripts/nba_lineups/nba_lineups.csv", index=False, encoding='utf-8')
        print("\nДанные сохранены в nba_lineups.csv")

        # Тестируем получение предыдущей игры
        print("\n\n=== Последняя игра LAL ===")
        lal_last = get_team_last_game_starters('LAL')
        if lal_last:
            print(f"Дата: {lal_last['date']}")
            print(f"Соперник: {lal_last['opponent']}")
            print(f"Результат: {lal_last['result']}")
            print(f"Стартеры: {', '.join(lal_last['starters'])}")
    else:
        print("Данные не получены")
