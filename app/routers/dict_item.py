"""数据字典路由（A11）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.dao.dict_item import DictItemDAO, DictTypeDAO
from app.schemas.dept_dict import (DictItemCreate, DictItemOut, DictTypeCreate)
from app.services.dict_service import DictService
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("system:dict"))])


@router.get("/types")
def list_types(db: Session = Depends(get_db)):
    return ok([{"id": t.id, "code": t.code, "name": t.name, "status": t.status}
               for t in DictTypeDAO.list(db, limit=500)])


@router.post("/types")
def create_type(body: DictTypeCreate, db: Session = Depends(get_db)):
    if DictTypeDAO.get_by(db, code=body.code):
        raise HTTPException(400, "字典编码已存在")
    t = DictTypeDAO.create(db, code=body.code, name=body.name, remark=body.remark)
    db.commit()
    return ok(id=t.id)


@router.get("/items/{type_code}")
def items(type_code: str, db: Session = Depends(get_db)):
    return ok([DictItemOut.model_validate(i) for i in DictService.items(db, type_code)])


@router.post("/items")
def create_item(body: DictItemCreate, db: Session = Depends(get_db)):
    obj = DictItemDAO.create(db, **body.model_dump())
    db.commit()
    return ok(DictItemOut.model_validate(obj))


@router.delete("/items/{iid}")
def delete_item(iid: int, db: Session = Depends(get_db)):
    obj = DictItemDAO.get(db, iid)
    if not obj:
        raise HTTPException(404, "字典项不存在")
    DictItemDAO.delete(db, obj)
    db.commit()
    return ok()
