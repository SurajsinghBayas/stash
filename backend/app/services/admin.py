"""The admin account (seeded from ADMIN_EMAIL / ADMIN_PASSWORD) and the numbers the admin panel shows."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.models import RefreshToken, User
from app.db import SessionLocal, capabilities, engine
from app.services.auth.passwords import hash_password, verify_password

log = logging.getLogger("stash.admin")


def is_admin(user: User) -> bool:
    return bool(settings.admin_email and user.email and user.email_verified
                and user.email.lower() == settings.admin_email.lower())


async def seed_admin() -> None:
    """Create the admin account, or bring its password in line with ADMIN_PASSWORD. Safe on every start."""
    if not settings.admin_email or not settings.admin_password:
        return
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(func.lower(User.email) == settings.admin_email.lower()))).scalar()
        if user is None:
            user = User(email=settings.admin_email, email_verified=True, display_name="Admin",
                        password_hash=await hash_password(settings.admin_password),
                        digest_daily=False, digest_weekly=False)
            s.add(user)
            log.info("admin account created")
        else:
            user.email_verified = True
            user.suspended_at = None
            if not await verify_password(settings.admin_password, user.password_hash):
                user.password_hash = await hash_password(settings.admin_password)
                # A new password ends every existing admin session.
                await s.execute(update(RefreshToken).where(RefreshToken.user_id == user.id,
                                                           RefreshToken.revoked_at.is_(None))
                                .values(revoked_at=datetime.now(UTC)))
                log.info("admin password updated")
        await s.commit()


async def _rows(s: AsyncSession, sql: str) -> list[dict]:
    return [dict(r) for r in (await s.execute(text(sql))).mappings()]


async def _one(s: AsyncSession, sql: str) -> dict:
    return dict((await s.execute(text(sql))).mappings().one())


# Activity: a session refresh (every ~15 minutes while the app is open), a question, or a card edit.
ACTIVITY = """
  select user_id, created_at as at from refresh_tokens where created_at > now() - interval '30 days'
  union all select user_id, created_at from chat_messages
    where role = 'user' and created_at > now() - interval '30 days'
  union all select owner_id, updated_at from items where updated_at > now() - interval '30 days'
