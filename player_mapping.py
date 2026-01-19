"""
Маппинг имён игроков NBA: английские <-> русские
Используется для поиска новостей по игроку
"""

# Топ игроки NBA с русскими именами
# Формат: английское имя -> список вариантов русского написания
PLAYER_NAMES = {
    # Superstars
    "LeBron James": ["Леброн Джеймс", "Леброн", "Джеймс"],
    "Stephen Curry": ["Стефен Карри", "Стеф Карри", "Карри"],
    "Kevin Durant": ["Кевин Дюрант", "Дюрант"],
    "Giannis Antetokounmpo": ["Яннис Адетокунбо", "Адетокунбо", "Яннис"],
    "Nikola Jokic": ["Никола Йокич", "Йокич"],
    "Luka Doncic": ["Лука Дончич", "Дончич"],
    "Joel Embiid": ["Джоэл Эмбиид", "Эмбиид"],
    "Jayson Tatum": ["Джейсон Тейтум", "Тейтум"],
    "Jimmy Butler": ["Джимми Батлер", "Батлер"],
    "Anthony Davis": ["Энтони Дэвис", "Дэвис"],
    "Damian Lillard": ["Дэмиан Лиллард", "Лиллард"],
    "Kawhi Leonard": ["Кавай Ленард", "Ленард"],
    "Paul George": ["Пол Джордж"],
    "Devin Booker": ["Девин Букер", "Букер"],
    "Kyrie Irving": ["Кайри Ирвинг", "Ирвинг"],
    "Ja Morant": ["Джа Морант", "Морант"],
    "Trae Young": ["Трэй Янг", "Янг"],
    "Donovan Mitchell": ["Донован Митчелл", "Митчелл"],
    "Zion Williamson": ["Зайон Уильямсон", "Уильямсон"],
    "Anthony Edwards": ["Энтони Эдвардс", "Эдвардс"],
    "Victor Wembanyama": ["Виктор Вембаньяма", "Вембаньяма"],
    "Shai Gilgeous-Alexander": ["Шэй Гилджес-Александер", "Гилджес-Александер", "SGA"],
    "Tyrese Haliburton": ["Тайриз Халибёртон", "Халибёртон"],
    "De'Aaron Fox": ["Деаарон Фокс", "Фокс"],
    "Paolo Banchero": ["Паоло Банкеро", "Банкеро"],
    "Chet Holmgren": ["Чет Холмгрен", "Холмгрен"],

    # All-Stars & Key Players
    "Jaylen Brown": ["Джейлен Браун", "Браун"],
    "Bam Adebayo": ["Бэм Адебайо", "Адебайо"],
    "Pascal Siakam": ["Паскаль Сиакам", "Сиакам"],
    "Domantas Sabonis": ["Домантас Сабонис", "Сабонис"],
    "Karl-Anthony Towns": ["Карл-Энтони Таунс", "Таунс"],
    "Rudy Gobert": ["Руди Гобер", "Гобер"],
    "Jalen Brunson": ["Джален Брансон", "Брансон"],
    "Julius Randle": ["Джулиус Рэндл", "Рэндл"],
    "Draymond Green": ["Дрэймонд Грин"],
    "Klay Thompson": ["Клэй Томпсон", "Томпсон"],
    "Chris Paul": ["Крис Пол"],
    "Russell Westbrook": ["Расселл Уэстбрук", "Уэстбрук"],
    "James Harden": ["Джеймс Харден", "Харден"],
    "Bradley Beal": ["Брэдли Бил", "Бил"],
    "DeMar DeRozan": ["Демар Дерозан", "Дерозан"],
    "Zach LaVine": ["Зак Лавин", "Лавин"],
    "LaMelo Ball": ["Ламело Болл", "Болл"],
    "Brandon Ingram": ["Брэндон Ингрэм", "Ингрэм"],
    "CJ McCollum": ["Си Джей Макколлум", "Макколлум"],
    "Jamal Murray": ["Джамал Мюррэй", "Мюррэй"],
    "Michael Porter Jr.": ["Майкл Портер", "Портер"],
    "Aaron Gordon": ["Аарон Гордон", "Гордон"],
    "Scottie Barnes": ["Скотти Барнс", "Барнс"],
    "Evan Mobley": ["Эван Мобли", "Мобли"],
    "Jarrett Allen": ["Джаррет Аллен", "Аллен"],
    "Mikal Bridges": ["Микал Бриджес", "Бриджес"],
    "OG Anunoby": ["Оджей Ануноби", "Ануноби"],
    "Jrue Holiday": ["Джру Холидей", "Холидей"],
    "Khris Middleton": ["Крис Миддлтон", "Миддлтон"],
    "Brook Lopez": ["Брук Лопес", "Лопес"],
    "Tyrese Maxey": ["Тайриз Макси", "Макси"],
    "Desmond Bane": ["Десмонд Бэйн", "Бэйн"],
    "Jaren Jackson Jr.": ["Джарен Джексон", "Джексон"],
    "Marcus Smart": ["Маркус Смарт", "Смарт"],
    "Fred VanVleet": ["Фред Ванвлит", "Ванвлит"],
    "Alperen Sengun": ["Альперен Шенгюн", "Шенгюн"],
    "Jalen Green": ["Джален Грин"],
    "Franz Wagner": ["Франц Вагнер", "Вагнер"],
    "Cade Cunningham": ["Кейд Каннингем", "Каннингем"],
    "Anfernee Simons": ["Анферни Саймонс", "Саймонс"],
    "Derrick White": ["Деррик Уайт", "Уайт"],
    "Al Horford": ["Эл Хорфорд", "Хорфорд"],
    "Kristaps Porzingis": ["Кристапс Порзингис", "Порзингис"],
    "Austin Reaves": ["Остин Ривз", "Ривз"],
    "Rui Hachimura": ["Руи Хатимура", "Хатимура"],
    "D'Angelo Russell": ["Ди'Анджело Расселл", "Расселл"],

    # Rising Stars & Role Players
    "Derrick Rose": ["Деррик Роуз", "Роуз"],
    "Kyle Lowry": ["Кайл Лаури", "Лаури"],
    "Spencer Dinwiddie": ["Спенсер Динуидди", "Динуидди"],
    "Terry Rozier": ["Терри Розир", "Розир"],
    "Malcolm Brogdon": ["Малкольм Брогдон", "Брогдон"],
    "Tobias Harris": ["Тобайас Харрис", "Харрис"],
    "Kelly Oubre Jr.": ["Келли Убре", "Убре"],
    "Josh Hart": ["Джош Харт", "Харт"],
    "Malik Monk": ["Малик Монк", "Монк"],
    "Buddy Hield": ["Бадди Хилд", "Хилд"],
    "Bogdan Bogdanovic": ["Богдан Богданович", "Богданович"],
    "Bojan Bogdanovic": ["Боян Богданович"],
    "Nikola Vucevic": ["Никола Вучевич", "Вучевич"],
    "Jonas Valanciunas": ["Йонас Валанчюнас", "Валанчюнас"],
    "Clint Capela": ["Клинт Капела", "Капела"],
    "Steven Adams": ["Стивен Адамс", "Адамс"],
    "Myles Turner": ["Майлс Тёрнер", "Тёрнер"],
    "Dejounte Murray": ["Дежонте Мюррей"],
    "John Collins": ["Джон Коллинз", "Коллинз"],
    "Lauri Markkanen": ["Лаури Маркканен", "Маркканен"],
    "Jordan Clarkson": ["Джордан Кларксон", "Кларксон"],
    "Collin Sexton": ["Коллин Секстон", "Секстон"],
    "Keldon Johnson": ["Келдон Джонсон"],
    "Josh Giddey": ["Джош Гидди", "Гидди"],
    "Immanuel Quickley": ["Иммануэль Квикли", "Квикли"],
    "Ayo Dosunmu": ["Айо Досунму", "Досунму"],
    "Herb Jones": ["Херб Джонс"],
    "Andrew Wiggins": ["Эндрю Уиггинс", "Уиггинс"],
    "Jonathan Kuminga": ["Джонатан Куминга", "Куминга"],
    "Jordan Poole": ["Джордан Пул", "Пул"],
    "Tyler Herro": ["Тайлер Хирро", "Хирро"],
    "Kyle Kuzma": ["Кайл Кузма", "Кузма"],
    "Coby White": ["Коби Уайт"],
    "Alex Caruso": ["Алекс Карузо", "Карузо"],
    "Dillon Brooks": ["Диллон Брукс", "Брукс"],
    "Lu Dort": ["Лугенц Дорт", "Дорт"],
    "Isaiah Stewart": ["Исайя Стюарт", "Стюарт"],
    "Jaden Ivey": ["Джейден Айви", "Айви"],
    "Keegan Murray": ["Киган Мюррей"],
    "Amen Thompson": ["Эймен Томпсон"],
    "Ausar Thompson": ["Осар Томпсон"],
    "Scoot Henderson": ["Скут Хендерсон", "Хендерсон"],
    "Jaime Jaquez Jr.": ["Хайме Хакес", "Хакес"],
    "Brandin Podziemski": ["Брэндин Подземски", "Подземски"],
}

