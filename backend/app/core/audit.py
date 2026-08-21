from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AdminAuditLog
from app.models.user import User


async def log_admin_action(
    db: AsyncSession,
    *,
    admin_user: User,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            before=before,
            after=after,
        )
    )
    await db.flush()
