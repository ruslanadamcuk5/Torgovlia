from sqlalchemy.orm import Session

from app.models import AuditLog
from app.tenancy import current_tenant_id


def audit(
    db: Session,
    action: str,
    actor: str = "",
    user_id: int | None = None,
    entity: str = "",
    entity_id: str | None = None,
    details: dict | None = None,
    tenant_id: int | None = None,
) -> None:
    if tenant_id is None:
        tenant_id = current_tenant_id()
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            actor=actor[:120],
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details or {},
        )
    )
