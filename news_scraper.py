"""
News Scraper - парсер новостей NBA с сайта championat.ru
Сохраняет новости в SQLite базу данных с контролем дубликатов
"""

import os
import re
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

# Импорт маппинга команд
try:
    from team_mapping import find_teams_in_text
except ImportError:
    # Fallback если маппинг недоступен
    def find_teams_in_text(text):
        return []

# Импорт маппинга игроков
try:
    from player_mapping import find_player_in_text, get_player_keywords
except ImportError:
    def find_player_in_text(name, text):
        return name.lower() in text.lower()
    def get_player_keywords(name):
        return [name]

# Настройки
BASE_URL = "https://www.championat.ru"
NEWS_LIST_URL = BASE_URL + "/news/basketball/_nba/{page}.html"
DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def init_database():
    """Инициализация базы данных SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY,
            news_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT,
            author TEXT,
            published_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            sport TEXT DEFAULT 'basketball',
            section TEXT DEFAULT 'nba',
            teams TEXT DEFAULT ''
        )
    """)

    # Добавляем колонку teams если её нет (для миграции)
    try:
        cursor.execute("ALTER TABLE news ADD COLUMN teams TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_id ON news(news_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_published_at ON news(published_at)
    """)

    conn.commit()
    conn.close()
    print(f"База данных инициализирована: {DB_PATH}")


def news_exists(news_id: int) -> bool:
    """Проверка существования новости в базе."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM news WHERE news_id = ?", (news_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def save_news(news_data: Dict) -> bool:
    """Сохранение новости в базу данных."""
    if news_exists(news_data['news_id']):
        return False

    # Определяем команды в тексте
    text_for_search = f"{news_data['title']} {news_data.get('content', '')}"
    teams = find_teams_in_text(text_for_search)
    teams_str = ','.join(teams) if teams else ''

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO news (news_id, title, url, content, author, published_at, teams)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            news_data['news_id'],
            news_data['title'],
            news_data['url'],
            news_data.get('content', ''),
            news_data.get('author', ''),
            news_data.get('published_at'),
            teams_str
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def extract_news_id(url: str) -> Optional[int]:
    """Извлечение ID новости из URL."""
    match = re.search(r'news-(\d+)', url)
    if match:
        return int(match.group(1))
    return None


def parse_news_list_page(page: int = 1) -> List[Dict]:
    """
    Парсинг страницы со списком новостей.

    Returns:
        Список словарей с url и news_id
    """
    url = NEWS_LIST_URL.format(page=page)

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Ошибка загрузки страницы {page}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    news_items = []

    # Ищем все ссылки на новости баскетбола
    links = soup.find_all('a', href=re.compile(r'/basketball/news-\d+'))

    seen_ids = set()
    for link in links:
        href = link.get('href', '')

        # Пропускаем комментарии
        if '#comments' in href:
            continue

        news_id = extract_news_id(href)
        if news_id and news_id not in seen_ids:
            seen_ids.add(news_id)

            # Формируем полный URL
            full_url = href if href.startswith('http') else BASE_URL + href

            news_items.append({
                'news_id': news_id,
                'url': full_url
            })

    return news_items


def parse_article(url: str) -> Optional[Dict]:
    """
    Парсинг полной статьи.

    Returns:
        Словарь с данными статьи или None
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Ошибка загрузки статьи {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Извлекаем данные из JSON-LD схемы
    schema_script = soup.find('script', {'type': 'application/ld+json', 'class': 'js-schema'})

    title = ""
    author = ""
    published_at = None

    if schema_script:
        try:
            schema_data = json.loads(schema_script.string)
            title = schema_data.get('headline', '')

            # Автор
            author_data = schema_data.get('author', {})
            if isinstance(author_data, dict):
                author = author_data.get('name', '')

            # Дата публикации
            date_str = schema_data.get('datePublished', '')
            if date_str:
                # Парсим ISO формат: 2026-01-19T14:46:54+03:00
                # Убираем timezone для naive datetime
                try:
                    published_at = datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
                except:
                    pass
        except json.JSONDecodeError:
            pass

    # Если заголовок не нашли в схеме, ищем в HTML
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)

    # Извлекаем контент статьи
    content = ""
    article_content = soup.find('div', {'class': 'article-content', 'id': 'articleBody'})

    if article_content:
        # Удаляем рекламные блоки
        for banner in article_content.find_all('div', class_=re.compile(r'banner')):
            banner.decompose()

        # Собираем текст из параграфов
        paragraphs = article_content.find_all('p')
        content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

    news_id = extract_news_id(url)

    if not news_id or not title:
        return None

    return {
        'news_id': news_id,
        'title': title,
        'url': url,
        'content': content,
        'author': author,
        'published_at': published_at
    }


def get_date_from_article(url: str) -> Optional[datetime]:
    """Быстрое получение даты статьи без полного парсинга."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except:
        return None

    # Ищем дату в JSON-LD
    match = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})', response.text)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except:
            pass

    return None


