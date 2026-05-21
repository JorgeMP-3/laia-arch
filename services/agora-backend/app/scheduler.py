"""Agent scheduler — background tick loop + cron parser + delivery (Fase A).

Pulls due jobs from ``agent_scheduled_jobs`` every N seconds, builds an
ephemeral AIAgent via the shared AgentPool, runs the job's prompt, and
delivers the result to the configured channel (telegram / local / origin).

Inspired by ``.laia-core/cron/scheduler.py`` but adapted to:
- DB persistence (SQLite) instead of JSON files
- AGORA AgentPool for AIAgent construction (not standalone)
- asyncio lifespan task (not background thread w/ flock)

We don't port the whole ARCH scheduler (1391 LOC of platform-specific
delivery adapters) — only the cron expression parser and a minimal
delivery layer (telegram via the existing telegram_gateway, or local
log fallback).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any


logger = logging.getLogger(__name__)


_TICK_DEFAULT = 30
_DECAY_TICK_INTERVAL_HOURS = 6
_CONSECUTIVE_FAILURES_TO_DISABLE = 5
_STALE_RUNNING_MIN = 5  # jobs marked "running" longer than this at boot → reset


# ── Cron expression parsing ────────────────────────────────────────────────


_ALIAS_MAP = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_field(part: str, lo: int, hi: int) -> set[int]:
    """Parse a single crontab field — supports ``*``, ``*/N``, ``a-b``, ``a,b,c``."""
    out: set[int] = set()
    for chunk in part.split(","):
        step = 1
        if "/" in chunk:
            chunk, step_s = chunk.split("/", 1)
            step = int(step_s)
        if chunk == "*" or chunk == "":
            rng = range(lo, hi + 1, step)
        elif "-" in chunk:
            a, b = chunk.split("-", 1)
            rng = range(int(a), int(b) + 1, step)
        else:
            rng = [int(chunk)]
        for v in rng:
            if lo <= v <= hi:
                out.add(v)
    return out


def compute_next_run(cron_expr: str, *, base: datetime | None = None) -> datetime | None:
    """Compute the next datetime ``cron_expr`` should fire after ``base``.

    Supports:
      - 5-field cron ``minute hour day_of_month month day_of_week`` (UTC).
      - Aliases ``@daily``, ``@hourly``, ``@weekly``, ``@monthly``, ``@yearly``.
      - One-shot ``in 10m`` / ``in 2h`` / ``in 1d`` — returns ``base + delta``.

    Returns ``None`` if the expression is invalid.
    """
    if not cron_expr:
        return None
    base = base or _now_utc()
    expr = cron_expr.strip()

    # One-shot relative.
    m = re.match(r"^in\s+(\d+)\s*([mhd])$", expr)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n),
                 "d": timedelta(days=n)}[unit]
        return base + delta

    if expr in _ALIAS_MAP:
        expr = _ALIAS_MAP[expr]

    parts = expr.split()
    if len(parts) != 5:
        logger.warning("scheduler: invalid cron_expr %r", cron_expr)
        return None
    try:
        mins = _parse_field(parts[0], 0, 59)
        hrs = _parse_field(parts[1], 0, 23)
        doms = _parse_field(parts[2], 1, 31)
        mons = _parse_field(parts[3], 1, 12)
        dows = _parse_field(parts[4], 0, 6)
    except (ValueError, IndexError) as exc:
        logger.warning("scheduler: cron parse failed %r: %s", cron_expr, exc)
        return None

    # Forward-search minute by minute, up to 366 days. cron DOW: 0=Sun..6=Sat;
    # Python weekday(): 0=Mon..6=Sun → convert via (weekday + 1) % 7.
    cand = base.replace(second=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        cron_dow = (cand.weekday() + 1) % 7
        if (cand.minute in mins and cand.hour in hrs
                and cand.day in doms and cand.month in mons
                and cron_dow in dows):
            return cand
        cand += timedelta(minutes=1)
    return None


def is_one_shot(cron_expr: str) -> bool:
    return bool(re.match(r"^in\s+\d+\s*[mhd]$", (cron_expr or "").strip()))


# ── Delivery ───────────────────────────────────────────────────────────────


def deliver_result(text: str, deliver_spec: str, *, user_id: str | None = None) -> str:
    """Best-effort delivery. Returns the actual channel used ('local' fallback).

    Supports:
      - ``"local"`` — log only (default for v0.3).
      - ``"telegram:<chat_id>"`` — push via telegram_gateway outbound.
      - ``"origin"`` — try the user's linked telegram, fallback to local.
    """
    spec = (deliver_spec or "local").strip().lower()
    if spec == "local":
        logger.info("scheduler.deliver[local] user=%s text=%s", user_id, text[:200])
        return "local"
    if spec.startswith("telegram:"):
        chat_id = spec.split(":", 1)[1]
        if _send_telegram(chat_id, text):
            return f"telegram:{chat_id}"
        logger.warning("scheduler: telegram delivery failed, fallback to local")
        return "local"
    if spec == "origin":
        if user_id:
            try:
                from .storage import store
                tg_ids = store.telegram_ids_for_user(user_id)
                for tg_id in tg_ids:
                    if _send_telegram(tg_id, text):
                        return f"telegram:{tg_id}"
            except Exception as exc:
                logger.debug("scheduler: origin lookup failed: %s", exc)
        return "local"
    # Unknown spec → local with warning.
    logger.warning("scheduler: unknown deliver_spec %r, using local", deliver_spec)
    return "local"


def _send_telegram(chat_id: str, text: str) -> bool:
    """Send a text message to a telegram chat via the running gateway, if any.

    Returns True on success. Best-effort: if the gateway isn't reachable,
    we silently fail and let the caller fall back to local.
    """
    try:
        from . import telegram_gateway as _tg
    except Exception:
        return False
    gw = getattr(_tg, "_active_gateway", None)
    if gw is None:
        return False
    send = getattr(gw, "send_text", None)
    if send is None:
        return False
    try:
        # Some gateway impls are async; assume sync wrapper. If async, the
        # scheduler runs in an asyncio task so we can schedule it.
        result = send(chat_id, text)
        if asyncio.iscoroutine(result):
            loop = asyncio.get_event_loop()
            asyncio.ensure_future(result, loop=loop)
        return True
    except Exception as exc:
        logger.debug("scheduler: telegram send raised: %s", exc)
        return False


# ── Tick loop ──────────────────────────────────────────────────────────────


class AgentScheduler:
    """Background scheduler — single instance owned by the FastAPI lifespan."""

    def __init__(self, tick_seconds: int | None = None) -> None:
        self.tick_seconds = tick_seconds or int(
            os.environ.get("AGORA_SCHED_TICK_SECONDS", _TICK_DEFAULT)
        )
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_decay_at: datetime | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="agent-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        logger.info("scheduler: started (tick=%ss)", self.tick_seconds)
        try:
            while not self._stop.is_set():
                try:
                    await self._tick()
                except Exception:
                    logger.exception("scheduler tick failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.tick_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            logger.info("scheduler: stopped")

    async def _tick(self) -> None:
        from .storage import store
        now = _now_utc()
        due = store.list_due_scheduled_jobs(now.isoformat(), limit=20)
        if due:
            logger.info("scheduler: %d job(s) due", len(due))
        loop = asyncio.get_event_loop()
        for job in due:
            await loop.run_in_executor(None, _run_one_job, job.id)

        # Piggyback: decay agent_learnings every N hours (Fase B).
        if (self._last_decay_at is None
                or (now - self._last_decay_at).total_seconds() >= _DECAY_TICK_INTERVAL_HOURS * 3600):
            try:
                _decay_learnings()
            except Exception:
                logger.exception("scheduler: learning decay failed")
            self._last_decay_at = now


def _run_one_job(job_id: str) -> None:
    """Run a single scheduled job synchronously (called from executor)."""
    from .storage import store
    from .agent_pool import LLMSessionConfig
    from .chat_engine import get_pool

    job = store.get_scheduled_job(job_id)
    if job is None or job.status != "active":
        return

    # Skip if next_run_at moved (race with another tick).
    now = _now_utc()
    started_at = now.isoformat()

    result_text = ""
    error_text: str | None = None
    try:
        user = store.user_by_id(job.user_id)
        if user is None:
            raise RuntimeError(f"user {job.user_id} not found")
        cfg = LLMSessionConfig(
            provider=user.llm_provider, api_key=user.llm_api_key,
            base_url=user.llm_base_url, model=user.llm_model,
            api_mode=user.llm_api_mode,
        )
        pool = get_pool()
        session_id = f"sched-{job.id}-{int(now.timestamp())}"
        agent_slug = user.username  # naming convention: agent-<username>
        session = pool.get_or_create(
            user_id=user.id, session_id=session_id,
            agent_slug=agent_slug, llm_config=cfg,
        )
        try:
            run = getattr(session.aiagent, "run_conversation", None)
            if run is None:
                raise RuntimeError("AIAgent has no run_conversation method")
            response = run(job.prompt)
            try:
                from .agent_pool import record_usage_for_session
                record_usage_for_session(
                    user_id=user.id, session_id=session_id,
                    llm_config=cfg, run_output=response, kind="scheduled",
                )
            except Exception:
                logger.debug("scheduler: usage hook failed", exc_info=True)
            if isinstance(response, str):
                result_text = response
            elif isinstance(response, dict):
                result_text = response.get("response") or str(response)
            else:
                result_text = str(response)
        finally:
            pool.evict(user.id, session_id)  # don't pollute the pool with sched sessions
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        logger.exception("scheduler: job %s failed", job_id)

    # Persist outcome + compute next_run_at.
    truncated_result = (result_text[:4000] if result_text else "") or None
    if error_text:
        next_failures = job.consecutive_failures + 1
        new_status = "error" if next_failures >= _CONSECUTIVE_FAILURES_TO_DISABLE else "active"
        store.update_scheduled_job(
            job_id,
            last_run_at=started_at, last_error=error_text,
            runs_total=job.runs_total + 1, runs_failed=job.runs_failed + 1,
            consecutive_failures=next_failures, status=new_status,
            next_run_at=_compute_next_or_none(job),
        )
        return

    # Success path.
    delivered_to = deliver_result(truncated_result or "(empty)",
                                   job.deliver, user_id=job.user_id)
    if is_one_shot(job.cron_expr):
        new_status = "paused"
        new_next = None
    else:
        new_status = "active"
        new_next = _compute_next_or_none(job)
    store.update_scheduled_job(
        job_id,
        last_run_at=started_at, last_result=truncated_result, last_error=None,
        runs_total=job.runs_total + 1, consecutive_failures=0,
        status=new_status, next_run_at=new_next,
    )
    # Best-effort audit.
    try:
        from .models import Event, new_id
        store.record_event(Event(
            id=new_id("evt"),
            event_type="scheduled_job_run",
            actor_id=job.user_id,
            summary=f"job {job.name} → {delivered_to}",
        ))
    except Exception:
        pass


def _compute_next_or_none(job) -> str | None:
    nxt = compute_next_run(job.cron_expr)
    return nxt.isoformat() if nxt else None


def _decay_learnings() -> None:
    """Apply confidence decay to old learnings; prune below threshold."""
    from .storage import store
    threshold_age_days = int(os.environ.get("AGORA_LEARNING_DECAY_DAYS", "30"))
    decay_factor = float(os.environ.get("AGORA_LEARNING_DECAY_FACTOR", "0.95"))
    floor = float(os.environ.get("AGORA_LEARNING_DECAY_FLOOR", "0.05"))
    cur = store.db.conn.execute(
        "UPDATE agent_learnings SET confidence = confidence * ? "
        "WHERE updated_at < datetime('now', '-' || ? || ' days') "
        "AND confidence > ?",
        (decay_factor, threshold_age_days, floor),
    )
    decayed = cur.rowcount or 0
    pruned = store.db.conn.execute(
        "DELETE FROM agent_learnings WHERE confidence < ?", (floor,),
    ).rowcount or 0
    store.db.conn.commit()
    if decayed or pruned:
        logger.info("scheduler.decay: %d decayed, %d pruned", decayed, pruned)


# ── Public helpers (used by the agent-scheduler plugin) ────────────────────


def create_job_with_next_run(
    *, user_id: str, name: str, cron_expr: str, prompt: str,
    deliver: str = "local",
):
    """Insert a scheduled job pre-computing its next_run_at. Returns the job."""
    from .models import ScheduledJob
    from .storage import store

    next_run = compute_next_run(cron_expr)
    if next_run is None:
        raise ValueError(f"invalid cron_expr: {cron_expr}")
    job = ScheduledJob(
        user_id=user_id, name=name, cron_expr=cron_expr, prompt=prompt,
        deliver=deliver, next_run_at=next_run.isoformat(),
    )
    return store.create_scheduled_job(job)


def recompute_next_for(job_id: str) -> str | None:
    """Helper used when resuming a paused job."""
    from .storage import store
    job = store.get_scheduled_job(job_id)
    if job is None:
        return None
    nxt = compute_next_run(job.cron_expr)
    if nxt is None:
        return None
    store.update_scheduled_job(job_id, next_run_at=nxt.isoformat())
    return nxt.isoformat()


# Singleton (the FastAPI lifespan owns this).
_scheduler: AgentScheduler | None = None


def get_scheduler() -> AgentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler
