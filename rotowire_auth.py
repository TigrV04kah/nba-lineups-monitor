"""
RotoWire Authenticated Scraper - парсинг лайнапов с авторизацией.
Использует requests для парсинга (thread-safe), Playwright только для логина.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
import requests
import urllib3

# Suppress SSL warnings (RotoWire works fine without cert verification)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Playwright импортируется динамически
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

# Файлы для хранения данных
DATA_DIR = Path(__file__).parent / "browser_data"
COOKIES_FILE = DATA_DIR / "cookies.json"
ROTOWIRE_BASE_URL = "https://www.rotowire.com/basketball/nba-lineups.php"


def check_playwright_installed() -> bool:
    """Проверка установлен ли Playwright."""
    return PLAYWRIGHT_AVAILABLE


def get_rotowire_url(date: str = "today") -> str:
    """Get URL for lineups page."""
    if date == "tomorrow":
        return f"{ROTOWIRE_BASE_URL}?date=tomorrow"
    return ROTOWIRE_BASE_URL


def save_cookies(cookies: list):
    """Save cookies to file."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies, f)
    print(f"[OK] Cookies saved ({len(cookies)} cookies)")


def load_cookies() -> dict:
    """Load auth cookies from file.
    Only PHPSESSID is needed for authentication (other cookies cause 520 errors).
    """
    if not COOKIES_FILE.exists():
        return {}
    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies_list = json.load(f)

        # Only need PHPSESSID for RotoWire auth
        for c in cookies_list:
            if c.get('name') == 'PHPSESSID' and 'rotowire' in c.get('domain', '').lower():
                return {'PHPSESSID': c['value']}

        return {}
    except Exception as e:
        print(f"[WARNING] Failed to load cookies: {e}")
        return {}


