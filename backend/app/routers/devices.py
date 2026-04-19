import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Device, User

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegisterIn(BaseModel):
    label: str
    type: str  # pos | door | admin


class DeviceOut(BaseModel):
    id: str
    label: str
    type: str
    last_sync_at: datetime | None


@router.post("/register", response_model=DeviceOut)
def register(
    body: DeviceRegisterIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    """Registra un nuevo dispositivo para el venue del usuario y devuelve su ID."""
    dev = Device(venue_id=user.venue_id, label=body.label, type=body.type)
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return DeviceOut(id=str(dev.id), label=dev.label, type=dev.type, last_sync_at=dev.last_sync_at)


@router.get("", response_model=list[DeviceOut])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Device).where(Device.venue_id == user.venue_id)).scalars().all()
    return [
        DeviceOut(id=str(d.id), label=d.label, type=d.type, last_sync_at=d.last_sync_at)
        for d in rows
    ]


class DeviceHeartbeat(BaseModel):
    device_id: str


@router.post("/heartbeat")
def heartbeat(body: DeviceHeartbeat, db: Session = Depends(get_db)):
    try:
        dev_id = uuid.UUID(body.device_id)
    except ValueError:
        return {"ok": False}
    dev = db.get(Device, dev_id)
    if dev:
        dev.last_sync_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}
