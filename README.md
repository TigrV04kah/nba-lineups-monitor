# NBA Lineups Monitor

Real-time NBA starting lineups monitoring application with change detection and notifications.

## Features

- **Live Lineups**: Fetches today's NBA starting lineups from Rotowire
- **Change Detection**: Monitors lineup changes every 3 minutes with notifications
- **Historical Comparison**: Compare current lineups with previous games via NBA API
- **Player Stats**: View starter statistics for last 3 games (PTS, REB, AST, STL, BLK)
- **Smart Caching**: Multi-tier caching system to reduce API calls:
  - Lineups cache (1 hour TTL)
  - Historical data cache (12 hours TTL)
  - Team stats cache (24 hours TTL)
- **Preloading**: Background preloading of all team stats on startup

## Requirements

```
requests
beautifulsoup4
pandas
nba_api
plyer
```

## Installation

```bash
pip install requests beautifulsoup4 pandas nba_api plyer
```

## Usage

```bash
python lineups_gui.py
```

## Screenshots

The application displays:
- All NBA games scheduled for today
- Starting 5 players for each team with positions
- Team colors and records
- Injury status indicators
- Click on team header to view detailed stats

## Files

- `lineups_gui.py` - Main GUI application (Tkinter)
- `nba_lineups_scraper.py` - Data scraping and NBA API integration

## License

MIT