def run_login() -> bool:
    """
    Interactive login - opens browser for manual Google auth.
    Saves cookies after successful login.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[ERROR] Playwright not installed")
        print("  pip install playwright")
        print("  playwright install chromium")
        return False

    try:
        print("\n" + "="*60)
        print("ROTOWIRE LOGIN")
        print("="*60)
        print("1. Browser will open")
        print("2. Login to RotoWire via Google")
        print("3. After login, wait for redirect to main page")
        print("4. Close browser window")
        print("="*60 + "\n")

        DATA_DIR.mkdir(exist_ok=True)

        playwright = sync_playwright().start()

        # Use Chrome with separate profile
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(DATA_DIR),
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        page = context.new_page()
        page.goto("https://www.rotowire.com/users/login.php", wait_until="domcontentloaded")

        print("[INFO] Login in the browser window...")
        print("[INFO] Close browser after successful login")

        # Wait for user to close browser
        try:
            context.pages[0].wait_for_event("close", timeout=300000)
        except:
            pass

        # Get cookies before closing
        cookies = context.cookies()
        save_cookies(cookies)

        context.close()
        playwright.stop()

        # Verify login worked
        if check_auth_status():
            print("[OK] Login successful!")
            return True
        else:
            print("[WARNING] Login may not have completed. Try again.")
            return False

    except Exception as e:
        print(f"[ERROR] Login error: {e}")
        return False


def check_auth_status() -> bool:
    """Check if we have valid auth cookies."""
    cookies = load_cookies()
    if not cookies:
        return False

    # Try to access tomorrow's page (requires subscription)
    try:
        response = requests.get(
            get_rotowire_url("tomorrow"),
            cookies=cookies,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=30,
            verify=False
        )

        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        lineups = [l for l in soup.find_all('div', class_='lineup') if 'is-nba' in l.get('class', [])]
        return len(lineups) > 0
    except Exception as e:
        print(f"[ERROR] Auth check failed: {e}")
        return False


def fetch_lineups_with_auth(date: str = "today") -> list:
    """
    Fetch lineups using saved cookies (thread-safe).

    Args:
        date: "today" or "tomorrow"

    Returns:
        List of games with lineups
    """
    cookies = load_cookies()

    try:
        url = get_rotowire_url(date)
        print(f"[INFO] Loading {url}...")

        # Use same headers as original scraper (works!)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            timeout=30,
            verify=False
        )

        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code}")
            return []

        return parse_lineups_from_html(response.text)

    except Exception as e:
        print(f"[ERROR] Fetch error: {e}")
        return []


def parse_lineups_from_html(html: str) -> list:
    """Parse lineups from HTML."""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    games = []

    game_containers = soup.find_all('div', class_='lineup')

    for container in game_containers:
        classes = container.get('class', [])
        if 'is-nba' not in classes:
            continue

        # Skip ads
        if container.find(class_='picks-logo') or container.find(class_='picks-headline'):
            continue

        if not container.find(class_='lineup__abbr'):
            continue

        game_data = _parse_game_container(container)
        if game_data and game_data.get('away_team', {}).get('abbrev'):
            games.append(game_data)

    return games


def _parse_game_container(container) -> dict:
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

    # Find team elements
    visit_team = container.find(class_='is-visit')
    home_team = container.find(class_='is-home')

    if visit_team:
        abbr = visit_team.find(class_='lineup__abbr')
        if abbr:
            game['away_team']['abbrev'] = abbr.get_text(strip=True)

    if home_team:
        abbr = home_team.find(class_='lineup__abbr')
        if abbr:
            game['home_team']['abbrev'] = abbr.get_text(strip=True)

    # Get team records
    matchup = container.find(class_='lineup__matchup')
    if matchup:
        visit_record = matchup.find(class_='is-visit')
        home_record = matchup.find(class_='is-home')
        if visit_record:
            text = visit_record.get_text(strip=True)
            if '(' in text and ')' in text:
                game['away_team']['record'] = text[text.find('(')+1:text.find(')')]
        if home_record:
            text = home_record.get_text(strip=True)
            if '(' in text and ')' in text:
                game['home_team']['record'] = text[text.find('(')+1:text.find(')')]

    # Find player lists
    player_lists = container.find_all('ul', class_='lineup__list')
    if len(player_lists) >= 2:
        game['away_team']['lineup'] = _parse_player_list(player_lists[0])
        game['home_team']['lineup'] = _parse_player_list(player_lists[1])

        for player in game['away_team']['lineup']:
            if player.get('status') in ['out', 'doubtful']:
                game['away_team']['injuries'].append(player['name'])
        for player in game['home_team']['lineup']:
            if player.get('status') in ['out', 'doubtful']:
                game['home_team']['injuries'].append(player['name'])

    return game


def _parse_player_list(player_list) -> list:
    """Parse a player list element."""
    players = []
    items = player_list.find_all('li')
    for item in items:
        player = _parse_player_item(item)
        if player:
            players.append(player)
    return players


def _parse_player_item(item) -> dict:
    """Parse a player item."""
    player = {}

    name_elem = item.find('a')
    if name_elem:
        player['name'] = name_elem.get_text(strip=True)
    else:
        return None

    pos_elem = item.find(class_='lineup__pos')
    if pos_elem:
        player['position'] = pos_elem.get_text(strip=True)

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


# CLI
if __name__ == "__main__":
    import sys

    print("RotoWire Auth Scraper")
    print("="*40)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "login":
            if not PLAYWRIGHT_AVAILABLE:
                print("\n[ERROR] Playwright not installed!")
                print("  pip install playwright")
                print("  playwright install chromium")
                sys.exit(1)
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
            print("\nCommands: login, check, today, tomorrow")
    else:
        print("\nUsage:")
        print("  python rotowire_auth.py login    - login to RotoWire")
        print("  python rotowire_auth.py check    - check auth status")
        print("  python rotowire_auth.py today    - today's lineups")
        print("  python rotowire_auth.py tomorrow - tomorrow's lineups")