def scrape_news(days: int = 3, max_pages: int = 20) -> Dict:
    """
    Основная функция парсинга новостей.

    Args:
        days: За сколько дней собирать новости
        max_pages: Максимальное количество страниц для парсинга

    Returns:
        Статистика парсинга
    """
    init_database()

    cutoff_date = datetime.now() - timedelta(days=days)
    stats = {
        'pages_processed': 0,
        'articles_found': 0,
        'articles_saved': 0,
        'articles_skipped': 0,
        'errors': 0
    }

    print(f"\n=== Начинаем парсинг новостей NBA за последние {days} дня ===")
    print(f"Дата отсечки: {cutoff_date.strftime('%Y-%m-%d')}\n")

    stop_parsing = False

    for page in range(1, max_pages + 1):
        if stop_parsing:
            break

        print(f"--- Страница {page} ---")
        news_items = parse_news_list_page(page)
        stats['pages_processed'] += 1

        if not news_items:
            print("Нет новостей на странице, завершаем")
            break

        for item in news_items:
            stats['articles_found'] += 1

            # Проверяем дубликат
            if news_exists(item['news_id']):
                print(f"  [SKIP] ID {item['news_id']} уже в базе")
                stats['articles_skipped'] += 1
                continue

            # Парсим полную статью
            article = parse_article(item['url'])

            if not article:
                print(f"  [ERROR] Не удалось распарсить {item['url']}")
                stats['errors'] += 1
                continue

            # Проверяем дату
            if article['published_at']:
                if article['published_at'] < cutoff_date:
                    print(f"  [OLD] {article['title'][:50]}... - {article['published_at'].strftime('%Y-%m-%d')}")
                    stop_parsing = True
                    break

            # Сохраняем
            if save_news(article):
                print(f"  [SAVED] {article['title'][:60]}...")
                stats['articles_saved'] += 1
            else:
                stats['articles_skipped'] += 1

            # Небольшая задержка между запросами
            time.sleep(0.5)

        # Задержка между страницами
        time.sleep(1)

    print(f"\n=== Парсинг завершён ===")
    print(f"Страниц обработано: {stats['pages_processed']}")
    print(f"Статей найдено: {stats['articles_found']}")
    print(f"Статей сохранено: {stats['articles_saved']}")
    print(f"Статей пропущено (дубликаты): {stats['articles_skipped']}")
    print(f"Ошибок: {stats['errors']}")

    return stats


