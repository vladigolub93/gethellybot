# HELLY v1 Infrastructure Decisions

Production Stack Decisions for v1

Version: 1.0  
Date: 2026-03-07

## 1. Purpose

This document fixes the concrete infrastructure choices for Helly v1 so implementation can proceed against a real deployment target rather than abstract options.

These decisions are based on available accounts and deployment preferences provided for the project.

## 2. Fixed Stack for v1

Helly v1 will use:

- `Supabase` for PostgreSQL
- `pgvector` inside Supabase Postgres for embeddings
- `Railway` for application deployment
- `Telegram Bot API` for bot transport
- `OpenAI API` for LLM capabilities

Working assumption for storage:

- prefer `Supabase Storage` for user-uploaded and generated artifacts unless a separate storage requirement emerges later

Working assumption for queue/runtime:

- queue and worker processes will run inside Railway deployment units and use the application-selected queue backend

## 3. Finalized Decisions

## 3.1 Database

Decision:

- use `Supabase Postgres` as the primary operational database

Why:

- managed PostgreSQL reduces operational burden
- fits the architecture already documented for Helly
- supports transactional stateful workflows
- works well with SQLAlchemy/Alembic
- allows `pgvector` so we do not need a separate vector database in v1

Consequences:

- schema and migrations should target standard PostgreSQL behavior
- app should avoid vendor-specific lock-in beyond normal managed Postgres expectations
- row-level security is not a priority for the bot backend itself, since the backend will use privileged service access

## 3.2 Vector Search

Decision:

- use `pgvector` in Supabase Postgres

Why:

- keeps the stack smaller
- embeddings volume for v1 is moderate
- avoids introducing Qdrant/Pinecone/Milvus too early

Consequences:

- matching implementation should be written so vector storage can be abstracted later if needed
- exact or simple ANN indexing is sufficient initially

## 3.3 File Storage

Decision:

- default to `Supabase Storage` for CVs, JD files, voice notes, videos, verification videos, transcripts, and generated exports

Why:

- same vendor/account as the database
- simplifies credentials and operations
- good fit for signed/private object access

Consequences:

- file service abstraction should still be implemented as `FileStorage` rather than binding domain code directly to Supabase SDK
- if storage needs change later, migration to S3-compatible storage should remain possible

## 3.4 Application Hosting

Decision:

- deploy API service and worker service on `Railway`

Why:

- user already has a Railway account
- practical for fast iteration and early production deployment
- easy environment variable and service management

Consequences:

- application should be container-friendly
- canonical runtime should be `Python 3.12`
- deployment should support at least:
  - one API/web process
  - one worker process
  - optional scheduler process
- startup commands and health checks need to be Railway-compatible

## 3.5 LLM Provider

Decision:

- use `OpenAI` as the primary LLM provider for v1

Why:

- API access already available
- strong fit for structured extraction, reranking, and evaluation tasks
- reduces uncertainty in early delivery

Consequences:

- implement an internal `LLMClient` abstraction anyway
- prompt assets and model routing should support future provider substitution
- token/cost logging should be built in from the start

## 3.6 Bot Transport

Decision:

- use `Telegram Bot API` with bot token from BotFather

Why:

- matches product design
- no reason to abstract away from Telegram at the product layer

Consequences:

- Telegram update idempotency is mandatory
- webhook-first deployment is preferred on Railway, though polling can exist as fallback for development

## 4. Recommended Production Shape on Railway

Recommended Railway services:

- `helly-api`
- `helly-worker`
- `helly-scheduler` if queue/scheduler separation is needed

External managed dependencies:

- `Supabase Postgres`
- `Supabase Storage`
- `OpenAI`
- `Telegram`

Optional:

- `Redis` if queue choice requires it and Railway-managed Redis is acceptable

## 5. Recommended Environment Variables

The application will likely need at least:

- `APP_ENV`
- `APP_BASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` if used
- `OPENAI_API_KEY`
- `OPENAI_MODEL_EXTRACTION`
- `OPENAI_MODEL_REASONING`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` only if ever needed client-side
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `SUPABASE_STORAGE_BUCKET_PRIVATE`
- `QUEUE_BACKEND`
- `REDIS_URL` if queue requires Redis

The exact final env contract should be formalized later in `.env.example`.

## 6. What Will Be Needed From the Owner

Implementation can proceed without secrets immediately, but for staging/production deployment the following will be needed from the owner:

- Supabase project URL
- Supabase database connection string
- Supabase service role key
- name of storage bucket(s) or permission to create them
- Railway project/environment setup or permission to provide deploy manifests
- Telegram bot token
- OpenAI API key
- target base domain or Railway public domain strategy

## 7. What Can Proceed Without Further Input

With these stack decisions fixed, the following can be built immediately:

- codebase scaffold
- data model and migrations
- Supabase-targeted SQLAlchemy/Alembic config
- Railway deployment configuration
- Telegram bot integration layer
- OpenAI client integration layer
- storage abstraction with Supabase-backed implementation

## 8. Open Infra Choices Still Remaining

These decisions are still open, but they do not block architecture work:

- exact queue implementation
- whether to use Railway Redis or Postgres-backed job queue
- exact webhook domain naming
- whether staging and production use separate Supabase projects

## 9. Recommended Default Choices for Remaining Infra

Unless a better constraint appears, I recommend:

- webhook mode in production
- separate `staging` and `production` Supabase projects
- separate Railway environments or projects for staging and production
- private storage buckets by default
- Redis-backed queue only if job volume or scheduling ergonomics justify it

## 10. Final Position

Helly v1 now has a concrete infrastructure baseline:

- `Supabase` for data and storage
- `Railway` for runtime
- `Telegram` for interaction
- `OpenAI` for AI

This is a strong v1 stack because it keeps infrastructure count low while remaining compatible with the architecture already defined in the main technical documents.
