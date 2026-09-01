"""部门路由（A07）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.dao.dept import DeptDAO
from app.models.dept import Dept
from app.schemas.dept_dict import DeptCreate, DeptOut
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:dept"))])


@router.get("")
def list_depts(db: Session = Depends(get_db)):
    rows = DeptDAO.list(db, limit=500, order_by=Dept.sort)
    return ok([DeptOut.model_validate(d) for d in rows])


@router.post("")
def create_dept(body: DeptCreate, db: Session = Depends(get_db)):
    obj = DeptDAO.create(db, **body.model_dump())
    db.commit()
    return ok(DeptOut.model_validate(obj))


@router.put("/{did}")
def update_dept(did: int, body: DeptCreate, db: Session = Depends(get_db)):
    d = DeptDAO.get(db, did)
    if not d:
        raise HTTPException(404, "部门不存在")
    DeptDAO.update(db, d, **body.model_dump())
    db.commit()
    return ok(DeptOut.model_validate(d))


@router.delete("/{did}")
def delete_dept(did: int, db: Session = Depends(get_db)):
    d = DeptDAO.get(db, did)
    if not d:
        raise HTTPException(404, "部门不存在")
    DeptDAO.delete(db, d)
    db.commit()
    return ok()
