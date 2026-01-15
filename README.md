# NBA Lineups Monitor

Real-time NBA starting lineups monitoring application with change detection, notifications, and AI-powered analysis.

## Features

- **Live Lineups**: Fetches today's NBA starting lineups from Rotowire
- **Change Detection**: Monitors lineup changes every 3 minutes with notifications
- **Historical Comparison**: Compare current lineups with previous games via NBA API
- **Player Stats**: View starter statistics for last 3 games (PTS, REB, AST, STL, BLK)
- **AI Analysis**: GPT-powered analysis of lineup changes impact on player performance
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
openai
python-dotenv
```

## Installation

```bash
pip install requests beautifulsoup4 pandas nba_api plyer openai python-dotenv
```

## AI Setup (Optional)

To enable AI analysis, create a `.env` file in the project directory:

```
OPENAI_API_KEY=sk-your-api-key-here
```

The AI feature analyzes lineup changes and predicts their impact on remaining players' statistics.

## Usage

```bash
python lineups_gui.py
```

## Features Overview

The application displays:
- All NBA games scheduled for today
- Starting 5 players for each team with positions
- Team colors and records
- Injury status indicators
- Click on team header to view detailed stats
- AI Analysis button for GPT-powered insights

## Files

- `lineups_gui.py` - Main GUI application (Tkinter)
- `nba_lineups_scraper.py` - Data scraping and NBA API integration
- `ai_analyzer.py` - OpenAI GPT integration for lineup analysis
- `.env.example` - Example environment file for API keys

## License

MIT
