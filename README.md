# RentScout

[![License](https://img.shields.io/badge/license-Commercial-orange.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/CreatmanCEO/rentscout?style=flat)](https://github.com/CreatmanCEO/rentscout/stargazers)
[![Validate](https://github.com/CreatmanCEO/rentscout/actions/workflows/validate.yml/badge.svg)](https://github.com/CreatmanCEO/rentscout/actions/workflows/validate.yml)
![Status](https://img.shields.io/badge/status-commercial-orange)
![Platform](https://img.shields.io/badge/platform-Python%20%7C%20FastAPI-009688?logo=fastapi&logoColor=white)

[Русская версия](README.ru.md)

> **Commercial product. This repository hosts the public surface — README, API docs, configuration scaffolding. Parser internals and operational pieces are proprietary.**

RentScout is a FastAPI service that aggregates Russian rental and short-term-stay listings from Avito, Cian, Yandex Travel, Sutochno, Ostrovok, Otello, and Tvil into a single normalized API. It is built for back-office tooling, market research, and client-facing rental dashboards that need one schema across many sources.

## Why this exists

Each rental platform exposes a different schema, different filter vocabulary, and different anti-bot posture. Stitching them together inside a downstream app means writing seven adapters, seven cache strategies, and seven bug surfaces. RentScout collapses that into one HTTP API: same query, same response shape, same SLA assumptions.

## How it works

1. **API** — FastAPI receives a search query (geo, dates, price band, room count, source filter).
2. **Search service** plans which parsers to run in parallel and merges their results.
3. **Parsers** — per-source modules (`app/parsers/<source>`) for Avito, Cian, Yandex Travel, Sutochno, Ostrovok, Otello, Tvil.
4. **Cache** — Redis-backed layer keyed by query fingerprint to absorb repeat traffic.
5. **Filter** service applies post-fetch normalization and dedupes near-identical listings.
6. **Storage** — SQLAlchemy + Alembic schema for persistent listings, run history, and audit.
7. **Telegram bot** (optional) exposes the same data to operators for alerts and ad-hoc queries.

See [`docs/architecture.svg`](docs/architecture.svg) and [`docs/API.md`](docs/API.md).

## Tech stack

| Layer | Tools |
|---|---|
| API | FastAPI, Uvicorn |
| Async parsing | httpx, asyncio |
| HTML | lxml / BeautifulSoup |
| DB | PostgreSQL + SQLAlchemy + Alembic |
| Cache | Redis |
| Tasks | APScheduler / background tasks |
| Bot | aiogram (operator interface) |
| Deploy | Docker, docker-compose |

## API surface (excerpt)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | liveness |
| `GET` | `/v1/search` | unified search across configured sources |
| `GET` | `/v1/sources` | enabled parsers and their capabilities |
| `GET` | `/v1/listing/{id}` | single normalized listing |

Full reference: [`docs/API.md`](docs/API.md).

## Limitations

- Public repo is **not a runnable product**. Some directories (`app/`, `docker/`, `scripts/`) hold scaffolding; production parsers and ops live elsewhere.
- Source platforms change HTML and anti-bot defenses frequently — production maintenance is a paid service, not a community one.
- Geo coverage is Russia-centric; international rentals are not in scope.
- Rate, freshness, and uptime targets are negotiated per deployment; no public SLA.
- Some parsers depend on residential-quality proxies; without them, request success drops sharply.

## Inquiries

Commercial inquiries, integrations, custom parsers: **creatmanick@gmail.com** · [creatman.site](https://creatman.site).

EOF
