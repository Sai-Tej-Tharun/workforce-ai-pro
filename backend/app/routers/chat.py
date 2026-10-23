"""Module 8: One-to-one chat (REST + WebSocket push, history, read receipts, communication logs)."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatMessage, User, ROLE_ADMIN, ROLE_HR
from ..schemas import ChatSendIn, ChatOut
from ..security import get_current_user, hr_admin
from ..services.common import notify
from ..ws import manager

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/contacts")
def contacts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    users = db.scalars(select(User).where(User.is_active == True, User.id != user.id).order_by(User.full_name)).all()  # noqa: E712
    unread = dict(db.execute(select(ChatMessage.sender_id, func.count()).where(ChatMessage.receiver_id == user.id, ChatMessage.is_read == False)  # noqa: E712
                             .group_by(ChatMessage.sender_id)).all())
    online = set(manager.online_user_ids())
    return [{"id": u.id, "full_name": u.full_name, "role": u.role, "unread": unread.get(u.id, 0), "online": u.id in online} for u in users]


@router.post("", response_model=ChatOut, status_code=201)
def send(body: ChatSendIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.receiver_id == user.id:
        raise HTTPException(422, "Cannot message yourself")
    rcv = db.get(User, body.receiver_id)
    if not rcv or not rcv.is_active:
        raise HTTPException(404, "Recipient not found")
    msg = ChatMessage(sender_id=user.id, receiver_id=rcv.id, content=body.content.strip())
    db.add(msg)
    db.commit()
    out = ChatOut.model_validate(msg).model_dump(mode="json")
    manager.publish_user(rcv.id, {"type": "chat", "data": {**out, "sender_name": user.full_name}})
    return msg


@router.get("/history/{other_id}")
def history(other_id: int, before_id: Optional[int] = None, limit: int = Query(50, ge=1, le=200),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(ChatMessage).where(or_(and_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == other_id),
                                      and_(ChatMessage.sender_id == other_id, ChatMessage.receiver_id == user.id)))
    if before_id:
        q = q.where(ChatMessage.id < before_id)
    rows = list(reversed(db.scalars(q.order_by(ChatMessage.id.desc()).limit(limit)).all()))
    return [ChatOut.model_validate(r) for r in rows]


@router.post("/read/{other_id}")
def mark_conversation_read(other_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Read receipts: marks messages from other_id as read and tells the sender live."""
    now = datetime.utcnow()
    ids = list(db.scalars(select(ChatMessage.id).where(ChatMessage.sender_id == other_id, ChatMessage.receiver_id == user.id,
                                                       ChatMessage.is_read == False)))  # noqa: E712
    if ids:
        db.execute(update(ChatMessage).where(ChatMessage.id.in_(ids)).values(is_read=True, read_at=now))
        db.commit()
        manager.publish_user(other_id, {"type": "chat_read", "data": {"reader_id": user.id, "message_ids": ids, "read_at": now.isoformat() + "Z"}})
    return {"marked": len(ids)}


@router.get("/logs")
def communication_logs(user_id: Optional[int] = None, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
                       db: Session = Depends(get_db), _: User = Depends(hr_admin)):
    """Employee communication logs (metadata only: who, to whom, when, length). HR/Admin."""
    q = select(ChatMessage)
    if user_id:
        q = q.where(or_(ChatMessage.sender_id == user_id, ChatMessage.receiver_id == user_id))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(ChatMessage.id.desc()).offset((page - 1) * size).limit(size)).all()
    names = {u.id: u.full_name for u in db.scalars(select(User))}
    return {"items": [{"id": m.id, "sender": names.get(m.sender_id), "receiver": names.get(m.receiver_id), "chars": len(m.content),
                       "is_read": m.is_read, "created_at": m.created_at} for m in rows], "total": total, "page": page, "size": size}
