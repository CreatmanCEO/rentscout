# RentScout by CREATMAN

Умный парсер недвижимости с Telegram ботом и автоматическим сбором данных в Google Sheets.

## Quick Start

```bash
# Install
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
nano .env

# Run
python -m app.telegram_bot.bot
```

## Features

✅ CIAN parser (Playwright + Stealth)  
✅ Telegram bot  
✅ Google Sheets integration  
✅ SQLite deduplication  
✅ Smart filters (CAO only, with renovation, 40-150m²)  
🔄 Avito parser (coming soon)

## Documentation

See [CREATMAN.md](CREATMAN.md) for full documentation.

## License

MIT
