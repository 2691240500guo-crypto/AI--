"""标签字典路由（批次2.1 → 合并后适配 tal_tag）。

2026-09-01 合并适配（hq+）：
- 标签统一用袁文武的 ``tal_tag`` 表（name/category/is_builtin）
- 本 router 改调 ``talent_service`` 的标签函数（list_tags/create_tag/update_tag/delete_tag）
- 保持前端调用路径 /talent-dicts 不变，出参适配前端（含绑定人数统计）
"""
# hq新增内容 - 人才档案批次2.1 + 合并
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.talent import TalentTag, TalentTalentTag
from app.services import talent_service as svc
from app.utils.response import ok

router = APIRouter()


def _with_stats(db: Session, rows: list[TalentTag]) -> list[dict]:
    """为标签列表附带绑定人才数量（前端「绑定人才」列）。

    hq+ 2026-09-01：同时返回 ``type``（合并前 7 大类 code）+ ``category``（袁武原 category），
    前端 tags.vue 用 type 显示合并前的旧分类（fit/experience/level/strength/quality/potential），
    edit.vue 改用 category 与袁武对齐。其他模块不受影响。
    """
    # 袁武 tal_tag.category → 我合并前 7 大类 code 的映射（custom→strength 职业特长）
    _CAT2TYPE = {
        "skill": "skill",          # 专业技能
        "exp": "experience",       # 项目经验
        "level": "level",          # 能力层级
        "position": "fit",         # 适配岗位
        "quality": "quality",      # 综合素质
        "potential": "potential",  # 潜力评级
        "custom": "strength",      # 职业特长（兜底类：泛词/AI抽取标签）
    }
    items = []
    for t in rows:
        cnt = db.query(TalentTalentTag).filter(TalentTalentTag.tag_id == t.id).count()
        names = [
            n[0] for n in db.query(TalentTalentTag.talent_id)
            .filter(TalentTalentTag.tag_id == t.id).limit(5).all()
        ]
        items.append({
            "id": t.id,
            "code": t.name,                                    # 旧字段（兼容）
            "name": t.name,
            "type": _CAT2TYPE.get(t.category, "strength"),     # 合并前旧 code（tags.vue 用）
            "category": t.category,                            # 袁武原 code（edit.vue 用）
            "sort": 0,
            "enabled": 1,
            "talent_count": cnt,
            "talent_names": [],                                 # 简单版不展开姓名（量大），保留字段
            "is_builtin": t.is_builtin,
            "description": t.description,
        })
    return items


@router.get("", summary="标签字典列表（按 category/keyword 过滤，附带绑定人才统计）")
def list_dicts(
    type: str | None = Query(None, description="旧字段 type → category"),
    keyword: str | None = Query(None),
    only_enabled: bool = Query(True),
    db: Session = Depends(get_db),
    user=Depends(require_permission("talent:query")),
):
    rows, total = svc.list_tags(db, keyword=keyword, category=type, page=1, page_size=200)
    return ok({"items": _with_stats(db, rows), "total": total})


@router.post("", summary="新增标签（tal_tag）")
def create_dict(body: dict, db: Session = Depends(get_db),
                user=Depends(require_permission("talent:manage"))):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "标签名不能为空")
    category = (body.get("type") or body.get("category") or "custom").strip()
    desc = body.get("description")
    tag = svc.create_tag(db, name, category=category, description=desc)
    db.commit()
    return ok({"id": tag.id, "name": tag.name, "category": tag.category, "message": "新增成功"})


@router.put("/{did}", summary="修改标签（tal_tag）")
def update_dict(did: int, body: dict, db: Session = Depends(get_db),
                user=Depends(require_permission("talent:manage"))):
    tag = db.get(TalentTag, did)
    if not tag:
        raise HTTPException(404, "标签不存在")
    name = (body.get("name") or tag.name).strip()
    category = (body.get("type") or body.get("category") or tag.category).strip()
    desc = body.get("description") or tag.description
    svc.update_tag(db, did, name=name, category=category, description=desc)
    db.commit()
    return ok({"message": "更新成功"})


@router.delete("/{did}", summary="删除标签（tal_tag）")
def delete_dict(did: int, db: Session = Depends(get_db),
                user=Depends(require_permission("talent:manage"))):
    svc.delete_tag(db, did)
    db.commit()
    return ok({"message": "删除成功"})