def get_latest_news(limit: int = 10) -> List[Dict]:
    """Получение последних новостей из базы."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM news
        ORDER BY published_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def search_news(query: str, limit: int = 20) -> List[Dict]:
    """Поиск новостей по тексту."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM news
        WHERE title LIKE ? OR content LIKE ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (f'%{query}%', f'%{query}%', limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_news_stats() -> Dict:
    """Статистика по базе новостей."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM news")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT MIN(published_at), MAX(published_at) FROM news")
    date_range = cursor.fetchone()

    conn.close()

    return {
        'total_news': total,
        'oldest': date_range[0],
        'newest': date_range[1]
    }


def get_news_by_team(team_abbrev: str, limit: int = 10) -> List[Dict]:
    """
    Получение новостей по команде.

    Args:
        team_abbrev: Аббревиатура команды (напр. 'LAL', 'BOS')
        limit: Максимальное количество новостей

    Returns:
        Список новостей, отсортированных по дате
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ищем команду в поле teams (разделённые запятыми)
    cursor.execute("""
        SELECT * FROM news
        WHERE teams LIKE ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (f'%{team_abbrev}%', limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_news_for_matchup(team1_abbrev: str, team2_abbrev: str, limit: int = 10) -> List[Dict]:
    """
    Получение новостей для матча между двумя командами.

    Args:
        team1_abbrev: Аббревиатура первой команды
        team2_abbrev: Аббревиатура второй команды
        limit: Максимальное количество новостей

    Returns:
        Список новостей, связанных с обеими командами
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ищем новости где упоминается любая из команд
    cursor.execute("""
        SELECT * FROM news
        WHERE teams LIKE ? OR teams LIKE ?
        ORDER BY published_at DESC
        LIMIT ?
    """, (f'%{team1_abbrev}%', f'%{team2_abbrev}%', limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_teams_for_existing_news():
    """Обновить поле teams для существующих новостей (миграция)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, content FROM news WHERE teams = '' OR teams IS NULL")
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        text = f"{row['title']} {row['content'] or ''}"
        teams = find_teams_in_text(text)
        if teams:
            teams_str = ','.join(teams)
            cursor.execute("UPDATE news SET teams = ? WHERE id = ?", (teams_str, row['id']))
            updated += 1

    conn.commit()
    conn.close()

    print(f"Обновлено {updated} новостей с командами")
    return updated


def get_news_by_player(player_name: str, team_abbrev: str = None, days: int = 3, limit: int = 10) -> List[Dict]:
    """
    Получение новостей об игроке и его команде.

    Args:
        player_name: Имя игрока (английское, напр. 'LeBron James')
        team_abbrev: Аббревиатура команды (опционально, для расширения поиска)
        days: За сколько дней искать новости
        limit: Максимальное количество новостей

    Returns:
        Список релевантных новостей
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Дата отсечки
    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

    # Получаем все новости за период
    cursor.execute("""
        SELECT * FROM news
        WHERE published_at >= ?
        ORDER BY published_at DESC
    """, (cutoff_str,))

    rows = cursor.fetchall()
    conn.close()

    # Фильтруем по игроку
    player_news = []
    team_news = []

    for row in rows:
        news_dict = dict(row)
        text = f"{news_dict.get('title', '')} {news_dict.get('content', '')}"

        # Проверяем упоминание игрока
        if find_player_in_text(player_name, text):
            news_dict['relevance'] = 'player'  # Прямое упоминание игрока
            player_news.append(news_dict)
        # Проверяем упоминание команды
        elif team_abbrev:
            teams_in_news = news_dict.get('teams', '')
            if team_abbrev in teams_in_news:
                news_dict['relevance'] = 'team'  # Новость о команде
                team_news.append(news_dict)

    # Сначала новости об игроке, потом о команде
    result = player_news[:limit]
    if len(result) < limit:
        result.extend(team_news[:limit - len(result)])

    return result


def get_relevant_news_for_analysis(player_name: str, team_abbrev: str, opponent_abbrev: str = None, days: int = 3) -> Dict:
    """
    Получение релевантных новостей для AI анализа игрока.

    Args:
        player_name: Имя игрока
        team_abbrev: Команда игрока
        opponent_abbrev: Команда соперника (опционально)
        days: За сколько дней

    Returns:
        Словарь с новостями:
        {
            'player_news': [...],  # Новости об игроке
            'team_news': [...],    # Новости о команде
            'opponent_news': [...], # Новости о сопернике
            'has_relevant_news': bool
        }
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        SELECT * FROM news
        WHERE published_at >= ?
        ORDER BY published_at DESC
    """, (cutoff_str,))

    rows = cursor.fetchall()
    conn.close()

    player_news = []
    team_news = []
    opponent_news = []

    for row in rows:
        news_dict = dict(row)
        text = f"{news_dict.get('title', '')} {news_dict.get('content', '')}"
        teams_in_news = news_dict.get('teams', '')

        # Новости об игроке (приоритет)
        if find_player_in_text(player_name, text):
            player_news.append({
                'title': news_dict.get('title', ''),
                'content': news_dict.get('content', ''),  # Полный текст новости
                'date': news_dict.get('published_at', ''),
                'url': news_dict.get('url', '')
            })
        # Новости о команде игрока
        elif team_abbrev and team_abbrev in teams_in_news:
            team_news.append({
                'title': news_dict.get('title', ''),
                'content': news_dict.get('content', ''),  # Полный текст новости
                'date': news_dict.get('published_at', '')
            })
        # Новости о сопернике
        elif opponent_abbrev and opponent_abbrev in teams_in_news:
            opponent_news.append({
                'title': news_dict.get('title', ''),
                'date': news_dict.get('published_at', '')
            })

    return {
        'player_news': player_news[:5],  # Максимум 5 новостей об игроке
        'team_news': team_news[:3],       # Максимум 3 о команде
        'opponent_news': opponent_news[:2], # Максимум 2 о сопернике
        'has_relevant_news': len(player_news) > 0 or len(team_news) > 0
    }


# Тест
if __name__ == "__main__":
    # Запускаем парсинг за последние 3 дня
    stats = scrape_news(days=3)

    print("\n" + "="*50)
    print("Последние 5 новостей в базе:")
    print("="*50)

    for news in get_latest_news(5):
        date = news['published_at'] or 'N/A'
        print(f"\n[{date}] {news['title']}")
        print(f"  Автор: {news['author'] or 'Не указан'}")
        print(f"  URL: {news['url']}")
