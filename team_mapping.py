"""
Маппинг названий команд NBA: английские <-> русские
Используется для поиска новостей по команде
"""

# Полный маппинг всех 30 команд NBA
# Формат: abbrev -> {english, russian_full, russian_short, keywords}

NBA_TEAMS = {
    # Atlantic Division
    "BOS": {
        "english": "Boston Celtics",
        "russian_full": "Бостон Селтикс",
        "russian_short": "Бостон",
        "keywords": ["Селтикс", "Celtics", "Boston", "Бостон"]
    },
    "BKN": {
        "english": "Brooklyn Nets",
        "russian_full": "Бруклин Нетс",
        "russian_short": "Бруклин",
        "keywords": ["Нетс", "Nets", "Brooklyn", "Бруклин"]
    },
    "NYK": {
        "english": "New York Knicks",
        "russian_full": "Нью-Йорк Никс",
        "russian_short": "Нью-Йорк",
        "keywords": ["Никс", "Knicks", "New York", "Нью-Йорк", "Никс"]
    },
    "PHI": {
        "english": "Philadelphia 76ers",
        "russian_full": "Филадельфия Сиксерс",
        "russian_short": "Филадельфия",
        "keywords": ["Сиксерс", "76ers", "Sixers", "Philadelphia", "Филадельфия"]
    },
    "TOR": {
        "english": "Toronto Raptors",
        "russian_full": "Торонто Рэпторс",
        "russian_short": "Торонто",
        "keywords": ["Рэпторс", "Raptors", "Toronto", "Торонто"]
    },

    # Central Division
    "CHI": {
        "english": "Chicago Bulls",
        "russian_full": "Чикаго Буллз",
        "russian_short": "Чикаго",
        "keywords": ["Буллз", "Bulls", "Chicago", "Чикаго"]
    },
    "CLE": {
        "english": "Cleveland Cavaliers",
        "russian_full": "Кливленд Кавальерс",
        "russian_short": "Кливленд",
        "keywords": ["Кавальерс", "Кавс", "Cavaliers", "Cavs", "Cleveland", "Кливленд"]
    },
    "DET": {
        "english": "Detroit Pistons",
        "russian_full": "Детройт Пистонс",
        "russian_short": "Детройт",
        "keywords": ["Пистонс", "Pistons", "Detroit", "Детройт"]
    },
    "IND": {
        "english": "Indiana Pacers",
        "russian_full": "Индиана Пэйсерс",
        "russian_short": "Индиана",
        "keywords": ["Пэйсерс", "Pacers", "Indiana", "Индиана"]
    },
    "MIL": {
        "english": "Milwaukee Bucks",
        "russian_full": "Милуоки Бакс",
        "russian_short": "Милуоки",
        "keywords": ["Бакс", "Bucks", "Milwaukee", "Милуоки"]
    },

    # Southeast Division
    "ATL": {
        "english": "Atlanta Hawks",
        "russian_full": "Атланта Хоукс",
        "russian_short": "Атланта",
        "keywords": ["Хоукс", "Hawks", "Atlanta", "Атланта"]
    },
    "CHA": {
        "english": "Charlotte Hornets",
        "russian_full": "Шарлотт Хорнетс",
        "russian_short": "Шарлотт",
        "keywords": ["Хорнетс", "Hornets", "Charlotte", "Шарлотт"]
    },
    "MIA": {
        "english": "Miami Heat",
        "russian_full": "Майами Хит",
        "russian_short": "Майами",
        "keywords": ["Хит", "Heat", "Miami", "Майами"]
    },
    "ORL": {
        "english": "Orlando Magic",
        "russian_full": "Орландо Мэджик",
        "russian_short": "Орландо",
        "keywords": ["Мэджик", "Magic", "Orlando", "Орландо"]
    },
    "WAS": {
        "english": "Washington Wizards",
        "russian_full": "Вашингтон Уизардс",
        "russian_short": "Вашингтон",
        "keywords": ["Уизардс", "Wizards", "Washington", "Вашингтон"]
    },

    # Northwest Division
    "DEN": {
        "english": "Denver Nuggets",
        "russian_full": "Денвер Наггетс",
        "russian_short": "Денвер",
        "keywords": ["Наггетс", "Nuggets", "Denver", "Денвер"]
    },
    "MIN": {
        "english": "Minnesota Timberwolves",
        "russian_full": "Миннесота Тимбервулвз",
        "russian_short": "Миннесота",
        "keywords": ["Тимбервулвз", "Timberwolves", "Wolves", "Minnesota", "Миннесота"]
    },
    "OKC": {
        "english": "Oklahoma City Thunder",
        "russian_full": "Оклахома-Сити Тандер",
        "russian_short": "Оклахома",
        "keywords": ["Тандер", "Thunder", "Oklahoma", "Оклахома", "OKC"]
    },
    "POR": {
        "english": "Portland Trail Blazers",
        "russian_full": "Портленд Трэйл Блэйзерс",
        "russian_short": "Портленд",
        "keywords": ["Блэйзерс", "Blazers", "Trail Blazers", "Portland", "Портленд"]
    },
    "UTA": {
        "english": "Utah Jazz",
        "russian_full": "Юта Джаз",
        "russian_short": "Юта",
        "keywords": ["Джаз", "Jazz", "Utah", "Юта"]
    },

    # Pacific Division
    "GSW": {
        "english": "Golden State Warriors",
        "russian_full": "Голден Стэйт Уорриорз",
        "russian_short": "Голден Стэйт",
        "keywords": ["Уорриорз", "Warriors", "Golden State", "Голден Стэйт", "GSW"]
    },
    "LAC": {
        "english": "Los Angeles Clippers",
        "russian_full": "Лос-Анджелес Клипперс",
        "russian_short": "Клипперс",
        "keywords": ["Клипперс", "Clippers", "LA Clippers", "Лос-Анджелес Клипперс"]
    },
    "LAL": {
        "english": "Los Angeles Lakers",
        "russian_full": "Лос-Анджелес Лейкерс",
        "russian_short": "Лейкерс",
        "keywords": ["Лейкерс", "Lakers", "LA Lakers", "Лос-Анджелес Лейкерс"]
    },
    "PHX": {
        "english": "Phoenix Suns",
        "russian_full": "Финикс Санз",
        "russian_short": "Финикс",
        "keywords": ["Санз", "Suns", "Phoenix", "Финикс"]
    },
    "SAC": {
        "english": "Sacramento Kings",
        "russian_full": "Сакраменто Кингз",
        "russian_short": "Сакраменто",
        "keywords": ["Кингз", "Kings", "Sacramento", "Сакраменто"]
    },

    # Southwest Division
    "DAL": {
        "english": "Dallas Mavericks",
        "russian_full": "Даллас Маверикс",
        "russian_short": "Даллас",
        "keywords": ["Маверикс", "Mavericks", "Mavs", "Dallas", "Даллас"]
    },
    "HOU": {
        "english": "Houston Rockets",
        "russian_full": "Хьюстон Рокетс",
        "russian_short": "Хьюстон",
        "keywords": ["Рокетс", "Rockets", "Houston", "Хьюстон"]
    },
    "MEM": {
        "english": "Memphis Grizzlies",
        "russian_full": "Мемфис Гриззлис",
        "russian_short": "Мемфис",
        "keywords": ["Гриззлис", "Grizzlies", "Memphis", "Мемфис"]
    },
    "NOP": {
        "english": "New Orleans Pelicans",
        "russian_full": "Нью-Орлеан Пеликанс",
        "russian_short": "Нью-Орлеан",
        "keywords": ["Пеликанс", "Pelicans", "New Orleans", "Нью-Орлеан"]
    },
    "SAS": {
        "english": "San Antonio Spurs",
        "russian_full": "Сан-Антонио Спёрс",
        "russian_short": "Сан-Антонио",
        "keywords": ["Спёрс", "Сперс", "Spurs", "San Antonio", "Сан-Антонио"]
    },
}

