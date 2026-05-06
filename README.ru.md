# RentScout

[![License](https://img.shields.io/badge/license-Commercial-orange.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/CreatmanCEO/rentscout?style=flat)](https://github.com/CreatmanCEO/rentscout/stargazers)
[![Validate](https://github.com/CreatmanCEO/rentscout/actions/workflows/validate.yml/badge.svg)](https://github.com/CreatmanCEO/rentscout/actions/workflows/validate.yml)
![Status](https://img.shields.io/badge/status-commercial-orange)
![Platform](https://img.shields.io/badge/platform-Python%20%7C%20FastAPI-009688?logo=fastapi&logoColor=white)

[English version](README.md)

> **Коммерческий продукт. В этом репозитории — публичная витрина: README, документация API, каркас конфигурации. Внутренности парсеров и эксплуатационные части проприетарны.**

RentScout — сервис на FastAPI, который агрегирует объявления аренды и краткосрочного проживания с Avito, Cian, Яндекс Путешествий, Суточно, Ostrovok, Otello и Tvil в единый нормализованный API. Делается под бэк-офис, маркет-рисёрч и клиентские дашборды, которым нужна одна схема для многих источников.

## Зачем

У каждой площадки своя схема, свой словарь фильтров и свой анти-бот. Собирать всё это внутри даунстрим-приложения — значит писать семь адаптеров, семь стратегий кеша и семь источников багов. RentScout сворачивает это в один HTTP API: один запрос, один формат ответа, одни допущения по SLA.

## Как устроено

1. **API** — FastAPI принимает запрос (гео, даты, цена, комнаты, фильтр по источникам).
2. **Search service** планирует параллельный запуск парсеров и сливает результаты.
3. **Парсеры** — модули `app/parsers/<source>` для Avito, Cian, Яндекс Путешествий, Суточно, Ostrovok, Otello, Tvil.
4. **Кеш** — Redis по отпечатку запроса для повторного трафика.
5. **Фильтрация** — нормализация и дедуп близких дублей после выдачи.
6. **Хранилище** — SQLAlchemy + Alembic для объявлений, истории, аудита.
7. **Telegram-бот** (опционально) даёт оператору тот же доступ для алертов и ad-hoc запросов.

См. [`docs/architecture.svg`](docs/architecture.svg) и [`docs/API.md`](docs/API.md).

## Стек

| Слой | Инструменты |
|---|---|
| API | FastAPI, Uvicorn |
| Async парсинг | httpx, asyncio |
| HTML | lxml / BeautifulSoup |
| БД | PostgreSQL + SQLAlchemy + Alembic |
| Кеш | Redis |
| Задачи | APScheduler / background tasks |
| Бот | aiogram (операторский интерфейс) |
| Деплой | Docker, docker-compose |

## API (фрагмент)

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/health` | liveness |
| `GET` | `/v1/search` | единый поиск по подключённым источникам |
| `GET` | `/v1/sources` | подключённые парсеры и их возможности |
| `GET` | `/v1/listing/{id}` | нормализованное объявление |

Полная справка: [`docs/API.md`](docs/API.md).

## Ограничения

- Публичный репозиторий **не рабочий продукт целиком**. Часть директорий (`app/`, `docker/`, `scripts/`) — каркас; продовые парсеры и ops живут отдельно.
- HTML и анти-бот площадок меняются часто — поддержка платная, не комьюнити.
- Гео — Россия; зарубежная аренда вне рамок.
- Свежесть, аптайм и rate согласуются по контракту, публичного SLA нет.
- Некоторые парсеры требуют резидентных прокси; без них success rate резко падает.

## Связаться

Коммерческие запросы, интеграции, кастомные парсеры: **creatmanick@gmail.com** · [creatman.site](https://creatman.site).

## Автор

**Николай Подоляк** — независимый разработчик, автоматизация и интеграция AI.

- GitHub: [@CreatmanCEO](https://github.com/CreatmanCEO)
- Habr: [creatman](https://habr.com/ru/users/creatman/)
- Telegram: [@Creatman_it](https://t.me/Creatman_it)
- Сайт: [creatman.site](https://creatman.site)
