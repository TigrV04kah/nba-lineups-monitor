"""
RotoWire Authenticated Scraper - парсинг лайнапов с авторизацией через Playwright.
Поддерживает данные на сегодня и завтра (требует подписки RotoWire).
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

# Playwright импортируется динамически чтобы не ломать приложение если не установлен
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

# Директория для хранения сессии браузера
USER_DATA_DIR = Path(__file__).parent / "browser_data"
ROTOWIRE_BASE_URL = "https://www.rotowire.com/basketball/nba-lineups.php"


def check_playwright_installed() -> bool:
    """Проверка установлен ли Playwright."""
    return PLAYWRIGHT_AVAILABLE


def get_rotowire_url(date: str = "today") -> str:
    """
    Получить URL для парсинга лайнапов.

    Args:
        date: "today" или "tomorrow"

    Returns:
        URL страницы с лайнапами
    """
    if date == "tomorrow":
        return f"{ROTOWIRE_BASE_URL}?date=tomorrow"
    return ROTOWIRE_BASE_URL


class RotoWireAuthScraper:
    """
    Класс для парсинга RotoWire с авторизацией через Playwright.
    Использует persistent context для сохранения сессии между запусками.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._is_initialized = False

    def init_browser(self, headless: bool = True) -> bool:
        """
        Инициализация браузера с persistent context.

        Args:
            headless: запускать в фоновом режиме (без окна)

        Returns:
            True если успешно
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright не установлен. Выполните:")
            print("  pip install playwright")
            print("  playwright install chromium")
            return False

        try:
            # Создаём директорию для данных браузера
            USER_DATA_DIR.mkdir(exist_ok=True)

            self.playwright = sync_playwright().start()

            # Используем persistent context - сохраняет cookies, localStorage и т.д.
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=headless,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Берём первую страницу или создаём новую
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()

            self._is_initialized = True
            print("[OK] Браузер инициализирован")
            return True

        except Exception as e:
            print(f"[ERROR] Ошибка инициализации браузера: {e}")
            return False

    def close(self):
        """Закрытие браузера и освобождение ресурсов."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        self._is_initialized = False
        print("[OK] Браузер закрыт")

    def is_logged_in(self) -> bool:
        """
        Проверка авторизован ли пользователь на RotoWire.

        Returns:
            True если авторизован
        """
        if not self._is_initialized:
            return False

        try:
            # Переходим на страницу RotoWire
            self.page.goto(ROTOWIRE_BASE_URL, wait_until="networkidle", timeout=30000)

            # Проверяем наличие элементов авторизованного пользователя
            # На RotoWire обычно есть кнопка "Log Out" или имя пользователя

            # Проверяем есть ли кнопка Login (значит не авторизован)
            login_btn = self.page.query_selector('a[href*="login"], .login-btn, [data-login]')
            if login_btn and login_btn.is_visible():
                # Проверяем текст кнопки
                text = login_btn.inner_text().lower()
                if 'log in' in text or 'login' in text or 'sign in' in text:
                    return False

            # Проверяем есть ли элементы авторизованного пользователя
            logout_btn = self.page.query_selector('a[href*="logout"], .logout-btn, [data-logout]')
            if logout_btn:
                return True

            # Дополнительная проверка - пробуем загрузить завтрашние данные
            self.page.goto(get_rotowire_url("tomorrow"), wait_until="networkidle", timeout=30000)

            # Если есть paywall или требование подписки - не авторизован
            paywall = self.page.query_selector('.paywall, .subscription-required, .premium-content')
            if paywall and paywall.is_visible():
                return False

            # Проверяем есть ли лайнапы на завтра
            lineups = self.page.query_selector_all('.lineup.is-nba')
            return len(lineups) > 0

        except Exception as e:
            print(f"[ERROR] Ошибка проверки авторизации: {e}")
            return False

    def login_interactive(self) -> bool:
        """
        Интерактивная авторизация - открывает браузер для ручного входа.
        Пользователь должен авторизоваться через Google вручную.

        Returns:
            True если авторизация успешна
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright не установлен")
            return False

        try:
            # Закрываем текущий контекст если есть
            if self.context:
                self.close()

            # Запускаем браузер в видимом режиме для авторизации
            print("\n" + "="*60)
            print("АВТОРИЗАЦИЯ НА ROTOWIRE")
            print("="*60)
            print("1. Откроется окно браузера")
            print("2. Авторизуйтесь через Google на сайте RotoWire")
            print("3. После успешного входа закройте браузер")
            print("="*60 + "\n")

            USER_DATA_DIR.mkdir(exist_ok=True)

            self.playwright = sync_playwright().start()

            # Запускаем в видимом режиме
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=False,  # Видимый режим!
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            self.page = self.context.new_page()

            # Переходим на страницу входа RotoWire
            self.page.goto("https://www.rotowire.com/users/login.php", wait_until="networkidle")

            print("[INFO] Авторизуйтесь в открывшемся окне браузера...")
            print("[INFO] После входа закройте браузер для продолжения")

            # Ждём пока пользователь закроет браузер
            try:
                self.context.pages[0].wait_for_event("close", timeout=300000)  # 5 минут
            except:
                pass

            # Закрываем контекст
            self.context.close()
            self.playwright.stop()

            # Переинициализируем в headless режиме
            self._is_initialized = False
            if self.init_browser(headless=True):
                # Проверяем успешность авторизации
                if self.is_logged_in():
                    print("[OK] Авторизация успешна! Сессия сохранена.")
                    return True
                else:
                    print("[WARNING] Авторизация не подтверждена. Попробуйте ещё раз.")
                    return False

            return False

        except Exception as e:
            print(f"[ERROR] Ошибка авторизации: {e}")
            return False

    def fetch_page_content(self, date: str = "today") -> str:
        """
        Загрузка HTML контента страницы с лайнапами.

        Args:
            date: "today" или "tomorrow"

        Returns:
            HTML контент страницы
        """
        if not self._is_initialized:
            if not self.init_browser(headless=True):
                return ""

        try:
            url = get_rotowire_url(date)
            print(f"[INFO] Загрузка {url}...")

            self.page.goto(url, wait_until="networkidle", timeout=30000)

            # Ждём загрузки лайнапов
            self.page.wait_for_selector('.lineup.is-nba', timeout=10000)

            return self.page.content()

        except Exception as e:
            print(f"[ERROR] Ошибка загрузки страницы: {e}")
            return ""

    def parse_lineups_from_html(self, html: str) -> list:
        """
        Парсинг лайнапов из HTML (использует существующую логику).

        Args:
            html: HTML контент страницы

        Returns:
            Список игр с составами
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        games = []

        game_containers = soup.find_all('div', class_='lineup')

        for container in game_containers:
            classes = container.get('class', [])
            if 'is-nba' not in classes:
                continue

            # Пропускаем рекламные блоки
            if container.find(class_='picks-logo') or container.find(class_='picks-headline'):
                continue

            if not container.find(class_='lineup__abbr'):
                continue

            game_data = self._parse_game_container(container)
            if game_data and game_data.get('away_team', {}).get('abbrev'):
                games.append(game_data)

        return games

    def _parse_game_container(self, container) -> dict:
        """Парсинг одного контейнера игры."""
        game = {
            'game_time': '',
            'away_team': {'abbrev': '', 'record': '', 'lineup': [], 'injuries': []},
            'home_team': {'abbrev': '', 'record': '', 'lineup': [], 'injuries': []}
        }

        # Время игры
        time_elem = container.find(class_='lineup__time')
        if time_elem:
            game['game_time'] = time_elem.get_text(strip=True)

        # Находим блоки команд
        team_boxes = container.find_all(class_='lineup__box')

        if len(team_boxes) >= 2:
            # Away team (первый блок)
            game['away_team'] = self._parse_team_box(team_boxes[0])
            # Home team (второй блок)
            game['home_team'] = self._parse_team_box(team_boxes[1])

        return game

    def _parse_team_box(self, box) -> dict:
        """Парсинг блока одной команды."""
        team = {
            'abbrev': '',
            'record': '',
            'lineup': [],
            'injuries': []
        }

        # Аббревиатура команды
        abbrev_elem = box.find(class_='lineup__abbr')
        if abbrev_elem:
            team['abbrev'] = abbrev_elem.get_text(strip=True)

        # Рекорд команды
        record_elem = box.find(class_='lineup__record')
        if record_elem:
            team['record'] = record_elem.get_text(strip=True)

        # Игроки
        player_items = box.find_all('li')
        for item in player_items:
            player = self._parse_player_item(item)
            if player:
                team['lineup'].append(player)
                # Если игрок OUT или DOUBTFUL - добавляем в injuries
                if player.get('status') in ['out', 'doubtful']:
                    team['injuries'].append(player['name'])

        return team

    def _parse_player_item(self, item) -> dict:
        """Парсинг элемента игрока."""
        player = {}

        # Имя игрока
        name_elem = item.find('a')
        if name_elem:
            player['name'] = name_elem.get_text(strip=True)
        else:
            return None

        # Позиция
        pos_elem = item.find(class_='lineup__pos')
        if pos_elem:
            player['position'] = pos_elem.get_text(strip=True)

        # Статус (injury status)
        status = 'active'
        status_elem = item.find(class_='lineup__inj')
        if status_elem:
            status_text = status_elem.get_text(strip=True).lower()
            if 'out' in status_text:
                status = 'out'
            elif 'doubtful' in status_text or 'dtd' in status_text:
                status = 'doubtful'
            elif 'questionable' in status_text or 'gtd' in status_text:
                status = 'questionable'
            elif 'probable' in status_text:
                status = 'probable'

        player['status'] = status

        return player

    def get_lineups(self, date: str = "today") -> list:
        """
        Получение лайнапов на указанную дату.

        Args:
            date: "today" или "tomorrow"

        Returns:
            Список игр с составами
        """
        html = self.fetch_page_content(date)
        return self.parse_lineups_from_html(html)


