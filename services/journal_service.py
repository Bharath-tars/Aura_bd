from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from models.journal import JournalEntry


async def create_journal_entry(
    db: AsyncSession,
    user_id: str,
    title: str,
    content: str,
    plan_id: str | None = None,
) -> JournalEntry:
    entry = JournalEntry(
        user_id=user_id, title=title, content=content,
        word_count=len(content.split()),
        plan_id=plan_id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_journal_entries(db: AsyncSession, user_id: str,
                                skip: int = 0, limit: int = 20) -> tuple[list[JournalEntry], int]:
    total = await db.scalar(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.user_id == user_id)
    )
    result = await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == user_id)
        .order_by(desc(JournalEntry.created_at)).offset(skip).limit(limit)
    )
    return result.scalars().all(), total or 0


async def get_journal_entry(db: AsyncSession, user_id: str, entry_id: str) -> JournalEntry | None:
    return await db.scalar(
        select(JournalEntry).where(JournalEntry.user_id == user_id, JournalEntry.id == entry_id)
    )


async def update_journal_entry(db: AsyncSession, entry: JournalEntry,
                                title: str | None, content: str | None) -> JournalEntry:
    if title is not None:
        entry.title = title
    if content is not None:
        entry.content = content
        entry.word_count = len(content.split())
        entry.analyzed = False  # re-analysis needed after content change
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_plan_journal_entries(
    db: AsyncSession, user_id: str, plan_id: str
) -> list[JournalEntry]:
    result = await db.execute(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id, JournalEntry.plan_id == plan_id)
        .order_by(desc(JournalEntry.created_at))
    )
    return list(result.scalars().all())


async def save_ai_insights(db: AsyncSession, entry: JournalEntry,
                            insights: list[dict], sentiment: float | None,
                            themes: list[str]) -> JournalEntry:
    entry.ai_insights = insights
    entry.sentiment_score = sentiment
    entry.themes = themes
    entry.analyzed = True
    await db.commit()
    await db.refresh(entry)
    return entry
