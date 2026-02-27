# Hybel Messaging Platform

A multi-participant messaging system for landlord-tenant communication, built as part of the [Hybel](https://hybel.no) rent management platform.

## Overview

Hybel connects landlords with tenants across Scandinavia. This project upgrades the existing messaging system to support:

- **Multi-participant conversations** — loop in contractors, property managers, and co-landlords
- **Full-text search** — find messages by content, property, status, and more
- **Real-time delivery** — instant messages via WebSockets with graceful offline handling

All while preserving existing features: read/unread tracking, attachments, delegation, and internal comments.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.1, Django REST Framework, Django Channels |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS 4 |
| Database | PostgreSQL 16 (full-text search with GIN indexes) |
| Real-time | WebSockets via Channels + Redis 7 |
| State | Zustand, TanStack React Query |
| Infrastructure | Docker Compose, Nginx, Daphne (ASGI) |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd hybel

# Create environment file
cp .env.example .env

# Start all services
docker compose up --build
```

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/ |
| Django Admin | http://localhost:8000/admin/ |

Admin credentials (dev only): `admin` / `admin`

### Running Tests

```bash
# Backend tests
docker compose exec backend pytest

# Backend tests with coverage report
docker compose exec backend pytest --cov=apps --cov-report=html

# Frontend tests
docker compose exec frontend npm test

# Frontend tests with coverage
docker compose exec frontend npm run test:coverage
```

### Linting

```bash
# Backend (ruff + mypy)
docker compose run backend-lint

# Frontend (ESLint)
docker compose run frontend-lint
```

### Seed Data

```bash
docker compose exec backend python manage.py seed_data
```

### Stop / Reset

```bash
# Stop services
docker compose down

# Stop and delete all data
docker compose down -v
```

## Architecture

### Data Model

```
Conversation
├── ConversationParticipant (role + side)
├── Message (regular, internal_comment, system_event)
│   └── Attachment
├── ReadState (per-user unread tracking)
└── Delegation (assigned responsible user)
```

The `side` field on `ConversationParticipant` (`tenant_side` | `landlord_side`) is the core access control boundary. Internal comments are only visible to `landlord_side` participants — this rule is enforced across the REST API, search results, and WebSocket broadcasts.

### API Endpoints

```
GET    /api/conversations/                              # Inbox list
POST   /api/conversations/                              # Create conversation
GET    /api/conversations/{id}/                         # Detail + participants
PATCH  /api/conversations/{id}/                         # Update status/subject
GET    /api/conversations/{id}/messages/                # Messages (filtered by side)
POST   /api/conversations/{id}/messages/                # Send message
POST   /api/conversations/{id}/add-participant/         # Add participant
POST   /api/conversations/{id}/delegate/                # Delegate
POST   /api/conversations/{id}/mark-read/               # Mark as read
GET    /api/conversations/search/?q=...&property=...    # Full-text search
```

### Frontend Pages

| Route | Description |
|-------|-------------|
| `/meldinger` | Inbox — conversation list + detail panel |
| `/meldinger/[conversationId]` | Deep link to a conversation |
| `/meldinger/ny` | Create new conversation |

### WebSocket Events

Connect to `ws://localhost:8000/ws/inbox/` for real-time updates:

`message.new`, `read.updated`, `participant.added`, `participant.removed`, `delegation.assigned`, `typing.started`, `typing.stopped`, `connection.sync`

## Project Structure

```
hybel/
├── docker-compose.yml              # Development environment
├── docker-compose.prod.yml         # Production environment
├── .env.example                    # Environment template
├── pyproject.toml                  # Ruff, mypy, pytest config
├── .pre-commit-config.yaml         # Pre-commit hooks
│
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh               # DB wait, migrations, superuser
│   ├── manage.py
│   ├── requirements/
│   │   ├── base.txt                # Django, DRF, Channels, PostgreSQL
│   │   ├── dev.txt                 # pytest, factory-boy, ruff, mypy
│   │   └── prod.txt                # gunicorn, sentry, whitenoise
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py             # Shared settings
│   │   │   ├── dev.py              # Debug, CORS
│   │   │   ├── prod.py             # Security, HTTPS
│   │   │   └── test.py             # Fast hashing, in-memory storage
│   │   ├── urls.py
│   │   ├── asgi.py                 # Channels + HTTP routing
│   │   └── wsgi.py
│   └── apps/
│       ├── users/                  # Custom User model (UUID, email-based)
│       ├── properties/             # Property model
│       └── messaging/              # Core messaging app
│           ├── models.py           # Conversation, Message, Participant, etc.
│           ├── serializers.py
│           ├── views.py
│           ├── permissions.py      # Access control (side-based visibility)
│           ├── services.py         # Business logic
│           ├── consumers.py        # WebSocket consumers
│           ├── managers.py         # Custom QuerySet managers
│           └── tests/              # Comprehensive test suite
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── app/
│       │   └── meldinger/          # Messaging routes (Next.js App Router)
│       ├── components/
│       │   ├── messaging/          # InboxLayout, ConversationList, MessageBubble, etc.
│       │   └── ui/                 # Avatar, Spinner, Icon
│       ├── hooks/                  # useWebSocket, useDebounce
│       ├── lib/
│       │   ├── api.ts              # REST client
│       │   ├── websocket.ts        # WebSocket manager (reconnection, offline queue)
│       │   ├── auth.tsx            # Auth context
│       │   └── providers.tsx       # React Query + Auth providers
│       ├── stores/
│       │   └── messaging.ts        # Zustand store
│       └── types/
│           └── messaging.ts        # TypeScript interfaces
│
└── nginx/
    ├── Dockerfile
    └── nginx.conf                  # Reverse proxy, WebSocket upgrade, rate limiting
```

## Development

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Hooks include: ruff (lint + format), mypy (strict), bandit (security), detect-secrets, trailing whitespace, YAML/TOML validation.

### Environment Variables

See [.env.example](.env.example) for all available configuration options.

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 (channel layer) |
| `backend` | 8000 | Django + Daphne (ASGI) |
| `frontend` | 3000 | Next.js (Turbopack dev server) |


## Key Design Decisions

- **`side` field over role-based visibility** — a contractor can be on either side depending on context; `side` decouples visibility from role
- **PostgreSQL FTS over Elasticsearch** — sufficient at current scale (10K+ conversations), with GIN indexes and tsvector triggers
- **Per-user ReadState with denormalized unread_count** — avoids expensive COUNT queries on every inbox load
- **Delegation as a separate model** — composes cleanly with multi-participant; one delegated user per conversation, independent of participants
- **Session-based authentication** — simple, stateful, appropriate for same-origin deployment