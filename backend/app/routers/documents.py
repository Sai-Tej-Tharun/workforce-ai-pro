"""Module 9: Document management (upload with validation, list, download, delete)."""
import re, uuid, mimetypes
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Document, User, ROLE_ADMIN, ROLE_HR
from ..security import get_current_user
from ..services.common import audit, ensure_employee_access, notify, user_ids_by_role

router = APIRouter(prefix="/documents", tags=["Documents"])
ALLOWED = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff",
           ".docx": b"PK", ".xlsx": b"PK", ".txt": None, ".csv": None}
DOC_TYPES = {"id_proof", "contract", "resume", "certificate", "offer_letter", "payslip", "other"}


def _out(d: Document) -> dict:
    return {"id": d.id, "employee_id": d.employee_id, "doc_type": d.doc_type, "original_name": d.original_name,
            "content_type": d.content_type, "size_bytes": d.size_bytes, "created_at": d.created_at}


@router.post("", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), employee_id: Optional[int] = Form(None),
                 doc_type: str = Form("other"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    eid = employee_id if (employee_id and user.role in (ROLE_ADMIN, ROLE_HR)) else user.employee_id
    if not eid:
        raise HTTPException(400, "No employee profile linked to this account")
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of {sorted(DOC_TYPES)}")
    name = re.sub(r"[^\w.\- ]", "_", Path(file.filename or "file").name)[:200]
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, f"File type {ext or '(none)'} not allowed. Allowed: {', '.join(sorted(ALLOWED))}")
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB} MB")
    if not data:
        raise HTTPException(422, "Empty file")
    magic = ALLOWED[ext]
    if magic and not data.startswith(magic):  # validate content, not just extension
        raise HTTPException(422, "File content does not match its extension")
    stored = f"{uuid.uuid4().hex}{ext}"
    (settings.UPLOAD_DIR / stored).write_bytes(data)
    doc = Document(employee_id=eid, doc_type=doc_type, original_name=name, stored_name=stored,
                   content_type=mimetypes.guess_type(name)[0] or "application/octet-stream", size_bytes=len(data), uploaded_by=user.id)
    db.add(doc)
    db.commit()
    audit(db, user, "UPLOAD", "document", doc.id, {"name": name, "employee_id": eid}, request)
    return _out(doc)


@router.get("")
def list_documents(employee_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    eid = employee_id or (user.employee_id if user.role not in (ROLE_ADMIN, ROLE_HR) else None)
    if eid:
        if user.role not in (ROLE_ADMIN, ROLE_HR) and eid != user.employee_id:
            raise HTTPException(403, "You can only view your own documents")
    elif user.role not in (ROLE_ADMIN, ROLE_HR):
        return []
    q = select(Document).order_by(Document.id.desc())
    if eid:
        q = q.where(Document.employee_id == eid)
    return [_out(d) for d in db.scalars(q.limit(500))]


def _get_allowed(db, user, did) -> Document:
    d = db.get(Document, did)
    if not d:
        raise HTTPException(404, "Document not found")
    if user.role not in (ROLE_ADMIN, ROLE_HR) and d.employee_id != user.employee_id:
        raise HTTPException(403, "Not allowed")
    return d


@router.get("/{did}/download")
def download(did: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = _get_allowed(db, user, did)
    path = settings.UPLOAD_DIR / d.stored_name
    if not path.exists():
        raise HTTPException(410, "File missing from storage")
    audit(db, user, "DOWNLOAD", "document", did, request=request)
    return FileResponse(path, media_type=d.content_type, filename=d.original_name)


@router.delete("/{did}", status_code=204)
def delete(did: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = _get_allowed(db, user, did)
    if user.role not in (ROLE_ADMIN, ROLE_HR) and d.uploaded_by != user.id:
        raise HTTPException(403, "Only HR or the uploader can delete")
    (settings.UPLOAD_DIR / d.stored_name).unlink(missing_ok=True)
    db.delete(d)
    db.commit()
    audit(db, user, "DELETE", "document", did, {"name": d.original_name}, request)
