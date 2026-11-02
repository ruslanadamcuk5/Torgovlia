from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(
    db: Session,
    action: str,
    actor: str = "",
    user_id: int | None = None,
    entity: str = "",
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            actor=actor[:120],
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details or {},
        )
    )
