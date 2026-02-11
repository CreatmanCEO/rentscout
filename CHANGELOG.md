# Changelog

## [2.0.0] - 2026-02-11

### Added
- SQLite database for duplicate prevention
- Critical fields parsing: renovation, building type, parking, seller
- Living area parsing
- Improved address parsing (100% coverage)
- Strict CAO district filtering (10 districts)
- Enhanced logging with emoji indicators
- Comprehensive CREATMAN documentation
- Avito parser structure (stub)

### Changed
- Migrated to new VPS (Waicore Frankfurt)
- Improved anti-detection (Playwright + Stealth)
- Better error handling and logging

### Fixed
- IndentationError in bot.py
- Undefined parsed_ids variable
- Triple duplicate filtering block
- enrich_data.py writing to wrong spreadsheet

### Performance
- 85-93% critical fields coverage (up from 0%)
- 100% address parsing (up from 9-20%)
- No duplicates (SQLite tracking)

## [1.0.0] - 2026-02-10

### Initial CREATMAN fork
- Basic CIAN parser
- Telegram bot integration
- Google Sheets output
