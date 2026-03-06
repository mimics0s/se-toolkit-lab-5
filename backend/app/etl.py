"""
ETL pipeline: fetch data from autochecker API and load into database.
"""

from datetime import datetime
import httpx
from dateutil.parser import isoparse
from sqlalchemy import select, func

from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings
from app.models.item import ItemRecord
from app.models.learner import Learner
from app.models.interaction import InteractionLog


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

async def fetch_items() -> list[dict]:

    async with httpx.AsyncClient() as client:

        r = await client.get(
            f"{settings.autochecker_api_url}/api/items",
            auth=(settings.autochecker_email, settings.autochecker_password),
            timeout=30,
        )

        if r.status_code != 200:
            raise Exception(f"Items fetch failed {r.status_code}")

        return r.json()


async def fetch_logs(since: datetime | None = None) -> list[dict]:

    all_logs = []
    has_more = True

    async with httpx.AsyncClient() as client:

        while has_more:

            params = {"limit": 500}

            if since:
                params["since"] = since.isoformat()

            r = await client.get(
                f"{settings.autochecker_api_url}/api/logs",
                auth=(settings.autochecker_email, settings.autochecker_password),
                params=params,
                timeout=30,
            )

            if r.status_code != 200:
                raise Exception(f"Logs fetch failed {r.status_code}")

            data = r.json()

            logs = data.get("logs", [])
            all_logs.extend(logs)

            has_more = data.get("has_more", False)

            if logs:
                since = isoparse(logs[-1]["submitted_at"])

    return all_logs


# ---------------------------------------------------------------------------
# Load items
# ---------------------------------------------------------------------------

async def load_items(items: list[dict], session: AsyncSession) -> int:

    created = 0
    lab_map = {}

    # Labs first
    for item in [x for x in items if x["type"] == "lab"]:

        existing = await session.execute(
            select(ItemRecord).where(
                ItemRecord.type == "lab",
                ItemRecord.title == item["title"],
            )
        )

        if existing.scalar_one_or_none():
            continue

        db_item = ItemRecord(
            type="lab",
            title=item["title"],
        )

        session.add(db_item)
        await session.flush()

        lab_map[item["lab"]] = db_item
        created += 1

    # Tasks second
    for item in [x for x in items if x["type"] == "task"]:

        parent = lab_map.get(item["lab"])
        if not parent:
            continue

        existing = await session.execute(
            select(ItemRecord).where(
                ItemRecord.type == "task",
                ItemRecord.title == item["title"],
                ItemRecord.parent_id == parent.id,
            )
        )

        if existing.scalar_one_or_none():
            continue

        session.add(
            ItemRecord(
                type="task",
                title=item["title"],
                parent_id=parent.id,
            )
        )

        created += 1

    await session.commit()
    return created


# ---------------------------------------------------------------------------
# Load logs
# ---------------------------------------------------------------------------

async def load_logs(
    logs: list[dict],
    items_catalog: list[dict],
    session: AsyncSession,
) -> int:

    # Build lookup map (lab, task) -> title
    lookup = {}

    for it in items_catalog:
        lookup[(it.get("lab"), it.get("task"))] = it["title"]

    created = 0

    for log in logs:

        # Learner
        learner_res = await session.execute(
            select(Learner).where(
                Learner.external_id == log["student_id"]
            )
        )

        learner = learner_res.scalar_one_or_none()

        if not learner:
            learner = Learner(
                external_id=log["student_id"],
                student_group=log.get("group"),
            )

            session.add(learner)
            await session.flush()

        # Item mapping
        title = lookup.get((log["lab"], log["task"]))
        if not title:
            continue

        item_res = await session.execute(
            select(ItemRecord).where(ItemRecord.title == title)
        )

        item = item_res.scalar_one_or_none()
        if not item:
            continue

        # Idempotency
        exists = await session.execute(
            select(InteractionLog).where(
                InteractionLog.external_id == str(log["id"])
            )
        )

        if exists.scalar_one_or_none():
            continue

        session.add(
            InteractionLog(
                external_id=str(log["id"]),
                learner_id=learner.id,
                item_id=item.id,
                kind="attempt",
                score=log.get("score"),
                checks_passed=log["passed"],
                checks_total=log["total"],
                created_at=isoparse(log["submitted_at"]),
            )
        )

        created += 1

    await session.commit()
    return created


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def sync(session: AsyncSession) -> dict:

    # Fetch items + load
    items = await fetch_items()
    await load_items(items, session)

    # Get last sync time
    result = await session.execute(
        select(func.max(InteractionLog.created_at))
    )

    since = result.scalar_one_or_none()

    # Fetch logs incrementally
    logs = await fetch_logs(since)

    new_records = await load_logs(logs, items, session)

    total_res = await session.execute(
        select(func.count()).select_from(InteractionLog)
    )

    return {
        "new_records": new_records,
        "total_records": total_res.scalar(),
    }