"""


async def metrics(s: AsyncSession) -> dict:
    totals = await _one(s, """
      select
        (select count(*) from users) as users,
        (select count(*) from users where email_verified) as verified_users,
        (select count(*) from users where suspended_at is not null) as suspended_users,
        (select count(*) from users where created_at > now() - interval '7 days') as new_users_7d,
        (select count(*) from canvases where deleted_at is null) as canvases,
        (select count(*) from canvases where deleted_at is null and share_token is not null) as shared_canvases,
        (select count(*) from items where deleted_at is null) as cards,
        (select count(*) from items where deleted_at is null and safety_state = 'flagged') as flagged_cards,
        (select coalesce(sum(bytes), 0) from items where deleted_at is null) as storage_bytes,
        (select count(*) from chat_messages where role = 'user') as questions,
        (select count(*) from reminders where state = 'pending') as reminders_pending,
        (select count(*) from reminders where state = 'sent') as reminders_sent,
        (select count(*) from memories) as memories
    """)
    active = await _one(s, f"""
      select count(distinct user_id) filter (where at > now() - interval '1 day') as dau,
             count(distinct user_id) filter (where at > now() - interval '7 days') as wau,
             count(distinct user_id) as mau
      from ({ACTIVITY}) a
    """)
    daily = await _rows(s, f"""
      with days as (
        select generate_series(date_trunc('day', now()) - interval '29 days', date_trunc('day', now()),
                               interval '1 day') as day
      ),
      act as ({ACTIVITY})
      select to_char(d.day, 'YYYY-MM-DD') as day,
        (select count(*) from users u where u.created_at >= d.day and u.created_at < d.day + interval '1 day')
          as signups,
        (select count(*) from items i where i.created_at >= d.day and i.created_at < d.day + interval '1 day')
          as cards,
        (select count(*) from chat_messages m where m.role = 'user' and m.created_at >= d.day
           and m.created_at < d.day + interval '1 day') as questions,
        (select count(distinct a.user_id) from act a where a.at >= d.day and a.at < d.day + interval '1 day')
          as active_users
      from days d order by d.day
    """)
    cards_by_kind = await _rows(s, """
      select kind, count(*) as count from items where deleted_at is null group by kind order by count desc
    """)
    sign_in = await _rows(s, """
      select 'email' as method, count(*) as count from users where password_hash is not null
      union all select provider, count(distinct user_id) from oauth_accounts group by provider
      order by count desc
    """)
    ai_tasks = await _rows(s, """
      select task, count(*) as requests,
             coalesce(sum(input_tokens), 0) as input_tokens, coalesce(sum(output_tokens), 0) as output_tokens,
             coalesce(round(avg(latency_ms)), 0) as avg_ms,
             count(*) filter (where outcome = 'provider_error') as errors
      from ai_requests where created_at > now() - interval '30 days'
      group by task order by requests desc
    """)
    ai = await _one(s, """
      select count(*) as requests,
             coalesce(sum(input_tokens), 0) + coalesce(sum(output_tokens), 0) as tokens,
             coalesce(round(percentile_cont(0.95) within group (order by latency_ms)), 0) as p95_ms,
             count(*) filter (where outcome = 'provider_error') as errors
      from ai_requests where created_at > now() - interval '30 days'
    """)
    moderation = await _rows(s, """
      select source, action, count(*) as count from moderation_events
      where created_at > now() - interval '30 days' group by source, action order by count desc
    """)
    jobs = await _rows(s, "select state, count(*) as count from jobs group by state order by state")
    queue = await _one(s, """
      select count(*) as due,
             coalesce(extract(epoch from now() - min(run_after))::int, 0) as oldest_due_s
      from jobs where state = 'queued' and run_after <= now()
    """)
    failed_jobs = await _rows(s, """
      select id, kind, attempts, left(coalesce(last_error, ''), 240) as error, updated_at
      from jobs where state = 'dead' order by updated_at desc limit 8
    """)
    emails = await _one(s, """
      select (select count(*) from reminders where state = 'sent' and sent_at > now() - interval '30 days')
               as reminders,
             (select count(*) from reminders where state = 'failed') as reminders_failed,
             (select count(*) from digest_runs where kind = 'daily' and sent_at > now() - interval '30 days')
               as daily_digests,
             (select count(*) from digest_runs where kind = 'weekly' and sent_at > now() - interval '30 days')
               as weekly_digests
    """)
    top_users = await _rows(s, f"""
      select u.email, u.display_name, u.created_at,
             (select count(*) from items i where i.owner_id = u.id and i.deleted_at is null) as cards,
             (select count(*) from canvases c where c.owner_id = u.id and c.deleted_at is null) as canvases,
             (select coalesce(sum(coalesce(r.input_tokens, 0) + coalesce(r.output_tokens, 0)), 0)
                from ai_requests r where r.user_id = u.id and r.created_at > now() - interval '30 days')
               as ai_tokens_30d,
             (select max(a.at) from ({ACTIVITY}) a where a.user_id = u.id) as last_active
      from users u order by cards desc, u.created_at desc limit 10
    """)
    recent_users = await _rows(s, """
      select u.email, u.display_name, u.email_verified, u.created_at, u.suspended_at is not null as suspended,
             coalesce((select string_agg(o.provider, ', ') from oauth_accounts o where o.user_id = u.id),
                      'email') as method
      from users u order by u.created_at desc limit 10
    """)
    system = await _one(s, "select pg_database_size(current_database()) as db_bytes, now() as server_time")
    system.update({
        "pool_in_use": engine.pool.checkedout(),
        "pool_size": settings.db_pool_size,
        "vector_search": capabilities.vector,
        "chat": settings.chat_ai_configured,
        "embeddings": settings.embeddings_configured,
        "mail": settings.mail_enabled,
        "environment": settings.app_env,
    })
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "totals": totals, "active": active, "daily": daily,
        "cards_by_kind": cards_by_kind, "sign_in": sign_in,
        "ai": {**ai, "budget_per_user": settings.ai_monthly_token_budget, "tasks": ai_tasks},
        "moderation": moderation, "jobs": {"states": jobs, **queue, "failed": failed_jobs},
        "emails": emails, "top_users": top_users, "recent_users": recent_users, "system": system,
    }