# Глобальный экземпляр скрапера (singleton)
_scraper_instance = None


def get_scraper() -> RotoWireAuthScraper:
    """Получение глобального экземпляра скрапера."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = RotoWireAuthScraper()
    return _scraper_instance


def fetch_lineups_with_auth(date: str = "today") -> list:
    """
    Простая функция для получения лайнапов с авторизацией.

    Args:
        date: "today" или "tomorrow"

    Returns:
        Список игр с составами
    """
    scraper = get_scraper()

    if not scraper._is_initialized:
        if not scraper.init_browser(headless=True):
            return []

    return scraper.get_lineups(date)


def run_login():
    """Запуск интерактивной авторизации."""
    scraper = get_scraper()
    return scraper.login_interactive()


def check_auth_status() -> bool:
    """Проверка статуса авторизации."""
    scraper = get_scraper()
    if not scraper._is_initialized:
        if not scraper.init_browser(headless=True):
            return False
    return scraper.is_logged_in()


# CLI для тестирования
if __name__ == "__main__":
    import sys

    print("RotoWire Auth Scraper")
    print("="*40)

    if not PLAYWRIGHT_AVAILABLE:
        print("\n[ERROR] Playwright не установлен!")
        print("\nДля установки выполните:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "login":
            # Запуск авторизации
            run_login()

        elif command == "check":
            # Проверка авторизации
            if check_auth_status():
                print("[OK] Авторизован на RotoWire")
            else:
                print("[NO] Не авторизован. Запустите: python rotowire_auth.py login")

        elif command == "today":
            # Парсинг на сегодня
            games = fetch_lineups_with_auth("today")
            print(f"\nНайдено игр на сегодня: {len(games)}")
            for g in games:
                print(f"  {g['away_team']['abbrev']} @ {g['home_team']['abbrev']} - {g['game_time']}")

        elif command == "tomorrow":
            # Парсинг на завтра
            games = fetch_lineups_with_auth("tomorrow")
            print(f"\nНайдено игр на завтра: {len(games)}")
            for g in games:
                print(f"  {g['away_team']['abbrev']} @ {g['home_team']['abbrev']} - {g['game_time']}")

        else:
            print(f"Неизвестная команда: {command}")
            print("\nДоступные команды:")
            print("  login    - авторизация на RotoWire")
            print("  check    - проверка статуса авторизации")
            print("  today    - показать лайнапы на сегодня")
            print("  tomorrow - показать лайнапы на завтра")

    else:
        print("\nИспользование:")
        print("  python rotowire_auth.py login    - авторизация")
        print("  python rotowire_auth.py check    - проверка авторизации")
        print("  python rotowire_auth.py today    - лайнапы на сегодня")
        print("  python rotowire_auth.py tomorrow - лайнапы на завтра")
