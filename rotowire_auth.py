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

# Путь к профилю Chrome пользователя (для авторизации через Google)
def get_chrome_user_data_dir():
    """Получение пути к профилю Chrome пользователя."""
    import os
    # Стандартный путь для Windows
    chrome_path = Path(os.environ.get('LOCALAPPDATA', '')) / "Google" / "Chrome" / "User Data"
    if chrome_path.exists():
        return str(chrome_path)
    return None


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
            print("[ERROR] Playwright not installed. Run:")
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
            print("[OK] Browser initialized")
            return True

        except Exception as e:
            print(f"[ERROR] Browser init error: {e}")
            return False

    def close(self):
        """Закрытие браузера и освобождение ресурсов."""
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
        self._is_initialized = False
        print("[OK] Browser closed")

    def is_logged_in(self) -> bool:
        """
        Check if user is logged in to RotoWire.

        Returns:
            True if logged in
        """
        if not self._is_initialized:
            return False

        try:
            # Navigate to RotoWire page (use domcontentloaded - more reliable than networkidle)
            self.page.goto(ROTOWIRE_BASE_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait a bit for dynamic content
            self.page.wait_for_timeout(2000)

            # Check for Login button (means NOT logged in)
            login_btn = self.page.query_selector('a[href*="login"], .login-btn, [data-login]')
            if login_btn and login_btn.is_visible():
                text = login_btn.inner_text().lower()
                if 'log in' in text or 'login' in text or 'sign in' in text:
                    return False

            # Check for logout elements (means logged in)
            logout_btn = self.page.query_selector('a[href*="logout"], .logout-btn, [data-logout]')
            if logout_btn:
                return True

            # Additional check - try to load tomorrow's data
            self.page.goto(get_rotowire_url("tomorrow"), wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(2000)

            # If paywall exists - not logged in
            paywall = self.page.query_selector('.paywall, .subscription-required, .premium-content')
            if paywall and paywall.is_visible():
                return False

            # Check if there are lineups for tomorrow
            lineups = self.page.query_selector_all('.lineup.is-nba')
            return len(lineups) > 0

        except Exception as e:
            print(f"[ERROR] Auth check error: {e}")
            return False

    def login_interactive(self, use_real_chrome: bool = True) -> bool:
        """
        Интерактивная авторизация - открывает браузер для ручного входа.

        Args:
            use_real_chrome: использовать реальный Chrome с профилем пользователя
                            (обходит блокировку Google OAuth)

        Returns:
            True если авторизация успешна
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright not installed")
            return False

        try:
            # Закрываем текущий контекст если есть
            if self.context:
                self.close()

            print("\n" + "="*60)
            print("ROTOWIRE LOGIN")
            print("="*60)

            chrome_user_data = get_chrome_user_data_dir()

            print("1. Browser will open")
            print("2. Login to RotoWire via Google")
            print("3. Close browser after login")
            print("="*60 + "\n")

            self.playwright = sync_playwright().start()

            # Используем отдельный профиль но с реальным Chrome (обходит блокировку Google)
            USER_DATA_DIR.mkdir(exist_ok=True)
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                channel="chrome",  # Реальный Chrome вместо Chromium
                headless=False,
                viewport={"width": 1280, "height": 800},
            )

            self.page = self.context.new_page()

            # Navigate to RotoWire login page
            self.page.goto("https://www.rotowire.com/users/login.php", wait_until="domcontentloaded")

            print("[INFO] Login in the browser window...")
            print("[INFO] Close browser after login to continue")

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
                    print("[OK] Login successful! Session saved.")
                    return True
                else:
                    print("[WARNING] Login not confirmed. Try again.")
                    return False

            return False

        except Exception as e:
            print(f"[ERROR] Login error: {e}")
            return False

    def fetch_page_content(self, date: str = "today") -> str:
        """
        Load HTML content of lineups page.

        Args:
            date: "today" or "tomorrow"

        Returns:
            HTML content of the page
        """
        if not self._is_initialized:
            if not self.init_browser(headless=True):
                return ""

        try:
            url = get_rotowire_url(date)
            print(f"[INFO] Loading {url}...")

            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for lineups to load
            self.page.wait_for_selector('.lineup.is-nba', timeout=15000)

            return self.page.content()

        except Exception as e:
            print(f"[ERROR] Page load error: {e}")
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
        """Parse a single game container."""
        game = {
            'game_time': '',
            'away_team': {'abbrev': '', 'record': '', 'lineup': [], 'injuries': []},
            'home_team': {'abbrev': '', 'record': '', 'lineup': [], 'injuries': []}
        }

        # Game time
        time_elem = container.find(class_='lineup__time')
        if time_elem:
            game['game_time'] = time_elem.get_text(strip=True)

        # Find team elements - new structure uses is-visit and is-home classes
        visit_team = container.find(class_='is-visit')
        home_team = container.find(class_='is-home')

        # Get team abbreviations
        if visit_team:
            abbr = visit_team.find(class_='lineup__abbr')
            if abbr:
                game['away_team']['abbrev'] = abbr.get_text(strip=True)

        if home_team:
            abbr = home_team.find(class_='lineup__abbr')
            if abbr:
                game['home_team']['abbrev'] = abbr.get_text(strip=True)

        # Get team records from matchup section
        matchup = container.find(class_='lineup__matchup')
        if matchup:
            visit_record = matchup.find(class_='is-visit')
            home_record = matchup.find(class_='is-home')
            if visit_record:
                text = visit_record.get_text(strip=True)
                # Extract record from text like "Cavaliers(25-20)"
                if '(' in text and ')' in text:
                    game['away_team']['record'] = text[text.find('(')+1:text.find(')')]
            if home_record:
                text = home_record.get_text(strip=True)
                if '(' in text and ')' in text:
                    game['home_team']['record'] = text[text.find('(')+1:text.find(')')]

        # Find player lists - typically 2 lists (away, home)
        player_lists = container.find_all('ul', class_='lineup__list')
        if len(player_lists) >= 2:
            game['away_team']['lineup'] = self._parse_player_list(player_lists[0])
            game['home_team']['lineup'] = self._parse_player_list(player_lists[1])

            # Update injuries
            for player in game['away_team']['lineup']:
                if player.get('status') in ['out', 'doubtful']:
                    game['away_team']['injuries'].append(player['name'])
            for player in game['home_team']['lineup']:
                if player.get('status') in ['out', 'doubtful']:
                    game['home_team']['injuries'].append(player['name'])

        return game

    def _parse_player_list(self, player_list) -> list:
        """Parse a player list element."""
        players = []
        items = player_list.find_all('li')
        for item in items:
            player = self._parse_player_item(item)
            if player:
                players.append(player)
        return players

    def _parse_team_box(self, box) -> dict:
        """Parse a single team box (legacy method for compatibility)."""
        team = {
            'abbrev': '',
            'record': '',
            'lineup': [],
            'injuries': []
        }

        abbrev_elem = box.find(class_='lineup__abbr')
        if abbrev_elem:
            team['abbrev'] = abbrev_elem.get_text(strip=True)

        record_elem = box.find(class_='lineup__record')
        if record_elem:
            team['record'] = record_elem.get_text(strip=True)

        player_items = box.find_all('li')
        for item in player_items:
            player = self._parse_player_item(item)
            if player:
                team['lineup'].append(player)
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
        print("\n[ERROR] Playwright not installed!")
        print("\nTo install run:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "login":
            run_login()

        elif command == "check":
            if check_auth_status():
                print("[OK] Logged in to RotoWire")
            else:
                print("[NO] Not logged in. Run: python rotowire_auth.py login")

        elif command == "today":
            games = fetch_lineups_with_auth("today")
            print(f"\nFound {len(games)} games today")
            for g in games:
                print(f"  {g['away_team']['abbrev']} @ {g['home_team']['abbrev']} - {g['game_time']}")

        elif command == "tomorrow":
            games = fetch_lineups_with_auth("tomorrow")
            print(f"\nFound {len(games)} games tomorrow")
            for g in games:
                print(f"  {g['away_team']['abbrev']} @ {g['home_team']['abbrev']} - {g['game_time']}")

        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  login    - login to RotoWire")
            print("  check    - check auth status")
            print("  today    - show today's lineups")
            print("  tomorrow - show tomorrow's lineups")

    else:
        print("\nUsage:")
        print("  python rotowire_auth.py login    - login")
        print("  python rotowire_auth.py check    - check auth")
        print("  python rotowire_auth.py today    - today's lineups")
        print("  python rotowire_auth.py tomorrow - tomorrow's lineups")
