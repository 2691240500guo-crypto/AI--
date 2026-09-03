#袁文武新增2026-08-31 17:10:00开始
"""人才档案 DAO（模块一）。

继承 BaseDAO 获得单表 CRUD，叠加本模块特有的多条件组合查询、标签筛选、
查重与批量取数能力。所有查询走 SQLAlchemy ORM，禁裸 SQL。
"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.dao.base import BaseDAO
from app.models.talent import Talent, TalentTag, TalentTalentTag


# 人才域通用预加载：标签/教育/工作/项目（避免列表/导出/统计接口 N+1 懒加载）
_TALENT_LOAD = (
    selectinload(Talent.tag_rels).selectinload(TalentTalentTag.tag),
    selectinload(Talent.educations),
    selectinload(Talent.works),
    selectinload(Talent.projects),
)


class TalentDAO(BaseDAO[Talent]):
    __model__ = Talent

    # ---------- 多条件组合分页（需求④ 多维查询统计）----------
    @classmethod
    def count(cls, db: Session, *, keyword: str | None = None, tag: str | None = None,
              education: str | None = None, skill: str | None = None,
              years_min: int | None = None, level: str | None = None,
              only_valid: bool = True) -> int:
        stmt = cls._build_where(keyword=keyword, tag=tag, education=education,
                                skill=skill, years_min=years_min, level=level,
                                only_valid=only_valid)
        return db.scalar(select(func.count()).select_from(Talent).where(*stmt)) or 0

    @classmethod
    def paged(cls, db: Session, *, keyword: str | None = None, tag: str | None = None,
              education: str | None = None, skill: str | None = None,
              years_min: int | None = None, level: str | None = None,
              only_valid: bool = True, page: int = 1, page_size: int = 20) -> list[Talent]:
        conds = cls._build_where(keyword=keyword, tag=tag, education=education,
                                 skill=skill, years_min=years_min, level=level,
                                 only_valid=only_valid)
        stmt = select(Talent).where(*conds).order_by(Talent.id.desc())
        stmt = stmt.options(*_TALENT_LOAD)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())

    @classmethod
    def _build_where(cls, *, keyword=None, tag=None, education=None, skill=None,
                     years_min=None, level=None, only_valid=True) -> list:
        conds: list = []
        if only_valid:
            conds.append(Talent.status == 1)
        if keyword:
            like = f"%{keyword}%"
            conds.append(or_(Talent.name.like(like), Talent.skills.like(like),
                             Talent.work_experience.like(like), Talent.project_experience.like(like)))
        if education:
            conds.append(Talent.highest_education == education)
        if skill:
            conds.append(Talent.skills.like(f"%{skill}%"))
        if years_min is not None:
            conds.append(Talent.years_experience >= years_min)
        if tag:
            conds.append(Talent.id.in_(
                select(TalentTalentTag.talent_id)
                .join(TalentTag, TalentTag.id == TalentTalentTag.tag_id)
                .where(TalentTag.name == tag)))
        if level:  # 能力层级标签（初级/中级/高级/…）；画像派生标签落库时为 custom 分类（uk_name 全局唯一），故按 name 精确匹配、不限 category
            conds.append(Talent.id.in_(
                select(TalentTalentTag.talent_id)
                .join(TalentTag, TalentTag.id == TalentTalentTag.tag_id)
                .where(TalentTag.name == level)))
        return conds

    # ---------- 查重辅助（需求③ 智能查重）----------
    @classmethod
    def find_by_identity(cls, db: Session, *, name: str | None = None,
                         phone: str | None = None, email: str | None = None,
                         exclude_id: int | None = None) -> list[Talent]:
        conds = [Talent.status == 1]
        identity = []
        if name:
            identity.append(Talent.name == name)
        if phone:
            identity.append(Talent.phone == phone)
        if email:
            identity.append(Talent.email == email)
        if not identity:
            return []
        stmt = select(Talent).where(*conds, or_(*identity))
        if exclude_id:
            stmt = stmt.where(Talent.id != exclude_id)
        return list(db.scalars(stmt).all())

    @classmethod
    def list_by_ids(cls, db: Session, ids: list[int], only_valid: bool = False) -> list[Talent]:
        if not ids:
            return []
        conds = [Talent.id.in_(ids)]
        if only_valid:
            conds.append(Talent.status == 1)
        return list(db.scalars(select(Talent).where(*conds)).all())

    @classmethod
    def list_all_valid(cls, db: Session, limit: int = 2000) -> list[Talent]:
        return list(db.scalars(
            select(Talent).where(Talent.status == 1).options(*_TALENT_LOAD).limit(limit)
        ).all())

    # hq+  按姓名/手机号精确查询（我的去重模块 detect_duplicate 复用）
    @classmethod
    def get_by_name(cls, db: Session, name: str) -> Talent | None:
        return db.scalar(select(Talent).where(Talent.name == name))

    @classmethod
    def get_by_phone(cls, db: Session, phone: str) -> Talent | None:
        if not phone:
            return None
        return db.scalar(select(Talent).where(Talent.phone == phone))


class TagDAO(BaseDAO[TalentTag]):
    __model__ = TalentTag

    @classmethod
    def get_by_name(cls, db: Session, name: str) -> TalentTag | None:
        return db.scalar(select(TalentTag).where(TalentTag.name == name))

    @classmethod
    def ensure_tags(cls, db: Session, names: list[str], *, category: str = "custom",
                    source: str = "manual") -> list[TalentTag]:
        """确保标签存在（内置或自定义），返回 TalentTag 列表。"""
        result: list[TalentTag] = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            tag = cls.get_by_name(db, n)
            if tag is None:
                tag = TalentTag(name=n, category=category, is_builtin=0 if source == "manual" else 1)
                db.add(tag)
                db.flush()
            result.append(tag)
        return result

    @classmethod
    def seed_builtin(cls, db: Session, items: list[tuple[str, str, str]]) -> int:
        """幂等写入内置标签库（200+ 多维度标签）。返回新增条数。"""
        added = 0
        for name, category, desc in items:
            if cls.get_by_name(db, name) is None:
                db.add(TalentTag(name=name, category=category, description=desc, is_builtin=1))
                added += 1
        db.flush()
        return added


class TalentTagRelDAO(BaseDAO[TalentTalentTag]):
    __model__ = TalentTalentTag

    @classmethod
    def set_ai_tags(cls, db: Session, talent_id: int, tag_ids: list[int],
                   scores: dict[int, float | None] | None = None) -> None:
        """Upsert AI 自动标签关系：已存在则刷新（手动标签保留来源），不存在则新增，
        不在新集合中的旧 AI 标签则清理。避免 (talent_id, tag_id) 唯一约束冲突。"""
        scores = scores or {}
        rels = list(db.scalars(
            select(TalentTalentTag).where(TalentTalentTag.talent_id == talent_id)).all())
        rel_by_tag = {r.tag_id: r for r in rels}
        new_set = set(tag_ids)
        for tid in tag_ids:
            rel = rel_by_tag.get(tid)
            if rel is None:
                db.add(TalentTalentTag(talent_id=talent_id, tag_id=tid,
                                       source="ai", score=scores.get(tid)))
            elif rel.source == "manual":
                rel.score = scores.get(tid)            # 手动标签保留来源，仅补分数
            else:
                rel.source = "ai"
                rel.score = scores.get(tid)
        # 清理不再属于本次 AI 画像的旧 AI 标签
        for r in rels:
            if r.source == "ai" and r.tag_id not in new_set:
                db.delete(r)
        db.flush()
#袁文武新增2026-08-31 17:10:00结束

#袁文武新增2026-08-31 23:30:00开始
from app.models.talent import TalentCertificate


class CertificateDAO(BaseDAO[TalentCertificate]):
    __model__ = TalentCertificate

    @classmethod
    def list_by_talent(cls, db: Session, talent_id: int) -> list[TalentCertificate]:
        return list(db.scalars(
            select(TalentCertificate).where(TalentCertificate.talent_id == talent_id)
            .order_by(TalentCertificate.id.desc())).all())

    @classmethod
    def replace_by_talent(cls, db: Session, talent_id: int, items: list[dict]) -> None:
        """全量替换某人才的证书列表。"""
        db.execute(TalentCertificate.__table__.delete()
                   .where(TalentCertificate.talent_id == talent_id))
        for item in items:
            db.add(TalentCertificate(talent_id=talent_id, **item))
        db.flush()
#袁文武新增2026-08-31 23:30:00结束