# Алиасы для аббревиатур (некоторые источники используют разные)
ABBREV_ALIASES = {
    "PHO": "PHX",  # Phoenix
    "BRK": "BKN",  # Brooklyn
    "CHO": "CHA",  # Charlotte
    "NOR": "NOP",  # New Orleans
    "SAN": "SAS",  # San Antonio
    "GS": "GSW",   # Golden State
    "NY": "NYK",   # New York
    "NO": "NOP",   # New Orleans
    "SA": "SAS",   # San Antonio
    "LA": "LAL",   # Default to Lakers for "LA"
}


def normalize_abbrev(abbrev: str) -> str:
    """Нормализация аббревиатуры команды."""
    abbrev = abbrev.upper().strip()
    return ABBREV_ALIASES.get(abbrev, abbrev)


def get_team_keywords(abbrev: str) -> list:
    """Получить все ключевые слова для поиска команды."""
    abbrev = normalize_abbrev(abbrev)
    team = NBA_TEAMS.get(abbrev)
    if team:
        return team['keywords']
    return []


def get_team_name(abbrev: str, lang: str = 'russian_short') -> str:
    """Получить название команды по аббревиатуре."""
    abbrev = normalize_abbrev(abbrev)
    team = NBA_TEAMS.get(abbrev)
    if team:
        return team.get(lang, team.get('english', abbrev))
    return abbrev


def find_teams_in_text(text: str) -> list:
    """
    Найти все упоминания команд в тексте.
    Возвращает список аббревиатур найденных команд.
    """
    text_lower = text.lower()
    found_teams = []

    for abbrev, team_data in NBA_TEAMS.items():
        for keyword in team_data['keywords']:
            if keyword.lower() in text_lower:
                if abbrev not in found_teams:
                    found_teams.append(abbrev)
                break

    return found_teams


def search_news_by_team(abbrev: str, news_list: list) -> list:
    """
    Фильтрация новостей по команде.

    Args:
        abbrev: Аббревиатура команды (напр. 'LAL')
        news_list: Список новостей с полями 'title' и 'content'

    Returns:
        Отфильтрованный список новостей
    """
    keywords = get_team_keywords(abbrev)
    if not keywords:
        return []

    result = []
    for news in news_list:
        text = f"{news.get('title', '')} {news.get('content', '')}".lower()
        for keyword in keywords:
            if keyword.lower() in text:
                result.append(news)
                break

    return result


# Тест
if __name__ == "__main__":
    # Тест поиска команд в тексте
    test_texts = [
        "Лейкерс разгромили Торонто с разницей в 30 очков",
        "Kevin Durant and the Phoenix Suns defeated Boston Celtics",
        "Янис Адетокунбо может покинуть Милуоки Бакс",
        "49 очков Дончича и ЛеБрона помогли Лейкерс разгромить Торонто"
    ]

    print("=== Тест поиска команд ===\n")
    for text in test_texts:
        teams = find_teams_in_text(text)
        print(f"Текст: {text[:60]}...")
        print(f"Найдены команды: {teams}")
        print(f"Названия: {[get_team_name(t) for t in teams]}")
        print()
