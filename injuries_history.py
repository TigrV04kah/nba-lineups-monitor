"""
Injuries History - сохранение истории травм игроков.
Со временем накопится база для анализа исторических составов.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_FILE = Path(__file__).parent / "injuries_history.db"


def init_db():
    """Инициализация базы данных."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            team_abbrev TEXT NOT NULL,
            player_name TEXT NOT NULL,
            status TEXT DEFAULT 'OUT',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, team_abbrev, player_name)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_injuries_date ON injuries(date)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_injuries_team ON injuries(team_abbrev)
    ''')

    conn.commit()
    conn.close()
    print(f"[OK] Injuries DB initialized: {DB_FILE}")


def save_injuries(team_abbrev: str, injured_players: list, game_date: str = None):
    """
    Сохранить травмированных игроков команды.

    Args:
        team_abbrev: Аббревиатура команды (OKC, DET, etc.)
        injured_players: Список имён травмированных игроков
        game_date: Дата игры (если None - используется сегодня)
    """
    if not injured_players:
        return

    if game_date is None:
        game_date = date.today().strftime('%Y-%m-%d')

    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    saved = 0
    for player in injured_players:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO injuries (date, team_abbrev, player_name, status)
                VALUES (?, ?, ?, 'OUT')
            ''', (game_date, team_abbrev, player))
            if cursor.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"[WARNING] Failed to save injury: {player} - {e}")

    conn.commit()
    conn.close()

    if saved > 0:
        print(f"[DB] Saved {saved} injuries for {team_abbrev} on {game_date}")


def get_injuries_for_date(team_abbrev: str, game_date: str) -> list:
    """
    Получить травмированных игроков команды на определённую дату.

    Returns:
        Список имён травмированных игроков
    """
    if not DB_FILE.exists():
        return []

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT player_name FROM injuries
        WHERE team_abbrev = ? AND date = ?
    ''', (team_abbrev, game_date))

    results = [row[0] for row in cursor.fetchall()]
    conn.close()

    return results


def get_injuries_stats() -> dict:
    """Статистика по базе травм."""
    if not DB_FILE.exists():
        return {'total': 0, 'teams': 0, 'dates': 0}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM injuries')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT team_abbrev) FROM injuries')
    teams = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT date) FROM injuries')
    dates = cursor.fetchone()[0]

    conn.close()

    return {'total': total, 'teams': teams, 'dates': dates}


# CLI для тестирования
if __name__ == "__main__":
    init_db()

    # Тест сохранения
    save_injuries("DET", ["C. Cunningham", "C. LeVert"], "2026-01-22")
    save_injuries("OKC", ["C. Holmgren"], "2026-01-22")

    # Тест получения
    injuries = get_injuries_for_date("DET", "2026-01-22")
    print(f"DET injuries on 2026-01-22: {injuries}")

    # Статистика
    stats = get_injuries_stats()
    print(f"DB stats: {stats}")