# Создаём обратный индекс: русское имя -> английское
RUSSIAN_TO_ENGLISH = {}
for eng_name, rus_variants in PLAYER_NAMES.items():
    for rus_name in rus_variants:
        RUSSIAN_TO_ENGLISH[rus_name.lower()] = eng_name


def get_player_keywords(english_name: str) -> list:
    """
    Получить ключевые слова для поиска игрока (русские варианты имени).

    Args:
        english_name: Английское имя игрока

    Returns:
        Список русских вариантов имени для поиска
    """
    # Пробуем точное совпадение
    if english_name in PLAYER_NAMES:
        return PLAYER_NAMES[english_name]

    # Пробуем найти по фамилии
    last_name = english_name.split()[-1] if ' ' in english_name else english_name
    for eng_name, rus_variants in PLAYER_NAMES.items():
        if last_name.lower() in eng_name.lower():
            return rus_variants

    # Не нашли - возвращаем оригинальное имя и фамилию
    parts = english_name.split()
    if len(parts) >= 2:
        return [english_name, parts[-1]]  # Полное имя и фамилия
    return [english_name]


def find_player_in_text(english_name: str, text: str) -> bool:
    """
    Проверить, упоминается ли игрок в тексте.

    Args:
        english_name: Английское имя игрока
        text: Текст для поиска

    Returns:
        True если игрок найден
    """
    keywords = get_player_keywords(english_name)
    text_lower = text.lower()

    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True

    # Также проверяем английское имя и фамилию
    if english_name.lower() in text_lower:
        return True

    parts = english_name.split()
    if len(parts) >= 2:
        last_name = parts[-1].lower()
        if last_name in text_lower and len(last_name) > 3:  # Избегаем коротких фамилий типа "Fox"
            return True

    return False


def get_english_name(russian_name: str) -> str:
    """
    Получить английское имя по русскому.

    Args:
        russian_name: Русское имя игрока

    Returns:
        Английское имя или оригинальное если не найдено
    """
    return RUSSIAN_TO_ENGLISH.get(russian_name.lower(), russian_name)


# Тест
if __name__ == "__main__":
    test_texts = [
        "Леброн Джеймс набрал 30 очков в матче с Торонто",
        "Дончич и Леброн показали отличную игру",
        "Виктор Вембаньяма стал лучшим блокирующим",
        "LeBron James scored 25 points",
        "Карри забил решающий трёхочковый"
    ]

    test_players = ["LeBron James", "Luka Doncic", "Victor Wembanyama", "Stephen Curry"]

    print("=== Test player search ===\n")
    for text in test_texts:
        print(f"Text: {text[:60]}...")
        for player in test_players:
            found = find_player_in_text(player, text)
            if found:
                print(f"  [OK] Found: {player}")
        print()

    print("=== Тест ключевых слов ===\n")
    for player in ["LeBron James", "Stephen Curry", "Unknown Player"]:
        keywords = get_player_keywords(player)
        print(f"{player}: {keywords}")
