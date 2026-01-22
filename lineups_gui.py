"""
NBA Lineups GUI - Графическое отображение составов команд
С мониторингом изменений составов
"""

import tkinter as tk
from tkinter import ttk, font, messagebox
import threading
import json
import os
from datetime import datetime
from plyer import notification
from nba_lineups_scraper import (
    get_nba_lineups_detailed, fetch_page, parse_lineups, ROTOWIRE_URL,
    get_team_last_game_starters_nba_api, get_multiple_teams_last_starters,
    get_team_last_n_games_stats
)
from ai_analyzer import analyze_lineup_changes, analyze_player_projection, init_openai

# Импорт авторизованного парсера (опционально)
try:
    from rotowire_auth import (
        check_playwright_installed, fetch_lineups_with_auth,
        run_login, check_auth_status
    )
    ROTOWIRE_AUTH_AVAILABLE = True
except ImportError:
    ROTOWIRE_AUTH_AVAILABLE = False
from news_scraper import get_news_by_team, get_news_for_matchup, get_latest_news, scrape_news, init_database
from team_mapping import get_team_name
import webbrowser

def get_last_name(full_name):
    """Извлечение фамилии из полного имени для сравнения."""
    if not full_name:
        return ""
    # Убираем суффиксы типа Jr., III, II
    name = full_name.replace(" Jr.", "").replace(" III", "").replace(" II", "").strip()
    parts = name.split()
    if len(parts) >= 2:
        # Берём последнюю часть как фамилию
        return parts[-1].lower()
    return name.lower()

def get_first_letter(full_name):
    """Извлечение первой буквы имени."""
    if not full_name:
        return ""
    name = full_name.strip()
    if name:
        return name[0].upper()
    return ""

def names_match(name1, name2):
    """
    Сравнение имён игроков: фамилия + первая буква имени.
    'S. Gilgeous-Alexander' vs 'Shai Gilgeous-Alexander' -> True
    'D. Mitchell' vs 'Donovan Mitchell' -> True
    """
    if not name1 or not name2:
        return False
    last1 = get_last_name(name1)
    last2 = get_last_name(name2)
    if last1 != last2:
        return False
    first1 = get_first_letter(name1)
    first2 = get_first_letter(name2)
    return first1 == first2

def normalize_name(name):
    """Нормализация имени для сравнения (D. Booker -> booker)."""
    if not name:
        return ""
    return get_last_name(name)

def match_players_by_lastname(current_names, past_names):
    """
    Сравнение списков игроков по фамилиям.
    Возвращает (new_players, removed_players) с оригинальными именами.
    """
    # Создаём словари: фамилия -> оригинальное имя
    current_by_lastname = {normalize_name(n): n for n in current_names}
    past_by_lastname = {normalize_name(n): n for n in past_names}

    current_lastnames = set(current_by_lastname.keys())
    past_lastnames = set(past_by_lastname.keys())

    # Новые игроки (есть сейчас, не было раньше)
    new_lastnames = current_lastnames - past_lastnames
    new_players = [current_by_lastname[ln] for ln in new_lastnames]

    # Выбывшие игроки (были раньше, нет сейчас)
    removed_lastnames = past_lastnames - current_lastnames
    removed_players = [past_by_lastname[ln] for ln in removed_lastnames]

    return new_players, removed_players

# Файл для хранения составов
LINEUPS_CACHE_FILE = "lineups_cache.json"  # Сохраняем в текущую директорию

# Файл для хранения исторических данных (последние игры)
HISTORICAL_CACHE_FILE = "historical_cache.json"  # Сохраняем в текущую директорию

# Файл для хранения статистики последних 3 игр
TEAM_STATS_CACHE_FILE = "team_stats_cache.json"  # Сохраняем в текущую директорию

# Интервал проверки (в миллисекундах) - 3 минуты
CHECK_INTERVAL_MS = 3 * 60 * 1000

# Время жизни кэша исторических данных (часы)
HISTORICAL_CACHE_TTL_HOURS = 12

# Время жизни кэша статистики команд (часы)
TEAM_STATS_CACHE_TTL_HOURS = 4

# Максимальный возраст кэша составов при запуске (часы)
LINEUPS_CACHE_MAX_AGE_HOURS = 4

# Цвета NBA команд (основные)
TEAM_COLORS = {
    'ATL': {'primary': '#E03A3E', 'secondary': '#C1D32F'},
    'BOS': {'primary': '#007A33', 'secondary': '#BA9653'},
    'BKN': {'primary': '#000000', 'secondary': '#FFFFFF'},
    'CHA': {'primary': '#1D1160', 'secondary': '#00788C'},
    'CHI': {'primary': '#CE1141', 'secondary': '#000000'},
    'CLE': {'primary': '#860038', 'secondary': '#FDBB30'},
    'DAL': {'primary': '#00538C', 'secondary': '#002B5E'},
    'DEN': {'primary': '#0E2240', 'secondary': '#FEC524'},
    'DET': {'primary': '#C8102E', 'secondary': '#1D42BA'},
    'GSW': {'primary': '#1D428A', 'secondary': '#FFC72C'},
    'HOU': {'primary': '#CE1141', 'secondary': '#000000'},
    'IND': {'primary': '#002D62', 'secondary': '#FDBB30'},
    'LAC': {'primary': '#C8102E', 'secondary': '#1D428A'},
    'LAL': {'primary': '#552583', 'secondary': '#FDB927'},
    'MEM': {'primary': '#5D76A9', 'secondary': '#12173F'},
    'MIA': {'primary': '#98002E', 'secondary': '#F9A01B'},
    'MIL': {'primary': '#00471B', 'secondary': '#EEE1C6'},
    'MIN': {'primary': '#0C2340', 'secondary': '#236192'},
    'NOP': {'primary': '#0C2340', 'secondary': '#C8102E'},
    'NYK': {'primary': '#006BB6', 'secondary': '#F58426'},
    'OKC': {'primary': '#007AC1', 'secondary': '#EF3B24'},
    'ORL': {'primary': '#0077C0', 'secondary': '#C4CED4'},
    'PHI': {'primary': '#006BB6', 'secondary': '#ED174C'},
    'PHX': {'primary': '#1D1160', 'secondary': '#E56020'},
    'POR': {'primary': '#E03A3E', 'secondary': '#000000'},
    'SAC': {'primary': '#5A2D81', 'secondary': '#63727A'},
    'SAS': {'primary': '#C4CED4', 'secondary': '#000000'},
    'TOR': {'primary': '#CE1141', 'secondary': '#000000'},
    'UTA': {'primary': '#002B5C', 'secondary': '#00471B'},
    'WAS': {'primary': '#002B5C', 'secondary': '#E31837'},
}

# Позиции и их порядок
POSITIONS_ORDER = ['PG', 'SG', 'SF', 'PF', 'C']


class LineupsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NBA Lineups - Today's Games")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a2e')

        self.games = []
        self.previous_lineups = {}  # Хранение предыдущих составов
        self.changes_log = []  # Лог изменений
        self._click_handlers = []  # Хранение ссылок на обработчики кликов (GC protection)
        self.auto_check_enabled = True  # Автопроверка включена
        self.check_job = None  # ID задачи автопроверки
        self.historical_cache = {}  # Кэш исторических данных (последние игры команд)
        self.team_stats_cache = {}  # Кэш статистики последних 3 игр команд
        self.cache_is_stale = False  # Флаг устаревшего кэша
        self.ai_enabled = False  # AI анализ
        self.selected_date = "today"  # Выбранная дата: "today" или "tomorrow"
        # Check if auth cookies exist (Playwright only needed for login, not fetching)
        self.rotowire_auth_available = ROTOWIRE_AUTH_AVAILABLE and check_auth_status() if ROTOWIRE_AUTH_AVAILABLE else False

        # Инициализируем AI
        self.ai_enabled = init_openai()
        if self.ai_enabled:
            print("AI анализатор инициализирован")
        else:
            print("AI анализатор недоступен - проверьте .env файл")

        # Инициализируем базу новостей
        try:
            init_database()
            print("База новостей инициализирована")
        except Exception as e:
            print(f"Ошибка инициализации базы новостей: {e}")

        # Загружаем кэши если есть
        self.load_cache()
        self.load_historical_cache()
        self.load_team_stats_cache()

        self.setup_ui()

        # Если кэш устарел (>4 часа), сначала показываем сообщение, потом обновляем
        if self.cache_is_stale:
            self.status_label.config(text="Cache is stale (>4h), refreshing...", fg='#ffd93d')
            print("Кэш устарел более чем на 4 часа - запускаем обновление...")

        self.load_data()

        # Запускаем автопроверку составов
        self.schedule_auto_check()

        # Запускаем фоновое обновление новостей при старте
        self.update_news_in_background()

    def setup_ui(self):
        # Заголовок
        header_frame = tk.Frame(self.root, bg='#16213e', height=60)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)

        title_font = font.Font(family='Arial', size=20, weight='bold')
        title = tk.Label(header_frame, text="NBA LINEUPS", font=title_font,
                        fg='#e94560', bg='#16213e')
        title.pack(side='left', padx=20, pady=15)

        # Переключатель дат Today/Tomorrow
        date_frame = tk.Frame(header_frame, bg='#16213e')
        date_frame.pack(side='left', padx=10, pady=15)

        self.today_btn = tk.Button(date_frame, text="Today",
                                   command=lambda: self.switch_date("today"),
                                   bg='#e94560', fg='white',
                                   font=('Arial', 10, 'bold'),
                                   relief='flat', padx=12, pady=3)
        self.today_btn.pack(side='left', padx=2)

        self.tomorrow_btn = tk.Button(date_frame, text="Tomorrow",
                                      command=lambda: self.switch_date("tomorrow"),
                                      bg='#0f3460', fg='white',
                                      font=('Arial', 10, 'bold'),
                                      relief='flat', padx=12, pady=3)
        self.tomorrow_btn.pack(side='left', padx=2)

        # Кнопка RotoWire Login (если доступен Playwright)
        if self.rotowire_auth_available:
            self.login_btn = tk.Button(date_frame, text="🔑",
                                       command=self.rotowire_login,
                                       bg='#2ecc71', fg='white',
                                       font=('Arial', 10),
                                       relief='flat', padx=5, pady=3)
            self.login_btn.pack(side='left', padx=5)

        # Кнопка обновления
        self.refresh_btn = tk.Button(header_frame, text="Refresh",
                                     command=self.refresh_data,
                                     bg='#0f3460', fg='white',
                                     font=('Arial', 10, 'bold'),
                                     relief='flat', padx=15, pady=5)
        self.refresh_btn.pack(side='right', padx=20, pady=15)

        # Кнопка лога изменений
        self.log_btn = tk.Button(header_frame, text="Changes Log",
                                 command=self.show_changes_log,
                                 bg='#0f3460', fg='white',
                                 font=('Arial', 10, 'bold'),
                                 relief='flat', padx=15, pady=5)
        self.log_btn.pack(side='right', padx=5, pady=15)

        # Кнопка сравнения с прошлой игрой
        self.compare_btn = tk.Button(header_frame, text="vs Last Game",
                                     command=self.compare_with_last_game,
                                     bg='#6bcb77', fg='white',
                                     font=('Arial', 10, 'bold'),
                                     relief='flat', padx=10, pady=5)
        self.compare_btn.pack(side='right', padx=5, pady=15)

        # Кнопка AI анализа
        ai_btn_color = '#9b59b6' if self.ai_enabled else '#555555'
        self.ai_btn = tk.Button(header_frame, text="AI Analysis",
                                command=self.show_ai_analysis_selection,
                                bg=ai_btn_color, fg='white',
                                font=('Arial', 10, 'bold'),
                                relief='flat', padx=10, pady=5)
        self.ai_btn.pack(side='right', padx=5, pady=15)

        # Кнопка Новости
        self.news_btn = tk.Button(header_frame, text="📰 News",
                                  command=self.show_news_window,
                                  bg='#e67e22', fg='white',
                                  font=('Arial', 10, 'bold'),
                                  relief='flat', padx=10, pady=5)
        self.news_btn.pack(side='right', padx=5, pady=15)

        # Кнопка тестового изменения (для отладки)
        self.test_btn = tk.Button(header_frame, text="Test Change",
                                  command=self.simulate_change,
                                  bg='#ff6b6b', fg='white',
                                  font=('Arial', 10, 'bold'),
                                  relief='flat', padx=10, pady=5)
        self.test_btn.pack(side='right', padx=5, pady=15)

        # Checkbox автопроверки
        self.auto_check_var = tk.BooleanVar(value=True)
        self.auto_check_cb = tk.Checkbutton(header_frame, text="Auto (3 min)",
                                            variable=self.auto_check_var,
                                            command=self.toggle_auto_check,
                                            bg='#16213e', fg='#a0a0a0',
                                            selectcolor='#0f3460',
                                            activebackground='#16213e',
                                            font=('Arial', 9))
        self.auto_check_cb.pack(side='right', padx=10, pady=15)

        # Статус
        self.status_label = tk.Label(header_frame, text="Loading...",
                                    font=('Arial', 10), fg='#a0a0a0', bg='#16213e')
        self.status_label.pack(side='right', padx=10, pady=15)

        # Главный контейнер с двумя колонками: игры слева, новости справа
        main_container = tk.Frame(self.root, bg='#1a1a2e')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Левая часть - игры (70% ширины)
        games_container = tk.Frame(main_container, bg='#1a1a2e')
        games_container.pack(side='left', fill='both', expand=True)

        # Canvas и scrollbar для игр
        self.canvas = tk.Canvas(games_container, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(games_container, orient='vertical', command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas, bg='#1a1a2e')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)

        # Правая часть - панель новостей (фиксированная ширина 320px)
        self._create_news_panel(main_container)

        # Mouse wheel scrolling - только когда курсор над canvas игр
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_news_mousewheel(self, event):
        """Скролл для панели новостей."""
        self.news_panel_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _create_news_panel(self, parent):
        """Создание боковой панели новостей."""
        # Контейнер панели (480px = 320 + 50%)
        news_panel = tk.Frame(parent, bg='#16213e', width=480)
        news_panel.pack(side='right', fill='y', padx=(10, 0))
        news_panel.pack_propagate(False)  # Фиксируем ширину

        # Заголовок панели
        header = tk.Frame(news_panel, bg='#e67e22')
        header.pack(fill='x')

        title = tk.Label(header, text="Latest News",
                        font=('Arial', 12, 'bold'), fg='white', bg='#e67e22')
        title.pack(side='left', padx=10, pady=8)

        # Кнопка обновления
        refresh_btn = tk.Button(header, text="Refresh",
                               command=self._refresh_news_panel,
                               bg='#d35400', fg='white',
                               font=('Arial', 9),
                               relief='flat', padx=8, pady=2)
        refresh_btn.pack(side='right', padx=10, pady=8)

        # Скроллируемый контейнер для новостей
        container = tk.Frame(news_panel, bg='#1a1a2e')
        container.pack(fill='both', expand=True, padx=5, pady=5)

        self.news_panel_canvas = tk.Canvas(container, bg='#1a1a2e', highlightthickness=0, width=460)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=self.news_panel_canvas.yview)

        self.news_panel_frame = tk.Frame(self.news_panel_canvas, bg='#1a1a2e')
        self.news_panel_frame.bind(
            "<Configure>",
            lambda e: self.news_panel_canvas.configure(scrollregion=self.news_panel_canvas.bbox("all"))
        )

        self.news_panel_canvas.create_window((0, 0), window=self.news_panel_frame, anchor='nw')
        self.news_panel_canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel для новостей
        self.news_panel_canvas.bind("<Enter>", lambda e: self.news_panel_canvas.bind_all("<MouseWheel>", self._on_news_mousewheel))
        self.news_panel_canvas.bind("<Leave>", lambda e: self.news_panel_canvas.unbind_all("<MouseWheel>"))

        scrollbar.pack(side='right', fill='y')
        self.news_panel_canvas.pack(side='left', fill='both', expand=True)

        # Загружаем новости
        self._load_news_panel()

    def _load_news_panel(self):
        """Загрузка новостей в боковую панель."""
        # Очищаем
        for widget in self.news_panel_frame.winfo_children():
            widget.destroy()

        try:
            news_list = get_latest_news(15)  # Последние 15 новостей
        except Exception as e:
            error_label = tk.Label(self.news_panel_frame,
                                  text=f"Error: {e}",
                                  font=('Arial', 10), fg='#ff6b6b', bg='#1a1a2e',
                                  wraplength=280)
            error_label.pack(pady=20)
            return

        if not news_list:
            no_news = tk.Label(self.news_panel_frame,
                              text="No news available.\nClick Refresh to update.",
                              font=('Arial', 10), fg='#a0a0a0', bg='#1a1a2e')
            no_news.pack(pady=30)
            return

        # Отображаем новости компактно
        for news in news_list:
            self._create_news_panel_card(news)

    def _create_news_panel_card(self, news):
        """Создание компактной карточки новости для боковой панели."""
        card = tk.Frame(self.news_panel_frame, bg='#0f3460', cursor='hand2')
        card.pack(fill='x', pady=3, padx=5)  # Добавлен отступ слева/справа для карточки

        # Дата
        published = news.get('published_at', '')
        if published:
            try:
                dt = datetime.strptime(str(published)[:19], '%Y-%m-%d %H:%M:%S')
                date_str = dt.strftime('%d.%m %H:%M')
            except:
                date_str = ''
        else:
            date_str = ''

        # Верхняя строка: дата и команды
        meta_frame = tk.Frame(card, bg='#0f3460')
        meta_frame.pack(fill='x', padx=10, pady=(5, 2))

        if date_str:
            date_label = tk.Label(meta_frame, text=date_str,
                                 font=('Arial', 8), fg='#888888', bg='#0f3460')
            date_label.pack(side='left')

        # Теги команд
        teams_str = news.get('teams', '')
        if teams_str:
            teams = teams_str.split(',')[:2]  # Максимум 2 тега
            for team in teams:
                team = team.strip()
                color = TEAM_COLORS.get(team, {}).get('primary', '#444444')
                tag = tk.Label(meta_frame, text=team,
                              font=('Arial', 7, 'bold'), fg='white', bg=color,
                              padx=4, pady=1)
                tag.pack(side='right', padx=1)

        # Заголовок новости (без обрезки - wraplength сам переносит)
        title = news.get('title', 'No title')

        title_label = tk.Label(card, text=title,
                              font=('Arial', 9), fg='#ffffff', bg='#0f3460',
                              wraplength=420, justify='left', anchor='w')
        title_label.pack(fill='x', padx=10, pady=(0, 8))

        # Клик открывает ссылку
        url = news.get('url', '')
        if url:
            card.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            title_label.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            meta_frame.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        # Hover эффект
        def on_enter(e):
            card.configure(bg='#1a4a7a')
            title_label.configure(bg='#1a4a7a')
            meta_frame.configure(bg='#1a4a7a')
            for child in meta_frame.winfo_children():
                if isinstance(child, tk.Label) and child.cget('fg') == '#888888':
                    child.configure(bg='#1a4a7a')

        def on_leave(e):
            card.configure(bg='#0f3460')
            title_label.configure(bg='#0f3460')
            meta_frame.configure(bg='#0f3460')
            for child in meta_frame.winfo_children():
                if isinstance(child, tk.Label) and child.cget('fg') == '#888888':
                    child.configure(bg='#0f3460')

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    def _refresh_news_panel(self):
        """Обновление новостей в боковой панели."""
        def update():
            try:
                scrape_news(pages=2)
            except Exception as e:
                print(f"Error updating news: {e}")
            self.root.after(0, self._load_news_panel)

        thread = threading.Thread(target=update, daemon=True)
        thread.start()

    def load_data(self):
        """Загрузка данных в фоновом потоке."""
        # Проверяем актуальность кэша
        if not self.cache_is_stale and self.games:
            # Кэш свежий и игры уже загружены - используем их
            print("Используем кэшированные составы (свежие)")
            self._update_ui()
            self.status_label.config(text=f"Ready ({len(self.games)} games)")
            return

        # Кэш устарел - загружаем новые данные
        self.status_label.config(text="Loading...")
        self.refresh_btn.config(state='disabled')

        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()

    def _fetch_data(self):
        """Получение данных с сайта."""
        try:
            if self.rotowire_auth_available:
                # Используем авторизованный парсинг (работает и для today и для tomorrow)
                print(f"Загрузка лайнапов на {self.selected_date} (авторизованный режим)...")
                self.games = fetch_lineups_with_auth(self.selected_date)
            else:
                # Стандартный парсинг (без Playwright)
                url = ROTOWIRE_URL
                if self.selected_date == "tomorrow":
                    url = f"{ROTOWIRE_URL}?date=tomorrow"
                    print(f"Загрузка лайнапов на завтра (без авторизации - могут быть ограничения)...")
                else:
                    print(f"Загрузка лайнапов на сегодня...")

                soup = fetch_page(url)
                self.games = parse_lineups(soup)

            # Помечаем кэш как свежий и сохраняем
            self.cache_is_stale = False
            self.save_cache()

            self.root.after(0, self._update_ui)
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(text=f"Error: {e}"))
            self.root.after(0, lambda: self.refresh_btn.config(state='normal'))

    def _update_ui(self):
        """Обновление интерфейса с данными."""
        # Очищаем старые виджеты и обработчики
        self._click_handlers.clear()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        date_text = "today" if self.selected_date == "today" else "tomorrow"
        if not self.games:
            no_games = tk.Label(self.scrollable_frame, text=f"No games {date_text}",
                               font=('Arial', 16), fg='#a0a0a0', bg='#1a1a2e')
            no_games.pack(pady=50)
        else:
            # Создаем карточки игр
            for i, game in enumerate(self.games):
                self.create_game_card(game, i)

        self.status_label.config(text=f"{len(self.games)} games {date_text}")
        self.refresh_btn.config(state='normal')

        # Предзагружаем статистику всех команд в фоне
        self.preload_all_teams_stats()

    def create_game_card(self, game, index):
        """Создание карточки одной игры."""
        # Основной контейнер карточки
        card = tk.Frame(self.scrollable_frame, bg='#16213e', relief='flat')
        card.pack(fill='x', padx=5, pady=8)

        # Заголовок игры (время)
        game_time = game.get('game_time', 'TBD')
        header = tk.Frame(card, bg='#0f3460')
        header.pack(fill='x')

        time_label = tk.Label(header, text=game_time, font=('Arial', 11, 'bold'),
                             fg='#e94560', bg='#0f3460')
        time_label.pack(side='left', padx=15, pady=8)

        # Контейнер для обеих команд
        teams_frame = tk.Frame(card, bg='#16213e')
        teams_frame.pack(fill='x', padx=10, pady=10)

        # Левая команда (Away)
        away = game.get('away_team', {})
        home = game.get('home_team', {})

        away_frame = tk.Frame(teams_frame, bg='#16213e')
        away_frame.pack(side='left', fill='both', expand=True, padx=5)
        # Away team plays against Home team, not at home
        self.create_team_lineup(away_frame, away, 'away', opponent_abbrev=home.get('abbrev'), is_home=False)

        # VS посередине
        vs_frame = tk.Frame(teams_frame, bg='#16213e', width=60)
        vs_frame.pack(side='left', fill='y', padx=10)
        vs_frame.pack_propagate(False)

        vs_label = tk.Label(vs_frame, text="@", font=('Arial', 24, 'bold'),
                           fg='#e94560', bg='#16213e')
        vs_label.pack(expand=True)

        # Правая команда (Home)
        home_frame = tk.Frame(teams_frame, bg='#16213e')
        home_frame.pack(side='left', fill='both', expand=True, padx=5)
        # Home team plays against Away team, at home
        self.create_team_lineup(home_frame, home, 'home', opponent_abbrev=away.get('abbrev'), is_home=True)

    def create_team_lineup(self, parent, team_data, team_type, opponent_abbrev=None, is_home=None):
        """Создание блока состава одной команды."""
        abbrev = team_data.get('abbrev', '???')
        record = team_data.get('record', '')
        lineup = team_data.get('lineup', [])

        # Получаем цвета команды
        colors = TEAM_COLORS.get(abbrev, {'primary': '#333333', 'secondary': '#666666'})

        # Заголовок команды (кликабельный)
        team_header = tk.Frame(parent, bg=colors['primary'], cursor='hand2')
        team_header.pack(fill='x')

        team_name = tk.Label(team_header, text=f"{abbrev}",
                            font=('Arial', 16, 'bold'),
                            fg='white', bg=colors['primary'], cursor='hand2')
        team_name.pack(side='left', padx=10, pady=8)

        record_label = tk.Label(team_header, text=record,
                               font=('Arial', 10),
                               fg='#cccccc', bg=colors['primary'], cursor='hand2')
        record_label.pack(side='left', padx=5, pady=8)

        # Иконка "кликни для статистики"
        stats_hint = tk.Label(team_header, text="📊",
                             font=('Arial', 10),
                             fg='#ffffff', bg=colors['primary'], cursor='hand2')
        stats_hint.pack(side='left', padx=5, pady=8)

        type_label = tk.Label(team_header, text=team_type.upper(),
                             font=('Arial', 8),
                             fg='#999999', bg=colors['primary'])
        type_label.pack(side='right', padx=10, pady=8)

        # Привязываем клик к заголовку и всем его элементам
        for widget in [team_header, team_name, record_label, stats_hint]:
            widget.bind('<Button-1>', lambda e, a=abbrev, o=opponent_abbrev, h=is_home: self.show_team_stats(a, o, h))

        # Список игроков
        players_frame = tk.Frame(parent, bg='#1a1a2e')
        players_frame.pack(fill='x', padx=2, pady=5)

        # Фильтруем только стартовый состав (первые 5 по позициям PG, SG, SF, PF, C)
        starters = []
        bench = []

        for player in lineup:
            pos = player.get('position', '')
            if pos in POSITIONS_ORDER and len(starters) < 5:
                # Проверяем что эта позиция еще не занята
                existing_positions = [p.get('position') for p in starters]
                if pos not in existing_positions:
                    starters.append(player)
                else:
                    bench.append(player)
            else:
                bench.append(player)

        # Если не хватает стартеров, добавляем из bench
        while len(starters) < 5 and bench:
            starters.append(bench.pop(0))

        # Отображаем стартеров
        for player in starters:
            self.create_player_row(players_frame, player, colors, is_starter=True)

        # Разделитель если есть травмированные
        injured = [p for p in lineup if p.get('status') == 'out']
        if injured:
            separator = tk.Frame(players_frame, bg='#333333', height=1)
            separator.pack(fill='x', pady=5)

            inj_label = tk.Label(players_frame, text="INJURIES",
                                font=('Arial', 8, 'bold'),
                                fg='#e94560', bg='#1a1a2e')
            inj_label.pack(anchor='w', padx=5)

            for player in injured:
                self.create_player_row(players_frame, player, colors, is_starter=False)

    def create_player_row(self, parent, player, colors, is_starter=True):
        """Создание строки с игроком."""
        name = player.get('name', 'Unknown')
        print(f"[CREATE ROW] Создаю строку для: {name}")
        position = player.get('position', '?')
        status = player.get('status', 'active')

        row = tk.Frame(parent, bg='#1a1a2e')
        row.pack(fill='x', pady=1)

        # Позиция
        pos_bg = colors['primary'] if is_starter else '#444444'
        pos_label = tk.Label(row, text=position, font=('Arial', 9, 'bold'),
                            fg='white', bg=pos_bg, width=3)
        pos_label.pack(side='left', padx=2)

        # Имя игрока
        name_color = '#ffffff' if status == 'active' else '#ff6b6b'
        if status == 'questionable':
            name_color = '#ffd93d'
        elif status == 'probable':
            name_color = '#6bcb77'
        elif status == 'doubtful':
            name_color = '#ff8c00'

        name_label = tk.Label(row, text=name, font=('Arial', 10),
                             fg=name_color, bg='#1a1a2e', anchor='w', cursor='hand2')
        name_label.pack(side='left', padx=5, fill='x', expand=True)

        # Добавляем обработчик клика на имя игрока для AI анализа
        player_data = player.copy()

        # Сохраняем данные прямо в виджете
        name_label.player_data = player_data
        name_label.original_color = name_color

        # Привязываем события через методы класса
        name_label.bind('<Button-1>', self._handle_player_label_click)
        name_label.bind('<Enter>', self._handle_player_label_enter)
        name_label.bind('<Leave>', self._handle_player_label_leave)

        # Сохраняем ссылку на label
        self._click_handlers.append(name_label)
        print(f"[BIND OK] {name} - handlers count: {len(self._click_handlers)}")

        # Статус (если не active)
        if status != 'active':
            status_text = status.upper()
            status_color = '#ff6b6b' if status == 'out' else '#ffd93d'
            status_label = tk.Label(row, text=status_text, font=('Arial', 8, 'bold'),
                                   fg=status_color, bg='#1a1a2e')
            status_label.pack(side='right', padx=5)

    def switch_date(self, date: str):
        """Переключение между Today и Tomorrow."""
        if date == self.selected_date:
            return

        self.selected_date = date

        # Обновляем стили кнопок
        if date == "today":
            self.today_btn.config(bg='#e94560')
            self.tomorrow_btn.config(bg='#0f3460')
            self.root.title("NBA Lineups - Today's Games")
        else:
            self.today_btn.config(bg='#0f3460')
            self.tomorrow_btn.config(bg='#e94560')
            self.root.title("NBA Lineups - Tomorrow's Games")

        # Загружаем данные для новой даты
        self.cache_is_stale = True  # Принудительно обновляем
        self.load_data()

    def rotowire_login(self):
        """Запуск интерактивной авторизации на RotoWire."""
        if not self.rotowire_auth_available:
            messagebox.showwarning("Недоступно",
                "Playwright не установлен.\n\n"
                "Для установки выполните:\n"
                "pip install playwright\n"
                "playwright install chromium")
            return

        # Показываем инструкцию
        result = messagebox.askyesno("RotoWire Login",
            "⚠️ ВАЖНО: Сначала закройте ВСЕ окна Chrome!\n\n"
            "Затем:\n"
            "1. Откроется Chrome с вашим профилем\n"
            "2. Войдите на RotoWire через Google\n"
            "3. После входа закройте браузер\n\n"
            "Chrome закрыт? Продолжить?")

        if not result:
            return

        # Запускаем авторизацию в отдельном потоке
        def do_login():
            success = run_login()
            self.root.after(0, lambda: self._on_login_complete(success))

        self.status_label.config(text="Авторизация на RotoWire...", fg='#ffd93d')
        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_complete(self, success: bool):
        """Callback после завершения авторизации."""
        if success:
            messagebox.showinfo("Успех", "Авторизация на RotoWire успешна!\n\nТеперь доступны лайнапы на завтра.")
            self.status_label.config(text="RotoWire авторизован", fg='#2ecc71')
        else:
            messagebox.showwarning("Ошибка", "Авторизация не удалась.\nПопробуйте ещё раз.")
            self.status_label.config(text="Ошибка авторизации", fg='#e94560')

    def refresh_data(self):
        """Обновление данных (принудительно, игнорируя кэш)."""
        # Помечаем кэш как устаревший, чтобы загрузить свежие данные
        self.cache_is_stale = True
        self.load_data()

    def load_cache(self):
        """Загрузка кэша составов из файла с проверкой свежести."""
        try:
            if os.path.exists(LINEUPS_CACHE_FILE):
                with open(LINEUPS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.previous_lineups = data.get('lineups', {})
                    self.changes_log = data.get('changes_log', [])
                    cached_games = data.get('games', [])
                    last_update_str = data.get('last_update', '')

                    print(f"Загружен кэш: {len(self.previous_lineups)} игр")

                    # Проверяем возраст кэша
                    if last_update_str:
                        try:
                            last_update = datetime.strptime(last_update_str, '%Y-%m-%d %H:%M:%S')
                            hours_passed = (datetime.now() - last_update).total_seconds() / 3600
                            print(f"Возраст кэша: {hours_passed:.1f} ч (максимум: {LINEUPS_CACHE_MAX_AGE_HOURS} ч)")

                            if hours_passed > LINEUPS_CACHE_MAX_AGE_HOURS:
                                self.cache_is_stale = True
                                print(f"Кэш устарел! Последнее обновление: {last_update_str}")
                            else:
                                # Кэш свежий - используем сохранённые составы
                                self.games = cached_games
                                self.cache_is_stale = False
                                print(f"Кэш актуален. Последнее обновление: {last_update_str}")
                                print(f"Загружено {len(self.games)} игр из кэша")
                        except ValueError as ve:
                            print(f"Ошибка парсинга даты кэша: {ve}")
                            self.cache_is_stale = True
                    else:
                        # Нет информации о времени - считаем устаревшим
                        self.cache_is_stale = True
                        print("Кэш без метки времени - считаем устаревшим")
            else:
                # Файла нет - кэш пуст, будет загружен свежий
                print("Файл кэша не найден - будет создан новый")
                self.cache_is_stale = True
        except Exception as e:
            print(f"Ошибка загрузки кэша: {e}")
            self.previous_lineups = {}
            self.changes_log = []
            self.cache_is_stale = True

    def save_cache(self):
        """Сохранение кэша составов в файл."""
        try:
            data = {
                'lineups': self.previous_lineups,
                'games': self.games,  # Сохраняем полные данные игр
                'changes_log': self.changes_log[-100:],  # Храним последние 100 изменений
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(LINEUPS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Кэш сохранён: {len(self.games)} игр")
        except Exception as e:
            print(f"Ошибка сохранения кэша: {e}")

    def load_historical_cache(self):
        """Загрузка кэша исторических данных из файла."""
        try:
            if os.path.exists(HISTORICAL_CACHE_FILE):
                with open(HISTORICAL_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.historical_cache = data.get('teams', {})
                    last_update = data.get('last_update', '')
                    print(f"Загружен исторический кэш: {len(self.historical_cache)} команд, обновлен: {last_update}")
        except Exception as e:
            print(f"Ошибка загрузки исторического кэша: {e}")
            self.historical_cache = {}

    def save_historical_cache(self):
        """Сохранение кэша исторических данных в файл."""
        try:
            data = {
                'teams': self.historical_cache,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(HISTORICAL_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Исторический кэш сохранен: {len(self.historical_cache)} команд")
        except Exception as e:
            print(f"Ошибка сохранения исторического кэша: {e}")

    def is_historical_cache_valid(self, team_abbrev):
        """Проверка актуальности кэша для команды (TTL = 12 часов)."""
        if team_abbrev not in self.historical_cache:
            return False

        cached_data = self.historical_cache[team_abbrev]
        cached_time_str = cached_data.get('cached_at', '')

        if not cached_time_str:
            return False

        try:
            cached_time = datetime.strptime(cached_time_str, '%Y-%m-%d %H:%M:%S')
            hours_passed = (datetime.now() - cached_time).total_seconds() / 3600
            return hours_passed < HISTORICAL_CACHE_TTL_HOURS
        except:
            return False

    def load_team_stats_cache(self):
        """Загрузка кэша статистики последних 3 игр."""
        try:
            if os.path.exists(TEAM_STATS_CACHE_FILE):
                with open(TEAM_STATS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.team_stats_cache = data.get('teams', {})
                    last_update = data.get('last_update', '')
                    print(f"Загружен кэш статистики: {len(self.team_stats_cache)} команд, обновлен: {last_update}")
        except Exception as e:
            print(f"Ошибка загрузки кэша статистики: {e}")
            self.team_stats_cache = {}

    def save_team_stats_cache(self):
        """Сохранение кэша статистики последних 3 игр."""
        try:
            data = {
                'teams': self.team_stats_cache,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(TEAM_STATS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Кэш статистики сохранен: {len(self.team_stats_cache)} команд")
        except Exception as e:
            print(f"Ошибка сохранения кэша статистики: {e}")

    def is_team_stats_cache_valid(self, team_abbrev):
        """Проверка актуальности кэша статистики команды (TTL = 24 часа)."""
        if team_abbrev not in self.team_stats_cache:
            return False

        cached_data = self.team_stats_cache[team_abbrev]
        cached_time_str = cached_data.get('cached_at', '')

        if not cached_time_str:
            return False

        try:
            cached_time = datetime.strptime(cached_time_str, '%Y-%m-%d %H:%M:%S')
            hours_passed = (datetime.now() - cached_time).total_seconds() / 3600
            return hours_passed < TEAM_STATS_CACHE_TTL_HOURS
        except:
            return False

    def get_game_key(self, game):
        """Создание уникального ключа игры."""
        away = game.get('away_team', {}).get('abbrev', '')
        home = game.get('home_team', {}).get('abbrev', '')
        return f"{away}@{home}"

    def get_starters(self, lineup):
        """Извлечение стартовой пятёрки из состава."""
        starters = {}
        for player in lineup:
            pos = player.get('position', '')
            status = player.get('status', 'active')
            # Только активные игроки в стартовой пятёрке
            if pos in POSITIONS_ORDER and pos not in starters and status != 'out':
                starters[pos] = player.get('name', 'Unknown')
        return starters

    def compare_lineups(self, old_lineups, new_lineups):
        """Сравнение старых и новых составов. Возвращает список изменений."""
        changes = []
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Проверяем что new_lineups это словарь
        if isinstance(new_lineups, dict):
            # Итерируем по элементам словаря
            for game_key, game in new_lineups.items():
                if game_key not in old_lineups:
                    continue  # Новая игра, не сравниваем

                old_game = old_lineups[game_key]

                # Проверяем что old_game это словарь, а не строка
                if not isinstance(old_game, dict):
                    continue

                # Сравниваем away team и home team
                for team_type in ['away_team', 'home_team']:
                    team_abbrev = game.get(team_type, {}).get('abbrev', '???')
                    old_starters = self.get_starters(old_game.get(team_type, {}).get('lineup', []))
                    new_starters = self.get_starters(game.get(team_type, {}).get('lineup', []))

                    for pos in POSITIONS_ORDER:
                        old_player = old_starters.get(pos, '')
                        new_player = new_starters.get(pos, '')

                        if old_player and new_player and old_player != new_player:
                            change = {
                                'time': timestamp,
                                'game': game_key,
                                'team': team_abbrev,
                                'position': pos,
                                'old_player': old_player,
                                'new_player': new_player
                            }
                            changes.append(change)

        return changes

    def games_to_dict(self, games):
        """Преобразование списка игр в словарь для хранения."""
        result = {}
        for game in games:
            key = self.get_game_key(game)
            result[key] = {
                'away_team': game.get('away_team', {}),
                'home_team': game.get('home_team', {}),
                'game_time': game.get('game_time')
            }
        return result

    def check_for_changes(self):
        """Проверка изменений в составах."""
        if not self.games:
            return []

        current_lineups = self.games_to_dict(self.games)
        changes = self.compare_lineups(self.previous_lineups, current_lineups)

        if changes:
            # Добавляем изменения в лог
            self.changes_log.extend(changes)

            # Показываем уведомление
            self.show_notification(changes)

            # Обновляем UI - подсвечиваем изменения
            self.highlight_changes(changes)

            # Запускаем AI анализ при изменениях
            self.auto_ai_analysis_on_change(changes)

        # Обновляем кэш
        self.previous_lineups = current_lineups
        self.save_cache()

        return changes

    def show_notification(self, changes):
        """Показ системного уведомления об изменениях."""
        try:
            msg_lines = []
            for ch in changes[:5]:  # Максимум 5 изменений в уведомлении
                msg_lines.append(f"{ch['team']} {ch['position']}: {ch['old_player']} -> {ch['new_player']}")

            msg = "\n".join(msg_lines)
            if len(changes) > 5:
                msg += f"\n...and {len(changes) - 5} more"

            notification.notify(
                title=f"NBA Lineup Changed! ({len(changes)})",
                message=msg,
                app_name="NBA Lineups",
                timeout=10
            )
        except Exception as e:
            print(f"Ошибка уведомления: {e}")
            # Fallback - показываем messagebox
            self.root.after(0, lambda: messagebox.showinfo(
                "Lineup Changed!",
                f"{len(changes)} изменений в составах!\n\nНажмите 'Changes Log' для деталей."
            ))

    def highlight_changes(self, changes):
        """Подсветка изменённых команд в UI."""
        # Обновляем статус
        self.status_label.config(
            text=f"{len(self.games)} games | {len(changes)} CHANGES!",
            fg='#e94560'
        )

        # Звуковой сигнал
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except:
            self.root.bell()

        # Мигание заголовка окна
        self.flash_window(5)

        # Показываем всплывающее окно с изменениями
        self.show_changes_popup(changes)

    def flash_window(self, times):
        """Мигание окна для привлечения внимания."""
        if times <= 0:
            return

        current_title = self.root.title()
        if "!!!" in current_title:
            self.root.title("NBA Lineups - Today's Games")
        else:
            self.root.title("!!! LINEUP CHANGED !!! NBA Lineups")

        self.root.after(500, lambda: self.flash_window(times - 1))

    def show_changes_popup(self, changes):
        """Показ всплывающего окна с изменениями."""
        popup = tk.Toplevel(self.root)
        popup.title("LINEUP CHANGED!")
        popup.geometry("450x300")
        popup.configure(bg='#e94560')
        popup.attributes('-topmost', True)  # Поверх всех окон

        # Заголовок
        header = tk.Label(popup, text=f"LINEUP CHANGES DETECTED!",
                         font=('Arial', 16, 'bold'), fg='white', bg='#e94560')
        header.pack(pady=15)

        # Количество изменений
        count_label = tk.Label(popup, text=f"{len(changes)} change(s)",
                              font=('Arial', 12), fg='white', bg='#e94560')
        count_label.pack()

        # Список изменений
        changes_frame = tk.Frame(popup, bg='#1a1a2e')
        changes_frame.pack(fill='both', expand=True, padx=15, pady=15)

        for i, ch in enumerate(changes[:10]):  # Максимум 10 изменений
            line = f"{ch['team']} {ch['position']}: {ch['old_player']} -> {ch['new_player']}"
            lbl = tk.Label(changes_frame, text=line,
                          font=('Consolas', 10), fg='white', bg='#1a1a2e',
                          anchor='w')
            lbl.pack(fill='x', padx=10, pady=2)

        if len(changes) > 10:
            more_lbl = tk.Label(changes_frame, text=f"...and {len(changes) - 10} more",
                               font=('Arial', 9, 'italic'), fg='#a0a0a0', bg='#1a1a2e')
            more_lbl.pack(pady=5)

        # Кнопка закрытия
        close_btn = tk.Button(popup, text="OK",
                             command=popup.destroy,
                             bg='white', fg='#e94560',
                             font=('Arial', 12, 'bold'),
                             relief='flat', padx=30, pady=5)
        close_btn.pack(pady=10)

        # Автозакрытие через 30 секунд
        popup.after(30000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def schedule_auto_check(self):
        """Планирование автоматической проверки."""
        if self.auto_check_enabled:
            self.check_job = self.root.after(CHECK_INTERVAL_MS, self.auto_check)

    def auto_check(self):
        """Автоматическая проверка изменений."""
        if not self.auto_check_enabled:
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Автопроверка...")
        self.status_label.config(text="Checking...", fg='#ffd93d')

        # Загружаем данные в фоне
        thread = threading.Thread(target=self._auto_fetch_and_check, daemon=True)
        thread.start()

    def _auto_fetch_and_check(self):
        """Фоновая загрузка и проверка."""
        try:
            soup = fetch_page(ROTOWIRE_URL)
            new_games = parse_lineups(soup)

            if new_games:
                old_games = self.games
                self.games = new_games

                # Проверяем изменения
                self.root.after(0, self._check_and_update)

        except Exception as e:
            print(f"Ошибка автопроверки: {e}")
            self.root.after(0, lambda: self.status_label.config(
                text=f"Error: {e}", fg='#ff6b6b'
            ))

        # Планируем следующую проверку
        self.root.after(0, self.schedule_auto_check)

    def _check_and_update(self):
        """Проверка изменений и обновление UI."""
        changes = self.check_for_changes()

        if changes:
            # Перерисовываем UI
            self._update_ui()
            print(f"Найдено {len(changes)} изменений!")
        else:
            # Просто обновляем статус
            self.status_label.config(
                text=f"{len(self.games)} games | Last check: {datetime.now().strftime('%H:%M')}",
                fg='#a0a0a0'
            )

    def toggle_auto_check(self):
        """Включение/выключение автопроверки."""
        self.auto_check_enabled = self.auto_check_var.get()
        if self.auto_check_enabled:
            self.schedule_auto_check()
            print("Автопроверка включена")
        else:
            if self.check_job:
                self.root.after_cancel(self.check_job)
            print("Автопроверка выключена")

    def show_changes_log(self):
        """Показ окна с логом изменений."""
        log_window = tk.Toplevel(self.root)
        log_window.title("Lineup Changes Log")
        log_window.geometry("600x400")
        log_window.configure(bg='#1a1a2e')

        # Заголовок
        header = tk.Label(log_window, text="Recent Lineup Changes",
                         font=('Arial', 14, 'bold'), fg='#e94560', bg='#1a1a2e')
        header.pack(pady=10)

        # Текстовое поле с логом
        text_frame = tk.Frame(log_window, bg='#1a1a2e')
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')

        log_text = tk.Text(text_frame, bg='#16213e', fg='white',
                          font=('Consolas', 10), yscrollcommand=scrollbar.set)
        log_text.pack(fill='both', expand=True)
        scrollbar.config(command=log_text.yview)

        if not self.changes_log:
            log_text.insert('end', "No changes detected yet.\n\n")
            log_text.insert('end', "The system will notify you when:\n")
            log_text.insert('end', "- A starter is replaced by another player\n")
            log_text.insert('end', "- A player moves to a different position\n")
        else:
            # Показываем изменения от новых к старым
            for change in reversed(self.changes_log[-50:]):
                line = f"[{change['time']}] {change['game']} | {change['team']} {change['position']}: "
                line += f"{change['old_player']} -> {change['new_player']}\n"
                log_text.insert('end', line)

        log_text.config(state='disabled')

        # Кнопка очистки
        clear_btn = tk.Button(log_window, text="Clear Log",
                             command=lambda: self.clear_changes_log(log_text),
                             bg='#e94560', fg='white',
                             font=('Arial', 10, 'bold'), relief='flat')
        clear_btn.pack(pady=10)

    def clear_changes_log(self, text_widget):
        """Очистка лога изменений."""
        self.changes_log = []
        self.save_cache()
        text_widget.config(state='normal')
        text_widget.delete('1.0', 'end')
        text_widget.insert('end', "Log cleared.\n")
        text_widget.config(state='disabled')

    def simulate_change(self):
        """Симуляция изменения состава для тестирования."""
        import random

        if not self.games:
            messagebox.showwarning("No Data", "Сначала загрузите данные!")
            return

        # Выбираем случайную игру и команду
        game = random.choice(self.games)
        team_type = random.choice(['away_team', 'home_team'])
        team = game.get(team_type, {})
        lineup = team.get('lineup', [])

        if len(lineup) < 2:
            messagebox.showwarning("No Players", "Недостаточно игроков для симуляции!")
            return

        # Находим стартера для замены
        starters = [p for p in lineup if p.get('position') in POSITIONS_ORDER and p.get('status', 'active') != 'out']
        if not starters:
            return

        # Выбираем игрока для "замены"
        player_to_change = random.choice(starters)
        old_name = player_to_change.get('name', 'Unknown')
        position = player_to_change.get('position', 'PG')

        # Генерируем "нового" игрока
        fake_names = [
            "Test Player", "John Doe", "Jane Smith", "Mike Johnson",
            "Chris Williams", "Alex Brown", "Sam Davis", "Jordan Lee"
        ]
        new_name = random.choice([n for n in fake_names if n != old_name])

        # Создаём фейковое изменение
        change = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'game': self.get_game_key(game),
            'team': team.get('abbrev', '???'),
            'position': position,
            'old_player': old_name,
            'new_player': new_name
        }

        # Добавляем в лог
        self.changes_log.append(change)
        self.save_cache()

        # Показываем уведомление
        self.show_notification([change])

        # Обновляем статус
        self.highlight_changes([change])

        print(f"ТЕСТ: {change['team']} {position}: {old_name} -> {new_name}")

    def compare_with_last_game(self):
        """Сравнение текущих составов с предыдущей игрой через NBA API."""
        if not self.games:
            messagebox.showwarning("No Data", "Сначала загрузите данные!")
            return

        # Показываем статус загрузки
        self.status_label.config(text="Loading historical data...", fg='#ffd93d')
        self.compare_btn.config(state='disabled')

        # Запускаем в фоне
        thread = threading.Thread(target=self._fetch_and_compare, daemon=True)
        thread.start()

    def _fetch_and_compare(self):
        """Фоновая загрузка и сравнение с использованием кэша."""
        try:
            # Собираем все команды из текущих игр
            teams_to_check = set()
            for game in self.games:
                teams_to_check.add(game.get('away_team', {}).get('abbrev'))
                teams_to_check.add(game.get('home_team', {}).get('abbrev'))

            teams_to_check.discard(None)

            # Получаем данные о последних играх (с использованием кэша)
            historical_data = {}
            teams_from_cache = 0
            teams_fetched = 0

            for team in teams_to_check:
                # Проверяем кэш
                if self.is_historical_cache_valid(team):
                    # Используем данные из кэша
                    historical_data[team] = self.historical_cache[team]
                    teams_from_cache += 1
                    print(f"  {team}: из кэша")
                else:
                    # Загружаем свежие данные
                    print(f"  {team}: загрузка...")
                    data = get_team_last_game_starters_nba_api(team, '2025-26')
                    if data:
                        # Добавляем время кэширования
                        data['cached_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        historical_data[team] = data
                        self.historical_cache[team] = data
                        teams_fetched += 1

            # Сохраняем обновленный кэш
            if teams_fetched > 0:
                self.save_historical_cache()

            print(f"Итого: {teams_from_cache} из кэша, {teams_fetched} загружено")

            # Сравниваем и показываем результат
            self.root.after(0, lambda: self._show_comparison_results(historical_data))

        except Exception as e:
            print(f"Ошибка сравнения: {e}")
            self.root.after(0, lambda: self.status_label.config(
                text=f"Error: {e}", fg='#ff6b6b'
            ))

        self.root.after(0, lambda: self.compare_btn.config(state='normal'))

    def _show_comparison_results(self, historical_data):
        """Показ результатов сравнения."""
        # Создаём окно с результатами
        compare_window = tk.Toplevel(self.root)
        compare_window.title("Comparison with Last Game")
        compare_window.geometry("800x600")
        compare_window.configure(bg='#1a1a2e')

        # Заголовок
        header = tk.Label(compare_window, text="Current vs Last Game Starters",
                         font=('Arial', 16, 'bold'), fg='#6bcb77', bg='#1a1a2e')
        header.pack(pady=15)

        # Скроллируемый фрейм
        container = tk.Frame(compare_window, bg='#1a1a2e')
        container.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')
        scrollable_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Для каждой команды показываем сравнение
        changes_found = 0

        for game in self.games:
            for team_type in ['away_team', 'home_team']:
                team_data = game.get(team_type, {})
                team_abbrev = team_data.get('abbrev')

                if not team_abbrev or team_abbrev not in historical_data:
                    continue

                hist = historical_data[team_abbrev]

                # Текущие стартеры
                current_starters = self.get_starters(team_data.get('lineup', []))
                current_names = set(current_starters.values())

                # Прошлые стартеры
                past_names = set(hist.get('starters_names', []))

                # Если есть изменения
                new_players = current_names - past_names
                removed_players = past_names - current_names

                if new_players or removed_players:
                    changes_found += 1

                    # Создаём карточку команды
                    team_frame = tk.Frame(scrollable_frame, bg='#16213e', relief='flat')
                    team_frame.pack(fill='x', padx=5, pady=5)

                    # Заголовок команды
                    team_header = tk.Label(team_frame,
                                          text=f"{team_abbrev} - Changes from {hist.get('date', 'N/A')}",
                                          font=('Arial', 12, 'bold'),
                                          fg='#e94560', bg='#16213e')
                    team_header.pack(anchor='w', padx=10, pady=5)

                    # Прошлая игра
                    last_game_info = tk.Label(team_frame,
                                             text=f"Last: {hist.get('matchup', '')} ({hist.get('result', '')})",
                                             font=('Arial', 9), fg='#a0a0a0', bg='#16213e')
                    last_game_info.pack(anchor='w', padx=10)

                    # Новые игроки (зелёные)
                    if new_players:
                        new_label = tk.Label(team_frame,
                                            text=f"+ NEW: {', '.join(new_players)}",
                                            font=('Arial', 10, 'bold'),
                                            fg='#6bcb77', bg='#16213e')
                        new_label.pack(anchor='w', padx=15, pady=2)

                    # Выбывшие (красные)
                    if removed_players:
                        removed_label = tk.Label(team_frame,
                                                text=f"- OUT: {', '.join(removed_players)}",
                                                font=('Arial', 10, 'bold'),
                                                fg='#ff6b6b', bg='#16213e')
                        removed_label.pack(anchor='w', padx=15, pady=2)

        # Итог
        if changes_found == 0:
            no_changes = tk.Label(scrollable_frame,
                                 text="No lineup changes detected from last games!",
                                 font=('Arial', 14), fg='#6bcb77', bg='#1a1a2e')
            no_changes.pack(pady=50)

        # Обновляем статус
        self.status_label.config(
            text=f"{len(self.games)} games | {changes_found} teams with changes",
            fg='#a0a0a0'
        )

    def show_team_stats(self, team_abbrev, opponent_abbrev=None, is_home=None):
        """Показ статистики команды за последние 5 игр."""
        # Показываем статус
        self.status_label.config(text=f"Loading {team_abbrev} stats...", fg='#ffd93d')

        # Запускаем в фоне
        thread = threading.Thread(
            target=self._fetch_team_stats,
            args=(team_abbrev, opponent_abbrev, is_home),
            daemon=True
        )
        thread.start()

    def _fetch_team_stats(self, team_abbrev, opponent_abbrev=None, is_home=None):
        """Фоновая загрузка статистики команды с кэшированием."""
        try:
            # Проверяем кэш
            if self.is_team_stats_cache_valid(team_abbrev):
                print(f"Статистика {team_abbrev}: из кэша")
                data = self.team_stats_cache[team_abbrev]
                self.root.after(0, lambda: self._show_team_stats_window(data, opponent_abbrev, is_home))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"{len(self.games)} games today (cached)", fg='#a0a0a0'
                ))
                return

            # Загружаем с API
            print(f"Загрузка статистики {team_abbrev} с API...")
            data = get_team_last_n_games_stats(team_abbrev, n_games=10, season='2025-26')

            if data:
                # Добавляем метку времени и сохраняем в кэш
                data['cached_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.team_stats_cache[team_abbrev] = data
                self.save_team_stats_cache()

                self.root.after(0, lambda: self._show_team_stats_window(data, opponent_abbrev, is_home))
            else:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"No data for {team_abbrev}", fg='#ff6b6b'
                ))

        except Exception as e:
            print(f"Ошибка загрузки статистики: {e}")
            self.root.after(0, lambda: self.status_label.config(
                text=f"Error: {e}", fg='#ff6b6b'
            ))

        self.root.after(0, lambda: self.status_label.config(
            text=f"{len(self.games)} games today", fg='#a0a0a0'
        ))

    def preload_all_teams_stats(self):
        """Предзагрузка статистики всех команд сегодняшних игр в фоне."""
        if not self.games:
            return

        # Собираем все команды из сегодняшних игр
        teams_to_preload = set()
        for game in self.games:
            away = game.get('away_team', {}).get('abbrev')
            home = game.get('home_team', {}).get('abbrev')
            if away:
                teams_to_preload.add(away)
            if home:
                teams_to_preload.add(home)

        if not teams_to_preload:
            return

        print(f"Предзагрузка статистики для {len(teams_to_preload)} команд...")
        self.status_label.config(text=f"Preloading stats for {len(teams_to_preload)} teams...", fg='#ffd93d')

        # Запускаем в фоновом потоке
        thread = threading.Thread(
            target=self._preload_teams_stats_thread,
            args=(list(teams_to_preload),),
            daemon=True
        )
        thread.start()

    def _preload_teams_stats_thread(self, teams):
        """Фоновая загрузка статистики команд."""
        loaded = 0
        cached = 0
        total = len(teams)

        for team_abbrev in teams:
            try:
                # Проверяем кэш
                is_valid = self.is_team_stats_cache_valid(team_abbrev)
                if is_valid:
                    cached += 1
                    # Получаем время кэша для отладки
                    cached_time = self.team_stats_cache.get(team_abbrev, {}).get('cached_at', 'unknown')
                    print(f"  {team_abbrev}: из кэша ({cached + loaded}/{total}) [кэширован: {cached_time}]")
                else:
                    # Загружаем с API
                    in_cache = team_abbrev in self.team_stats_cache
                    print(f"  {team_abbrev}: загрузка... ({cached + loaded}/{total}) [в кэше: {in_cache}]")
                    data = get_team_last_n_games_stats(team_abbrev, n_games=10, season='2025-26')

                    if data:
                        data['cached_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.team_stats_cache[team_abbrev] = data
                        loaded += 1

                # Обновляем статус в UI
                self.root.after(0, lambda c=cached, l=loaded, t=total: self.status_label.config(
                    text=f"Preloading stats... {c + l}/{t}", fg='#ffd93d'
                ))

            except Exception as e:
                print(f"  {team_abbrev}: ошибка - {e}")

        # Сохраняем кэш после загрузки
        if loaded > 0:
            self.save_team_stats_cache()

        # Финальный статус
        self.root.after(0, lambda: self.status_label.config(
            text=f"{len(self.games)} games today | Stats preloaded ({cached} cached, {loaded} loaded)",
            fg='#6bcb77'
        ))
        print(f"Предзагрузка завершена: {cached} из кэша, {loaded} загружено")

    def _show_team_stats_window(self, data, opponent_abbrev=None, is_home=None):
        """Показ окна со статистикой команды."""
        team_abbrev = data['team']
        team_name = data.get('team_name', team_abbrev)
        games = data.get('games', [])

        colors = TEAM_COLORS.get(team_abbrev, {'primary': '#333333', 'secondary': '#666666'})

        # Создаём окно (увеличили ширину для AI панели)
        stats_window = tk.Toplevel(self.root)
        stats_window.title(f"{team_abbrev} - Last 5 Games Stats")
        stats_window.geometry("1300x750")
        stats_window.configure(bg='#1a1a2e')

        # Заголовок
        header_frame = tk.Frame(stats_window, bg=colors['primary'])
        header_frame.pack(fill='x')

        header = tk.Label(header_frame, text=f"{team_name}",
                         font=('Arial', 18, 'bold'), fg='white', bg=colors['primary'])
        header.pack(pady=15)

        sub_title = "Starting Lineup - Last 5 Games"
        if opponent_abbrev:
            sub_title += f" | Next: vs {opponent_abbrev}"
        sub_header = tk.Label(header_frame, text=sub_title,
                             font=('Arial', 11), fg='#cccccc', bg=colors['primary'])
        sub_header.pack(pady=(0, 5))

        # Подсказка о кликабельности
        hint = tk.Label(header_frame, text="Click on player name for AI projection",
                       font=('Arial', 9, 'italic'), fg='#9b59b6', bg=colors['primary'])
        hint.pack(pady=(0, 10))

        # Основной контейнер - разделим на две части
        main_container = tk.Frame(stats_window, bg='#1a1a2e')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Левая панель - статистика игроков
        left_panel = tk.Frame(main_container, bg='#1a1a2e')
        left_panel.pack(side='left', fill='both', expand=False)

        # Правая панель - AI анализ команды
        right_panel = tk.Frame(main_container, bg='#16213e', width=400)
        right_panel.pack(side='right', fill='both', expand=True, padx=(10, 0))
        right_panel.pack_propagate(False)

        # Контейнер для скролла статистики
        container = tk.Frame(left_panel, bg='#1a1a2e')
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)

        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')
        scrollable_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Для каждой игры создаём блок
        for i, game in enumerate(games):
            game_frame = tk.Frame(scrollable_frame, bg='#16213e')
            game_frame.pack(fill='x', padx=5, pady=8)

            # Заголовок игры
            result_color = '#6bcb77' if game['result'] == 'W' else '#ff6b6b'
            game_header = tk.Frame(game_frame, bg='#0f3460')
            game_header.pack(fill='x')

            game_info = tk.Label(game_header,
                                text=f"Game {i+1}: {game['matchup']} | {game['date']}",
                                font=('Arial', 11, 'bold'),
                                fg='white', bg='#0f3460')
            game_info.pack(side='left', padx=10, pady=8)

            result_label = tk.Label(game_header,
                                   text=game['result'],
                                   font=('Arial', 14, 'bold'),
                                   fg=result_color, bg='#0f3460')
            result_label.pack(side='right', padx=15, pady=8)

            # Таблица со статистикой
            stats_frame = tk.Frame(game_frame, bg='#1a1a2e')
            stats_frame.pack(fill='x', padx=5, pady=5)

            # Заголовок таблицы
            headers = ['POS', 'PLAYER', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK']
            header_row = tk.Frame(stats_frame, bg='#0f3460')
            header_row.pack(fill='x')

            col_widths = [4, 20, 6, 5, 5, 5, 5, 5]
            for j, (h, w) in enumerate(zip(headers, col_widths)):
                lbl = tk.Label(header_row, text=h, font=('Arial', 9, 'bold'),
                              fg='#a0a0a0', bg='#0f3460', width=w, anchor='center')
                lbl.pack(side='left', padx=1)

            # Строки с игроками
            for starter in game['starters']:
                player_row = tk.Frame(stats_frame, bg='#16213e')
                player_row.pack(fill='x')

                # Позиция
                pos_lbl = tk.Label(player_row, text=starter['position'], font=('Consolas', 10),
                                  fg='white', bg='#16213e', width=col_widths[0], anchor='center')
                pos_lbl.pack(side='left', padx=1)

                # Имя игрока (кликабельное)
                player_name = starter['name']
                player_position = starter['position']
                name_lbl = tk.Label(player_row, text=player_name[:18], font=('Consolas', 10, 'underline'),
                                   fg='#9b59b6', bg='#16213e', width=col_widths[1], anchor='w', cursor='hand2')
                name_lbl.pack(side='left', padx=1)

                # Привязываем клик к имени
                name_lbl.bind('<Button-1>', lambda e, pn=player_name, pp=player_position, ta=team_abbrev, g=games, oa=opponent_abbrev, ih=is_home:
                             self._on_player_click(pn, pp, ta, g, oa, ih))
                name_lbl.bind('<Enter>', lambda e, lbl=name_lbl: lbl.config(fg='#c39bd3'))
                name_lbl.bind('<Leave>', lambda e, lbl=name_lbl: lbl.config(fg='#9b59b6'))

                # Остальные статы
                mins = starter['min'] if starter['min'] else '-'
                pts_color = '#ffd93d' if starter['pts'] >= 20 else 'white'
                reb_color = '#6bcb77' if starter['reb'] >= 10 else 'white'
                ast_color = '#4fc3f7' if starter['ast'] >= 8 else 'white'

                stat_values = [mins, str(starter['pts']), str(starter['reb']), str(starter['ast']),
                              str(starter['stl']), str(starter['blk'])]
                stat_colors = ['#a0a0a0', pts_color, reb_color, ast_color, 'white', 'white']
                stat_widths = col_widths[2:]

                for val, w, col in zip(stat_values, stat_widths, stat_colors):
                    lbl = tk.Label(player_row, text=val, font=('Consolas', 10),
                                  fg=col, bg='#16213e', width=w, anchor='center')
                    lbl.pack(side='left', padx=1)

        # Получаем текущий состав команды на сегодня (кто играет, кто травмирован)
        current_lineup = self._get_team_current_lineup(team_abbrev)

        # Добавляем AI анализ команды в правую панель
        self._add_team_ai_analysis(right_panel, team_abbrev, games, opponent_abbrev, colors, current_lineup)

        # Кнопка закрытия
        close_btn = tk.Button(stats_window, text="Close",
                             command=stats_window.destroy,
                             bg=colors['primary'], fg='white',
                             font=('Arial', 11, 'bold'),
                             relief='flat', padx=30, pady=8)
        close_btn.pack(pady=15)

    def _get_team_current_lineup(self, team_abbrev):
        """Получает текущий состав команды на сегодня из главного окна."""
        lineup = {'active': [], 'injured': [], 'out': []}

        for game in self.games:
            away_team = game.get('away_team', {})
            home_team = game.get('home_team', {})

            target_team = None
            if away_team.get('abbrev') == team_abbrev:
                target_team = away_team
            elif home_team.get('abbrev') == team_abbrev:
                target_team = home_team

            if target_team:
                for player in target_team.get('lineup', []):
                    status = player.get('status', 'active')
                    name = player.get('name', '')

                    if status == 'active':
                        lineup['active'].append(name)
                    elif status in ['out', 'doubtful']:
                        lineup['out'].append(name)
                    elif status in ['questionable', 'probable']:
                        lineup['injured'].append(name)

                # Также проверяем травмированных
                for injury in target_team.get('injuries', []):
                    injured_name = injury.get('name', '')
                    if injured_name and injured_name not in lineup['out']:
                        lineup['out'].append(injured_name)

                break

        return lineup

    def _add_team_ai_analysis(self, panel, team_abbrev, games, opponent_abbrev, colors, current_lineup=None):
        """Добавляет AI анализ команды в правую панель."""
        # Заголовок панели
        ai_header = tk.Label(panel, text="🤖 Team AI Analysis",
                            font=('Arial', 14, 'bold'), fg='#9b59b6', bg='#16213e')
        ai_header.pack(pady=(10, 5))

        # Описание
        desc = tk.Label(panel, text="AI прогноз перераспределения нагрузки",
                       font=('Arial', 9, 'italic'), fg='#a0a0a0', bg='#16213e')
        desc.pack(pady=(0, 10))

        # Контейнер для текста с прокруткой
        text_frame = tk.Frame(panel, bg='#16213e')
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)

        canvas = tk.Canvas(text_frame, bg='#16213e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=canvas.yview)

        scrollable = tk.Frame(canvas, bg='#16213e')
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Показываем индикатор загрузки
        loading_label = tk.Label(scrollable, text="AI анализирует состав команды...",
                                font=('Arial', 10), fg='#9b59b6', bg='#16213e')
        loading_label.pack(pady=50)

        # Запускаем AI анализ в фоне
        thread = threading.Thread(
            target=self._run_team_ai_analysis_thread,
            args=(scrollable, loading_label, team_abbrev, games, opponent_abbrev, current_lineup),
            daemon=True
        )
        thread.start()

    def _run_team_ai_analysis_thread(self, container, loading_label, team_abbrev, games, opponent_abbrev, current_lineup=None):
        """Фоновый AI анализ команды."""
        try:
            print(f"[DEBUG TEAM] Начало анализа команды {team_abbrev}")

            if not self.ai_enabled:
                print(f"[DEBUG TEAM] AI не включен")
                self.root.after(0, lambda: loading_label.config(
                    text="AI анализ недоступен\n\nНастройте OPENAI_API_KEY в .env файле"))
                return

            print(f"[DEBUG TEAM] Формирование промпта...")
            # Формируем данные для анализа
            analysis_prompt = self._build_team_analysis_prompt(team_abbrev, games, opponent_abbrev, current_lineup)
            print(f"[DEBUG TEAM] Промпт создан, длина: {len(analysis_prompt)}")

            # Получаем AI анализ (используем существующую функцию)
            from ai_analyzer import client
            if not client:
                print(f"[DEBUG TEAM] Инициализация OpenAI клиента...")
                from ai_analyzer import init_openai
                init_openai()

            from ai_analyzer import client
            if not client:
                raise Exception("AI клиент не инициализирован")

            print(f"[DEBUG TEAM] Отправка запроса к OpenAI...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты NBA аналитик. Анализируешь составы команд и прогнозируешь перераспределение игровой нагрузки. ВАЖНО: работай ТОЛЬКО с фактическими данными из промпта. НЕ делай предположений о возможных травмах или изменениях, если они не указаны явно."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=400,
                temperature=0.7,
                timeout=30
            )

            analysis_text = response.choices[0].message.content
            print(f"[DEBUG TEAM] Получен ответ от AI, длина: {len(analysis_text)}")

            # Обновляем UI
            print(f"[DEBUG TEAM] Обновление UI...")
            self.root.after(0, lambda: self._display_team_analysis(container, loading_label, analysis_text))
            print(f"[DEBUG TEAM] UI обновлен!")

        except Exception as e:
            print(f"[DEBUG TEAM] Ошибка AI анализа команды: {e}")
            import traceback
            traceback.print_exc()
            error_msg = str(e)[:100]
            self.root.after(0, lambda: loading_label.config(
                text=f"Ошибка AI анализа:\n{error_msg}"))

    def _build_team_analysis_prompt(self, team_abbrev, games, opponent_abbrev, current_lineup=None):
        """Формирует промпт для AI анализа команды."""
        # Собираем статистику стартовых пятерок
        starters_stats = {}

        for game_idx, game in enumerate(games[:5], 1):
            for starter in game.get('starters', []):
                name = starter['name']
                if name not in starters_stats:
                    starters_stats[name] = {
                        'games': [],
                        'avg_pts': 0,
                        'avg_min': 0
                    }

                starters_stats[name]['games'].append({
                    'pts': starter.get('pts', 0),
                    'min': starter.get('min', '0'),
                    'matchup': game.get('matchup', 'N/A')
                })

        # Вычисляем средние показатели
        for name, data in starters_stats.items():
            total_pts = sum(g['pts'] for g in data['games'])
            data['avg_pts'] = total_pts / len(data['games']) if data['games'] else 0

        # Сортируем по средним очкам
        sorted_players = sorted(starters_stats.items(), key=lambda x: x[1]['avg_pts'], reverse=True)

        # Получаем новости о команде
        from news_scraper import get_news_by_team
        team_news = get_news_by_team(team_abbrev, limit=5)

        # Формируем промпт
        prompt = f"""Проанализируй текущий состав команды {team_abbrev} на основе последних 5 игр и актуальных новостей.

СТАТИСТИКА ОСНОВНЫХ ИГРОКОВ (последние 5 игр, по средним очкам):
"""
        for name, stats in sorted_players[:7]:
            prompt += f"\n- {name}: {stats['avg_pts']:.1f} очков/игру"

        # Добавляем информацию о текущем составе (кто травмирован)
        if current_lineup:
            if current_lineup['out']:
                prompt += f"\n\n⚠️ ВЫБЫВШИЕ ИГРОКИ НА СЕГОДНЯ:"
                for player in current_lineup['out']:
                    # Проверяем, был ли этот игрок ключевым
                    is_key = any(player == name for name, _ in sorted_players[:3])
                    marker = " (КЛЮЧЕВОЙ ИГРОК!)" if is_key else ""
                    prompt += f"\n- {player}{marker}"

            if current_lineup['injured']:
                prompt += f"\n\n🤕 ПОД ВОПРОСОМ:"
                for player in current_lineup['injured']:
                    prompt += f"\n- {player}"

        # Добавляем новости
        if team_news:
            prompt += f"\n\nАКТУАЛЬНЫЕ НОВОСТИ О КОМАНДЕ (последние 3 дня):"
            for news in team_news[:3]:
                title = news.get('title', '')
                prompt += f"\n• {title}"
        else:
            prompt += f"\n\nАКТУАЛЬНЫЕ НОВОСТИ: Актуальных новостей нет"

        if opponent_abbrev:
            prompt += f"\n\nСЛЕДУЮЩИЙ СОПЕРНИК: {opponent_abbrev}"

        prompt += f"""

ЗАДАЧА:
1. **Анализ текущего состава**:
   - Определи ключевых игроков (топ-2 по очкам)
   - ЕСЛИ есть выбывшие ключевые игроки → проанализируй КТО возьмет на себя их нагрузку
   - Используй ТОЛЬКО РЕАЛЬНЫЕ данные о травмах выше

2. **Перераспределение нагрузки**:
   - Если ключевой игрок выбыл → кто из АКТИВНЫХ игроков получит больше бросков?
   - На сколько увеличится нагрузка на оставшихся лидеров? (конкретные проценты/очки)

3. **Прогноз на игру**:
   - Как выбывшие повлияют на результат команды?
   - Сильно ли это ослабит команду или есть глубокая скамейка?

⚠️ КРИТИЧЕСКИ ВАЖНО - РАБОТАЙ ТОЛЬКО С ФАКТАМИ:
- ЕСЛИ в данных НЕТ информации о выбывших игроках → НЕ ПИШИ о травмах и заменах
- ЕСЛИ нет актуальных новостей → просто укажи "новостей нет", НЕ предполагай ничего
- ЕСЛИ состав ПОЛНЫЙ и без изменений → так и напиши "состав без изменений"
- НЕ делай абстрактных предположений типа "если кто-то выбудет" - пиши только о реальных фактах
- Работай ТОЛЬКО с теми данными, которые указаны выше в промпте

Ответ на русском, структурированно, КОНКРЕТНО (с цифрами), максимум 350 слов."""

        return prompt

    def _display_team_analysis(self, container, loading_label, analysis_text):
        """Отображает результат AI анализа."""
        loading_label.destroy()

        text_widget = tk.Text(container, wrap='word', font=('Arial', 10),
                             bg='#16213e', fg='white', relief='flat',
                             padx=10, pady=10, height=30)
        text_widget.pack(fill='both', expand=True)
        text_widget.insert('1.0', analysis_text)
        text_widget.config(state='disabled')

    def _handle_main_window_player_click(self, player):
        """Обработка клика на игрока из главного окна."""
        # Извлекаем данные из player dict
        player_name = player.get('name', 'Unknown')
        player_position = player.get('position', '?')

        # Находим команду игрока и соперника из текущих игр
        team_abbrev = None
        opponent_abbrev = None
        is_home = None
        team_injuries = []

        for game in self.games:
            away_team = game.get('away_team', {})
            home_team = game.get('home_team', {})

            # Проверяем гостевую команду
            for p in away_team.get('lineup', []):
                if p.get('name') == player_name:
                    team_abbrev = away_team.get('abbrev')
                    opponent_abbrev = home_team.get('abbrev')
                    is_home = False
                    # Извлекаем РЕАЛЬНО травмированных игроков (только OUT и DOUBTFUL)
                    # PROBABLE и QUESTIONABLE - игрок скорее всего будет играть
                    team_injuries = [
                        pl.get('name') for pl in away_team.get('lineup', [])
                        if pl.get('status') in ['out', 'doubtful']
                    ]
                    break

            # Проверяем домашнюю команду
            if not team_abbrev:
                for p in home_team.get('lineup', []):
                    if p.get('name') == player_name:
                        team_abbrev = home_team.get('abbrev')
                        opponent_abbrev = away_team.get('abbrev')
                        is_home = True
                        # Извлекаем РЕАЛЬНО травмированных игроков (только OUT и DOUBTFUL)
                        team_injuries = [
                            pl.get('name') for pl in home_team.get('lineup', [])
                            if pl.get('status') in ['out', 'doubtful']
                        ]
                        break

            if team_abbrev:
                break

        if not team_abbrev:
            messagebox.showerror("Ошибка", f"Не удалось найти команду для игрока {player_name}")
            return

        # Получаем статистику команды из кеша
        team_data = self.team_stats_cache.get(team_abbrev, {})
        team_games = team_data.get('games', [])

        if not team_games:
            # Если нет в кеше - загружаем
            messagebox.showinfo("Загрузка данных",
                              f"Загружаю статистику {team_abbrev}...\nПожалуйста, подождите.")
            team_stats = get_team_last_n_games_stats(team_abbrev, n_games=10)
            team_games = team_stats.get('games', [])
            self.team_stats_cache[team_abbrev] = {'games': team_games}

        # Вызываем основную функцию анализа
        self._on_player_click(player_name, player_position, team_abbrev, team_games, opponent_abbrev, is_home, team_injuries)

    def _handle_player_label_click(self, event):
        """Обработчик клика на label игрока."""
        widget = event.widget
        print(f"[CLICK] {widget.player_data.get('name', '?')}")
        self._on_player_click(widget.player_data)

    def _handle_player_label_enter(self, event):
        """Обработчик наведения на label игрока."""
        widget = event.widget
        print(f"[ENTER] {widget.player_data.get('name', '?')}")
        widget.config(fg='#4fc3f7')

    def _handle_player_label_leave(self, event):
        """Обработчик ухода мыши с label игрока."""
        widget = event.widget
        widget.config(fg=widget.original_color)

    def _on_player_click(self, *args):
        """Обработка клика на имени игрока - запуск AI анализа.

        Может быть вызвана двумя способами:
        1. Из окна статистики команды: (player_name, player_position, team_abbrev, games, opponent_abbrev, is_home, team_injuries)
        2. Из главного окна составов: (player_dict,)
        """
        if not self.ai_enabled:
            messagebox.showwarning("AI недоступен",
                                   "AI анализ недоступен.\n\nСоздайте файл .env с вашим OpenAI API ключом:\nOPENAI_API_KEY=sk-...")
            return

        # Определяем откуда вызвана функция
        if len(args) == 1 and isinstance(args[0], dict):
            # Вызов из главного окна - получаем данные игрока
            self._handle_main_window_player_click(args[0])
            return

        # Вызов из окна статистики команды
        player_name, player_position, team_abbrev, games, opponent_abbrev, is_home, team_injuries = args if len(args) == 7 else (*args, [])

        # Собираем статистику игрока из всех игр
        # Если игрок не найден в игре - значит был травмирован
        player_stats = []
        for game_idx, game in enumerate(games, 1):
            player_found = False
            # Check all players (starters + bench) - use all_players field
            all_players = game.get('all_players', game.get('starters', []))
            for player in all_players:
                # Compare by last name + first letter (handles "S. Gilgeous-Alexander" vs "Shai Gilgeous-Alexander")
                if names_match(player['name'], player_name):
                    player_stats.append({
                        'matchup': game.get('matchup', 'N/A'),
                        'date': game.get('date', ''),
                        'pts': player.get('pts', 0),
                        'reb': player.get('reb', 0),
                        'ast': player.get('ast', 0),
                        'stl': player.get('stl', 0),
                        'blk': player.get('blk', 0),
                        'min': player.get('min', 0),  # Передаём как есть (строка "MM:SS"), парсинг в ai_analyzer
                        'injured': False
                    })
                    player_found = True
                    break

            # Если игрок не найден в этой игре - был травмирован
            if not player_found:
                player_stats.append({
                    'matchup': game.get('matchup', 'N/A'),
                    'date': game.get('date', ''),
                    'pts': 0,
                    'reb': 0,
                    'ast': 0,
                    'stl': 0,
                    'blk': 0,
                    'min': 0,
                    'injured': True  # Флаг травмы
                })

        # Показываем окно загрузки
        self.player_loading_window = tk.Toplevel(self.root)
        self.player_loading_window.title("AI Player Projection")
        self.player_loading_window.geometry("400x150")
        self.player_loading_window.configure(bg='#1a1a2e')
        self.player_loading_window.resizable(False, False)
        self.player_loading_window.transient(self.root)
        self.player_loading_window.grab_set()

        colors = TEAM_COLORS.get(team_abbrev, {'primary': '#9b59b6'})

        player_lbl = tk.Label(self.player_loading_window, text=player_name,
                             font=('Arial', 16, 'bold'), fg=colors['primary'], bg='#1a1a2e')
        player_lbl.pack(pady=(20, 5))

        team_lbl = tk.Label(self.player_loading_window, text=f"{team_abbrev} | {player_position}",
                           font=('Arial', 11), fg='#a0a0a0', bg='#1a1a2e')
        team_lbl.pack(pady=5)

        self.player_loading_label = tk.Label(self.player_loading_window, text="AI анализирует...",
                                            font=('Arial', 10), fg='#9b59b6', bg='#1a1a2e')
        self.player_loading_label.pack(pady=10)

        # Анимация
        self.player_loading_dots = 0
        self._animate_player_loading()

        # Получаем статистику соперника
        opponent_stats = self.team_stats_cache.get(opponent_abbrev) if opponent_abbrev else None

        # Запускаем анализ в фоне
        thread = threading.Thread(
            target=self._run_player_analysis_thread,
            args=(player_name, player_position, team_abbrev, player_stats, opponent_abbrev, opponent_stats, is_home, team_injuries, games),
            daemon=True
        )
        thread.start()

    def _animate_player_loading(self):
        """Анимация загрузки для анализа игрока."""
        if hasattr(self, 'player_loading_window') and self.player_loading_window.winfo_exists():
            self.player_loading_dots = (self.player_loading_dots + 1) % 4
            dots = "." * self.player_loading_dots
            self.player_loading_label.config(text=f"AI анализирует{dots}")
            self.root.after(400, self._animate_player_loading)

    def _run_player_analysis_thread(self, player_name, player_position, team_abbrev, player_stats,
                                    opponent_abbrev, opponent_stats, is_home, team_injuries=None, team_games=None):
        """Фоновый AI анализ игрока."""
        try:
            # Извлекаем имена травмированных игроков
            injuries_list = []
            if team_injuries:
                if isinstance(team_injuries, list):
                    for inj in team_injuries:
                        if isinstance(inj, dict):
                            injuries_list.append(inj.get('name', ''))
                        else:
                            injuries_list.append(str(inj))

            result = analyze_player_projection(
                player_name=player_name,
                player_position=player_position,
                team_abbrev=team_abbrev,
                player_stats=player_stats,
                opponent_abbrev=opponent_abbrev or "N/A",
                opponent_stats=opponent_stats,
                is_home=is_home if is_home is not None else True,
                team_injuries=[inj for inj in injuries_list if inj],
                team_games=team_games
            )

            # Распаковываем результат (analysis, prompt)
            analysis, ai_prompt = result if isinstance(result, tuple) else (result, "")

            # Отладка: проверяем что передаётся
            print(f"[DEBUG] AI prompt длина: {len(ai_prompt) if ai_prompt else 0} символов")
            print(f"[DEBUG] AI prompt пустой: {not bool(ai_prompt)}")

            self.root.after(0, lambda: self._show_player_projection_popup(
                player_name, player_position, team_abbrev, player_stats, opponent_abbrev, analysis, ai_prompt
            ))

        except Exception as e:
            print(f"Ошибка AI анализа игрока: {e}")
            self.root.after(0, lambda: self._close_player_loading())

    def _close_player_loading(self):
        """Закрытие окна загрузки анализа игрока."""
        if hasattr(self, 'player_loading_window') and self.player_loading_window.winfo_exists():
            self.player_loading_window.destroy()

    def _show_player_projection_popup(self, player_name, player_position, team_abbrev, player_stats,
                                      opponent_abbrev, analysis, ai_prompt=""):
        """Показ popup с прогнозом по игроку."""
        self._close_player_loading()

        # Отладка
        print(f"[DEBUG] _show_player_projection_popup вызван")
        print(f"[DEBUG] ai_prompt длина: {len(ai_prompt) if ai_prompt else 0}")
        print(f"[DEBUG] ai_prompt bool: {bool(ai_prompt)}")

        colors = TEAM_COLORS.get(team_abbrev, {'primary': '#333333', 'secondary': '#666666'})

        popup = tk.Toplevel(self.root)
        popup.title(f"AI Projection - {player_name}")
        popup.geometry("550x600")
        popup.configure(bg='#1a1a2e')

        # Сохраняем промпт для кнопки
        self.last_ai_prompt = ai_prompt

        # Заголовок
        header_frame = tk.Frame(popup, bg=colors['primary'])
        header_frame.pack(fill='x')

        name_lbl = tk.Label(header_frame, text=player_name,
                           font=('Arial', 16, 'bold'), fg='white', bg=colors['primary'])
        name_lbl.pack(pady=(15, 5))

        info_text = f"{team_abbrev} | {player_position}"
        if opponent_abbrev:
            info_text += f" | vs {opponent_abbrev}"
        info_lbl = tk.Label(header_frame, text=info_text,
                           font=('Arial', 11), fg='#cccccc', bg=colors['primary'])
        info_lbl.pack(pady=(0, 15))

        # Краткая статистика игрока
        if player_stats:
            stats_frame = tk.Frame(popup, bg='#16213e')
            stats_frame.pack(fill='x', padx=15, pady=10)

            avg_pts = sum(g.get('pts', 0) for g in player_stats) / len(player_stats)
            avg_reb = sum(g.get('reb', 0) for g in player_stats) / len(player_stats)
            avg_ast = sum(g.get('ast', 0) for g in player_stats) / len(player_stats)

            avg_lbl = tk.Label(stats_frame,
                              text=f"Last {len(player_stats)} games avg: {avg_pts:.1f} PTS | {avg_reb:.1f} REB | {avg_ast:.1f} AST",
                              font=('Arial', 11, 'bold'), fg='#ffd93d', bg='#16213e')
            avg_lbl.pack(pady=10)

        # AI прогноз
        analysis_frame = tk.Frame(popup, bg='#1a1a2e')
        analysis_frame.pack(fill='both', expand=True, padx=15, pady=10)

        analysis_header = tk.Label(analysis_frame, text="AI Projection",
                                  font=('Arial', 12, 'bold'), fg='#9b59b6', bg='#1a1a2e')
        analysis_header.pack(anchor='w', pady=5)

        text_frame = tk.Frame(analysis_frame, bg='#16213e')
        text_frame.pack(fill='both', expand=True)

        text_widget = tk.Text(text_frame, wrap='word', font=('Arial', 11),
                             bg='#16213e', fg='white', relief='flat',
                             padx=15, pady=15)
        text_widget.pack(fill='both', expand=True)
        text_widget.insert('1.0', analysis)
        text_widget.config(state='disabled')

        # Кнопки внизу
        buttons_frame = tk.Frame(popup, bg='#1a1a2e')
        buttons_frame.pack(pady=15)

        # Кнопка показа промпта
        if ai_prompt:
            show_prompt_btn = tk.Button(buttons_frame, text="Show AI Prompt",
                                       command=lambda: self._show_ai_prompt_window(ai_prompt, player_name),
                                       bg='#2c3e50', fg='white',
                                       font=('Arial', 9),
                                       relief='flat', padx=15, pady=6)
            show_prompt_btn.pack(side='left', padx=5)

        # Кнопка закрытия
        close_btn = tk.Button(buttons_frame, text="Close",
                             command=popup.destroy,
                             bg=colors['primary'], fg='white',
                             font=('Arial', 11, 'bold'),
                             relief='flat', padx=30, pady=8)
        close_btn.pack(side='left', padx=5)

    def _show_ai_prompt_window(self, prompt_text, player_name):
        """Показ окна с AI промптом для отладки."""
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title(f"AI Prompt - {player_name}")
        prompt_window.geometry("800x700")
        prompt_window.configure(bg='#1a1a2e')

        # Заголовок
        header = tk.Label(prompt_window, text=f"AI Prompt для {player_name}",
                         font=('Arial', 14, 'bold'), fg='#9b59b6', bg='#1a1a2e')
        header.pack(pady=15)

        desc = tk.Label(prompt_window, text="Все данные, которые передаются в GPT-4o-mini:",
                       font=('Arial', 10, 'italic'), fg='#a0a0a0', bg='#1a1a2e')
        desc.pack(pady=(0, 10))

        # Текстовое поле с промптом и скроллом
        text_frame = tk.Frame(prompt_window, bg='#16213e')
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')

        text_widget = tk.Text(text_frame, wrap='word', font=('Courier New', 9),
                             bg='#16213e', fg='#00ff00',
                             yscrollcommand=scrollbar.set,
                             padx=15, pady=15)
        text_widget.pack(fill='both', expand=True)
        scrollbar.config(command=text_widget.yview)

        # Вставляем промпт
        text_widget.insert('1.0', prompt_text)
        text_widget.config(state='disabled')

        # Кнопка закрытия
        close_btn = tk.Button(prompt_window, text="Close",
                             command=prompt_window.destroy,
                             bg='#2c3e50', fg='white',
                             font=('Arial', 11, 'bold'),
                             relief='flat', padx=30, pady=8)
        close_btn.pack(pady=15)

    def show_ai_analysis_selection(self):
        """Показ окна выбора команды для AI анализа."""
        if not self.ai_enabled:
            messagebox.showwarning("AI недоступен",
                                   "AI анализ недоступен.\n\nСоздайте файл .env с вашим OpenAI API ключом:\nOPENAI_API_KEY=sk-...")
            return

        if not self.games:
            messagebox.showwarning("Нет данных", "Сначала загрузите данные об играх!")
            return

        # Создаём окно выбора команды
        select_window = tk.Toplevel(self.root)
        select_window.title("AI Analysis - Select Team")
        select_window.geometry("400x500")
        select_window.configure(bg='#1a1a2e')

        # Заголовок
        header = tk.Label(select_window, text="Select Team for AI Analysis",
                         font=('Arial', 14, 'bold'), fg='#9b59b6', bg='#1a1a2e')
        header.pack(pady=15)

        desc = tk.Label(select_window,
                       text="AI проанализирует изменения в составе\nи их влияние на статистику игроков",
                       font=('Arial', 10), fg='#a0a0a0', bg='#1a1a2e')
        desc.pack(pady=5)

        # Список команд
        teams_frame = tk.Frame(select_window, bg='#1a1a2e')
        teams_frame.pack(fill='both', expand=True, padx=20, pady=10)

        for game in self.games:
            game_frame = tk.Frame(teams_frame, bg='#16213e')
            game_frame.pack(fill='x', pady=5)

            game_time = game.get('game_time', 'TBD')
            time_lbl = tk.Label(game_frame, text=game_time,
                               font=('Arial', 9), fg='#a0a0a0', bg='#16213e')
            time_lbl.pack(pady=5)

            btn_frame = tk.Frame(game_frame, bg='#16213e')
            btn_frame.pack(fill='x', padx=10, pady=5)

            # Away team
            away = game.get('away_team', {})
            away_abbrev = away.get('abbrev', '???')
            away_colors = TEAM_COLORS.get(away_abbrev, {'primary': '#333333'})

            away_btn = tk.Button(btn_frame, text=away_abbrev,
                                command=lambda a=away_abbrev, w=select_window: self.run_ai_analysis(a, w),
                                bg=away_colors['primary'], fg='white',
                                font=('Arial', 12, 'bold'),
                                relief='flat', padx=20, pady=8)
            away_btn.pack(side='left', padx=10)

            vs_lbl = tk.Label(btn_frame, text="@",
                             font=('Arial', 14, 'bold'), fg='#e94560', bg='#16213e')
            vs_lbl.pack(side='left', padx=10)

            # Home team
            home = game.get('home_team', {})
            home_abbrev = home.get('abbrev', '???')
            home_colors = TEAM_COLORS.get(home_abbrev, {'primary': '#333333'})

            home_btn = tk.Button(btn_frame, text=home_abbrev,
                                command=lambda h=home_abbrev, w=select_window: self.run_ai_analysis(h, w),
                                bg=home_colors['primary'], fg='white',
                                font=('Arial', 12, 'bold'),
                                relief='flat', padx=20, pady=8)
            home_btn.pack(side='left', padx=10)

    def run_ai_analysis(self, team_abbrev, parent_window):
        """Запуск AI анализа для выбранной команды."""
        parent_window.destroy()

        # Показываем окно загрузки
        self.loading_window = tk.Toplevel(self.root)
        self.loading_window.title("AI Analysis")
        self.loading_window.geometry("350x150")
        self.loading_window.configure(bg='#1a1a2e')
        self.loading_window.resizable(False, False)

        # Центрируем окно
        self.loading_window.transient(self.root)
        self.loading_window.grab_set()

        colors = TEAM_COLORS.get(team_abbrev, {'primary': '#9b59b6'})

        # Заголовок команды
        team_lbl = tk.Label(self.loading_window, text=team_abbrev,
                           font=('Arial', 18, 'bold'), fg=colors['primary'], bg='#1a1a2e')
        team_lbl.pack(pady=(20, 10))

        # Текст загрузки
        self.loading_label = tk.Label(self.loading_window, text="Загрузка данных...",
                                     font=('Arial', 11), fg='#a0a0a0', bg='#1a1a2e')
        self.loading_label.pack(pady=5)

        # Анимация точек
        self.loading_dots = 0
        self._animate_loading()

        self.status_label.config(text=f"AI analyzing {team_abbrev}...", fg='#9b59b6')

        # Запускаем в фоне
        thread = threading.Thread(
            target=self._run_ai_analysis_thread,
            args=(team_abbrev,),
            daemon=True
        )
        thread.start()

    def _animate_loading(self):
        """Анимация точек загрузки."""
        if hasattr(self, 'loading_window') and self.loading_window.winfo_exists():
            self.loading_dots = (self.loading_dots + 1) % 4
            dots = "." * self.loading_dots
            self.loading_label.config(text=f"AI анализирует{dots}")
            self.root.after(400, self._animate_loading)

    def _run_ai_analysis_thread(self, team_abbrev):
        """Фоновый AI анализ."""
        try:
            # Получаем данные о прошлой игре
            historical = self.historical_cache.get(team_abbrev)
            if not historical:
                # Загружаем если нет в кэше
                historical = get_team_last_game_starters_nba_api(team_abbrev, '2025-26')
                if historical:
                    historical['cached_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.historical_cache[team_abbrev] = historical

            # Получаем текущий состав
            current_starters = []
            for game in self.games:
                for team_type in ['away_team', 'home_team']:
                    team_data = game.get(team_type, {})
                    if team_data.get('abbrev') == team_abbrev:
                        lineup = team_data.get('lineup', [])
                        for player in lineup:
                            if player.get('position') in POSITIONS_ORDER and player.get('status', 'active') != 'out':
                                current_starters.append(player.get('name'))
                        break

            # Сравниваем составы по ФАМИЛИЯМ (разные форматы имён: D. Booker vs Devin Booker)
            past_starters = historical.get('starters_names', []) if historical else []

            new_players, removed_players = match_players_by_lastname(current_starters, past_starters)

            changes = {
                'new_players': new_players,
                'removed_players': removed_players
            }

            # Получаем статистику команды
            team_stats = self.team_stats_cache.get(team_abbrev)

            # Запускаем AI анализ
            analysis = analyze_lineup_changes(team_abbrev, changes, team_stats)

            # Закрываем окно загрузки и показываем результат
            self.root.after(0, lambda: self._close_loading_and_show_result(team_abbrev, changes, analysis, historical))

        except Exception as e:
            print(f"Ошибка AI анализа: {e}")
            self.root.after(0, lambda: self._close_loading_window())
            self.root.after(0, lambda: self.status_label.config(
                text=f"AI Error: {e}", fg='#ff6b6b'
            ))

        self.root.after(0, lambda: self.status_label.config(
            text=f"{len(self.games)} games today", fg='#a0a0a0'
        ))

    def _close_loading_window(self):
        """Закрытие окна загрузки."""
        if hasattr(self, 'loading_window') and self.loading_window.winfo_exists():
            self.loading_window.destroy()

    def _close_loading_and_show_result(self, team_abbrev, changes, analysis, historical):
        """Закрытие окна загрузки и показ результата."""
        self._close_loading_window()
        self._show_ai_analysis_popup(team_abbrev, changes, analysis, historical)

    def _show_ai_analysis_popup(self, team_abbrev, changes, analysis, historical):
        """Показ popup окна с AI анализом."""
        colors = TEAM_COLORS.get(team_abbrev, {'primary': '#333333', 'secondary': '#666666'})

        popup = tk.Toplevel(self.root)
        popup.title(f"AI Analysis - {team_abbrev}")
        popup.geometry("600x550")
        popup.configure(bg='#1a1a2e')

        # Заголовок
        header_frame = tk.Frame(popup, bg=colors['primary'])
        header_frame.pack(fill='x')

        header = tk.Label(header_frame, text=f"{team_abbrev} - AI Analysis",
                         font=('Arial', 16, 'bold'), fg='white', bg=colors['primary'])
        header.pack(pady=15)

        # Информация об изменениях
        changes_frame = tk.Frame(popup, bg='#16213e')
        changes_frame.pack(fill='x', padx=15, pady=10)

        if historical:
            last_game = tk.Label(changes_frame,
                                text=f"Last game: {historical.get('matchup', 'N/A')} ({historical.get('date', 'N/A')})",
                                font=('Arial', 10), fg='#a0a0a0', bg='#16213e')
            last_game.pack(anchor='w', padx=10, pady=5)

        new_players = changes.get('new_players', [])
        removed_players = changes.get('removed_players', [])

        if new_players:
            new_lbl = tk.Label(changes_frame,
                              text=f"+ RETURNING today: {', '.join(new_players)}",
                              font=('Arial', 11, 'bold'), fg='#6bcb77', bg='#16213e')
            new_lbl.pack(anchor='w', padx=10, pady=2)

        if removed_players:
            removed_lbl = tk.Label(changes_frame,
                                  text=f"- OUT today (vs last game): {', '.join(removed_players)}",
                                  font=('Arial', 11, 'bold'), fg='#ff6b6b', bg='#16213e')
            removed_lbl.pack(anchor='w', padx=10, pady=2)

        if not new_players and not removed_players:
            no_changes = tk.Label(changes_frame,
                                 text="No lineup changes detected",
                                 font=('Arial', 11), fg='#ffd93d', bg='#16213e')
            no_changes.pack(anchor='w', padx=10, pady=5)

        # AI анализ
        analysis_frame = tk.Frame(popup, bg='#1a1a2e')
        analysis_frame.pack(fill='both', expand=True, padx=15, pady=10)

        analysis_header = tk.Label(analysis_frame, text="AI Analysis",
                                  font=('Arial', 12, 'bold'), fg='#9b59b6', bg='#1a1a2e')
        analysis_header.pack(anchor='w', pady=5)

        # Текстовое поле с анализом
        text_frame = tk.Frame(analysis_frame, bg='#16213e')
        text_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')

        analysis_text = tk.Text(text_frame, bg='#16213e', fg='white',
                               font=('Arial', 11), wrap='word',
                               yscrollcommand=scrollbar.set,
                               padx=10, pady=10)
        analysis_text.pack(fill='both', expand=True)
        scrollbar.config(command=analysis_text.yview)

        analysis_text.insert('end', analysis)
        analysis_text.config(state='disabled')

        # Кнопка закрытия
        close_btn = tk.Button(popup, text="Close",
                             command=popup.destroy,
                             bg=colors['primary'], fg='white',
                             font=('Arial', 11, 'bold'),
                             relief='flat', padx=30, pady=8)
        close_btn.pack(pady=15)

    def auto_ai_analysis_on_change(self, changes):
        """Автоматический AI анализ при обнаружении изменений в составе."""
        if not self.ai_enabled:
            return

        # Группируем изменения по командам
        teams_changed = set()
        for change in changes:
            teams_changed.add(change['team'])

        # Запускаем анализ для каждой команды с изменениями
        for team_abbrev in teams_changed:
            thread = threading.Thread(
                target=self._run_ai_analysis_thread,
                args=(team_abbrev,),
                daemon=True
            )
            thread.start()

    def show_news_window(self):
        """Показ окна с новостями NBA."""
        # Создаём окно
        news_window = tk.Toplevel(self.root)
        news_window.title("NBA News - Championat.ru")
        news_window.geometry("900x700")
        news_window.configure(bg='#1a1a2e')

        # Заголовок
        header_frame = tk.Frame(news_window, bg='#e67e22')
        header_frame.pack(fill='x')

        header = tk.Label(header_frame, text="📰 NBA News",
                         font=('Arial', 18, 'bold'), fg='white', bg='#e67e22')
        header.pack(side='left', padx=20, pady=15)

        # Кнопка обновления новостей
        refresh_btn = tk.Button(header_frame, text="🔄 Update News",
                               command=lambda: self._refresh_news_in_window(news_window),
                               bg='#d35400', fg='white',
                               font=('Arial', 10, 'bold'),
                               relief='flat', padx=15, pady=5)
        refresh_btn.pack(side='right', padx=20, pady=15)

        # Фильтр по команде
        filter_frame = tk.Frame(news_window, bg='#16213e')
        filter_frame.pack(fill='x', padx=10, pady=5)

        filter_label = tk.Label(filter_frame, text="Filter by team:",
                               font=('Arial', 10), fg='#a0a0a0', bg='#16213e')
        filter_label.pack(side='left', padx=10)

        # Собираем команды из текущих игр
        teams = ["All"]
        for game in self.games:
            away = game.get('away_team', {}).get('abbrev')
            home = game.get('home_team', {}).get('abbrev')
            if away and away not in teams:
                teams.append(away)
            if home and home not in teams:
                teams.append(home)

        self.news_filter_var = tk.StringVar(value="All")
        for team in teams[:10]:  # Ограничиваем до 10 кнопок
            btn_color = TEAM_COLORS.get(team, {}).get('primary', '#333333') if team != "All" else '#555555'
            btn = tk.Button(filter_frame, text=team,
                           command=lambda t=team: self._filter_news(t, news_window),
                           bg=btn_color, fg='white',
                           font=('Arial', 9, 'bold'),
                           relief='flat', padx=8, pady=3)
            btn.pack(side='left', padx=3)

        # Скроллируемый фрейм для новостей
        container = tk.Frame(news_window, bg='#1a1a2e')
        container.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)

        self.news_scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')
        self.news_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.news_scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        self.news_canvas = canvas

        # Загружаем новости
        self._load_news_to_frame("All")

    def _filter_news(self, team_abbrev, window):
        """Фильтрация новостей по команде."""
        self.news_filter_var.set(team_abbrev)
        self._load_news_to_frame(team_abbrev)

    def _load_news_to_frame(self, team_filter):
        """Загрузка новостей в окно."""
        # Очищаем фрейм
        for widget in self.news_scrollable_frame.winfo_children():
            widget.destroy()

        # Получаем новости
        try:
            if team_filter == "All":
                news_list = get_latest_news(30)
            else:
                news_list = get_news_by_team(team_filter, 30)
        except Exception as e:
            error_label = tk.Label(self.news_scrollable_frame,
                                  text=f"Error loading news: {e}",
                                  font=('Arial', 12), fg='#ff6b6b', bg='#1a1a2e')
            error_label.pack(pady=20)
            return

        if not news_list:
            no_news = tk.Label(self.news_scrollable_frame,
                              text="No news found.\n\nClick 'Update News' to fetch latest news.",
                              font=('Arial', 12), fg='#a0a0a0', bg='#1a1a2e')
            no_news.pack(pady=50)
            return

        # Отображаем новости
        for news in news_list:
            self._create_news_card(news)

    def _create_news_card(self, news):
        """Создание карточки новости."""
        card = tk.Frame(self.news_scrollable_frame, bg='#16213e', cursor='hand2')
        card.pack(fill='x', padx=5, pady=5)

        # Левая часть: метаданные
        meta_frame = tk.Frame(card, bg='#16213e')
        meta_frame.pack(fill='x', padx=10, pady=8)

        # Дата
        published = news.get('published_at', '')
        if published:
            try:
                dt = datetime.strptime(str(published)[:19], '%Y-%m-%d %H:%M:%S')
                date_str = dt.strftime('%d.%m %H:%M')
            except:
                date_str = str(published)[:16]
        else:
            date_str = "N/A"

        date_label = tk.Label(meta_frame, text=date_str,
                             font=('Arial', 9), fg='#888888', bg='#16213e')
        date_label.pack(side='left')

        # Команды (теги)
        teams_str = news.get('teams', '')
        if teams_str:
            teams = teams_str.split(',')
            for team in teams[:3]:  # Максимум 3 тега
                team = team.strip()
                color = TEAM_COLORS.get(team, {}).get('primary', '#555555')
                team_tag = tk.Label(meta_frame, text=team,
                                   font=('Arial', 8, 'bold'), fg='white', bg=color,
                                   padx=5, pady=1)
                team_tag.pack(side='left', padx=3)

        # Автор
        author = news.get('author', '')
        if author:
            author_label = tk.Label(meta_frame, text=f"• {author}",
                                   font=('Arial', 9), fg='#666666', bg='#16213e')
            author_label.pack(side='right')

        # Заголовок
        title = news.get('title', 'No title')
        title_label = tk.Label(card, text=title,
                              font=('Arial', 12, 'bold'), fg='white', bg='#16213e',
                              wraplength=800, justify='left', anchor='w', cursor='hand2')
        title_label.pack(fill='x', padx=10, pady=(0, 5))

        # Краткое содержание (первые 200 символов)
        content = news.get('content', '')
        if content and len(content) > 200:
            content = content[:200] + "..."

        if content:
            content_label = tk.Label(card, text=content,
                                    font=('Arial', 10), fg='#a0a0a0', bg='#16213e',
                                    wraplength=800, justify='left', anchor='w')
            content_label.pack(fill='x', padx=10, pady=(0, 8))

        # Клик открывает новость в браузере
        url = news.get('url', '')
        if url:
            for widget in [card, title_label]:
                widget.bind('<Button-1>', lambda e, u=url: webbrowser.open(u))

            # Подсветка при наведении
            def on_enter(e):
                card.config(bg='#1e3a5f')
                meta_frame.config(bg='#1e3a5f')
                for child in meta_frame.winfo_children():
                    if 'tag' not in str(child):
                        try:
                            child.config(bg='#1e3a5f')
                        except:
                            pass
                title_label.config(bg='#1e3a5f')
                if content:
                    content_label.config(bg='#1e3a5f')

            def on_leave(e):
                card.config(bg='#16213e')
                meta_frame.config(bg='#16213e')
                for child in meta_frame.winfo_children():
                    if 'tag' not in str(child):
                        try:
                            child.config(bg='#16213e')
                        except:
                            pass
                title_label.config(bg='#16213e')
                if content:
                    content_label.config(bg='#16213e')

            card.bind('<Enter>', on_enter)
            card.bind('<Leave>', on_leave)

    def _refresh_news_in_window(self, window):
        """Обновление новостей в окне."""
        # Показываем статус загрузки
        loading_label = tk.Label(window, text="Updating news...",
                                font=('Arial', 12), fg='#ffd93d', bg='#1a1a2e')
        loading_label.place(relx=0.5, rely=0.5, anchor='center')
        window.update()

        # Запускаем парсинг в фоне
        def fetch_news():
            try:
                init_database()
                scrape_news(days=3, max_pages=5)
                # Обновляем отображение
                self.root.after(0, lambda: self._on_news_updated(window, loading_label))
            except Exception as e:
                print(f"Error fetching news: {e}")
                self.root.after(0, lambda: loading_label.config(text=f"Error: {e}", fg='#ff6b6b'))

        thread = threading.Thread(target=fetch_news, daemon=True)
        thread.start()

    def _on_news_updated(self, window, loading_label):
        """Callback после обновления новостей."""
        loading_label.destroy()
        current_filter = getattr(self, 'news_filter_var', None)
        filter_value = current_filter.get() if current_filter else "All"
        self._load_news_to_frame(filter_value)

    def update_news_in_background(self):
        """Фоновое обновление новостей при старте приложения."""
        def fetch():
            try:
                print("Запуск фонового обновления новостей...")
                # Парсим только 2 страницы для быстроты (последние новости)
                scrape_news(days=3, max_pages=2)
                print("Фоновое обновление новостей завершено")
            except Exception as e:
                print(f"Ошибка фонового обновления новостей: {e}")

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()


def main():
    root = tk.Tk()
    app = LineupsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
