"""migrate and retire legacy talent tag tables

Revision ID: e2f6a9c3d701
Revises: c9d4e7f1a203
Create Date: 2026-09-03

Legacy installations may still contain ``tal_talent_dict`` and
``tal_talent_tag_rel``. Their data is merged into ``tal_tag`` and
``tal_talent_tag`` before the old tables are moved to revision-owned backup
names. Renaming keeps downgrade lossless on MySQL and SQLite while removing
the obsolete names from the active schema.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2f6a9c3d701"
down_revision: Union[str, None] = "c9d4e7f1a203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_DICT = "tal_talent_dict"
LEGACY_REL = "tal_talent_tag_rel"
BACKUP_DICT = f"_bak_{revision}_{LEGACY_DICT}"
BACKUP_REL = f"_bak_{revision}_{LEGACY_REL}"

TYPE_TO_CATEGORY = {
    "skill": "skill",
    "experience": "exp",
    "exp": "exp",
    "level": "level",
    "quality": "quality",
    "fit": "position",
    "position": "position",
    "potential": "potential",
    "strength": "custom",
    "custom": "custom",
}


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _rows(bind, table: sa.Table) -> list[dict[str, Any]]:
    return [dict(row) for row in bind.execute(sa.select(table)).mappings().all()]


def _legacy_tag_name(row: dict[str, Any]) -> str:
    value = row.get("name") or row.get("code")
    return str(value).strip() if value is not None else ""


def _category(row: dict[str, Any]) -> str:
    value = str(row.get("category") or row.get("type") or "custom").strip().lower()
    return TYPE_TO_CATEGORY.get(value, "custom")


def _migrate_legacy_data(bind, has_dict: bool, has_rel: bool) -> None:
    metadata = sa.MetaData()
    target_tag = sa.Table("tal_tag", metadata, autoload_with=bind)
    target_rel = sa.Table("tal_talent_tag", metadata, autoload_with=bind)
    talent = sa.Table("tal_talent", metadata, autoload_with=bind)
    legacy_dict = sa.Table(LEGACY_DICT, metadata, autoload_with=bind) if has_dict else None
    legacy_rel = sa.Table(LEGACY_REL, metadata, autoload_with=bind) if has_rel else None

    dict_rows = _rows(bind, legacy_dict) if legacy_dict is not None else []
    rel_rows = _rows(bind, legacy_rel) if legacy_rel is not None else []
    dict_columns = set(legacy_dict.c.keys()) if legacy_dict is not None else set()
    rel_columns = set(legacy_rel.c.keys()) if legacy_rel is not None else set()

    if has_dict and not ({"id"} <= dict_columns and ({"name"} <= dict_columns or {"code"} <= dict_columns)):
        raise RuntimeError(f"{LEGACY_DICT} 缺少 id 及 name/code 字段，无法安全迁移")
    if has_rel and "talent_id" not in rel_columns:
        raise RuntimeError(f"{LEGACY_REL} 缺少 talent_id 字段，无法安全迁移")
    rel_tag_column = "dict_id" if "dict_id" in rel_columns else "tag_id" if "tag_id" in rel_columns else None
    if has_rel and rel_tag_column is None:
        raise RuntimeError(f"{LEGACY_REL} 缺少 dict_id/tag_id 字段，无法安全迁移")
    if has_rel and rel_tag_column == "dict_id" and not has_dict:
        raise RuntimeError(f"{LEGACY_REL}.dict_id 需要 {LEGACY_DICT} 才能映射")

    duplicate_names: dict[str, list[int]] = defaultdict(list)
    for row in dict_rows:
        name = _legacy_tag_name(row)
        if not name:
            raise RuntimeError(f"{LEGACY_DICT} id={row.get('id')} 的 name/code 为空")
        duplicate_names[name].append(int(row["id"]))
    duplicates = {name: ids for name, ids in duplicate_names.items() if len(ids) > 1}
    if duplicates:
        raise RuntimeError(f"{LEGACY_DICT} 存在重复标签名，无法无歧义迁移：{duplicates}")

    dict_by_id = {int(row["id"]): row for row in dict_rows}
    valid_talents = {int(row[0]) for row in bind.execute(sa.select(talent.c.id)).all()}
    problems: list[str] = []
    for row in rel_rows:
        talent_id = row.get("talent_id")
        legacy_tag_id = row.get(rel_tag_column) if rel_tag_column else None
        if talent_id is None or int(talent_id) not in valid_talents:
            problems.append(f"relation id={row.get('id')} 引用无效 talent_id={talent_id}")
        if rel_tag_column == "dict_id" and (
            legacy_tag_id is None or int(legacy_tag_id) not in dict_by_id
        ):
            problems.append(f"relation id={row.get('id')} 引用无效 dict_id={legacy_tag_id}")
    if problems:
        raise RuntimeError("旧人才标签存在孤儿关系：" + "；".join(problems[:20]))

    target_by_name = {
        str(row["name"]): int(row["id"])
        for row in bind.execute(sa.select(target_tag.c.id, target_tag.c.name)).mappings().all()
    }
    legacy_to_target: dict[int, int] = {}
    for row in dict_rows:
        name = _legacy_tag_name(row)
        target_id = target_by_name.get(name)
        if target_id is None:
            values = {
                "name": name,
                "category": _category(row),
                "description": row.get("description"),
                "is_builtin": int(row.get("is_builtin", 1) or 0),
            }
            if "created_at" in target_tag.c:
                values["created_at"] = row.get("created_at") or datetime.now()
            result = bind.execute(sa.insert(target_tag).values(**values))
            target_id = int(result.inserted_primary_key[0])
            target_by_name[name] = target_id
        legacy_to_target[int(row["id"])] = target_id

    existing_relations = {
        (int(row["talent_id"]), int(row["tag_id"])): row
        for row in bind.execute(sa.select(target_rel)).mappings().all()
    }
    for row in rel_rows:
        talent_id = int(row["talent_id"])
        source_tag_id = int(row[rel_tag_column])
        tag_id = legacy_to_target[source_tag_id] if rel_tag_column == "dict_id" else source_tag_id
        if rel_tag_column == "tag_id" and tag_id not in set(target_by_name.values()):
            raise RuntimeError(f"{LEGACY_REL} 引用不存在的 tal_tag.id={tag_id}")
        source = str(row.get("source") or "manual")[:16]
        raw_score = row.get("score", row.get("weight"))
        score = float(raw_score) if raw_score is not None else None
        key = (talent_id, tag_id)
        existing = existing_relations.get(key)
        if existing is None:
            bind.execute(sa.insert(target_rel).values(
                talent_id=talent_id, tag_id=tag_id, source=source, score=score
            ))
            existing_relations[key] = {
                "talent_id": talent_id, "tag_id": tag_id, "source": source, "score": score
            }
            continue
        updates = {}
        if existing.get("source") != "manual" and source == "manual":
            updates["source"] = "manual"
        if existing.get("score") is None and score is not None:
            updates["score"] = score
        if updates:
            bind.execute(sa.update(target_rel).where(
                target_rel.c.talent_id == talent_id,
                target_rel.c.tag_id == tag_id,
            ).values(**updates))


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    required = {"tal_tag", "tal_talent_tag", "tal_talent"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("legacy talent cleanup requires tables: " + ", ".join(missing))

    for legacy, backup in ((LEGACY_DICT, BACKUP_DICT), (LEGACY_REL, BACKUP_REL)):
        if legacy in tables and backup in tables:
            raise RuntimeError(f"{legacy} 与备份表 {backup} 同时存在，请先人工核对")

    has_dict = LEGACY_DICT in tables
    has_rel = LEGACY_REL in tables
    if not has_dict and not has_rel:
        return
    _migrate_legacy_data(bind, has_dict=has_dict, has_rel=has_rel)

    # Rename relation first so parent-table FK metadata remains valid while
    # the dictionary table is renamed. The backup names are intentionally not
    # imported into ORM metadata.
    if has_rel:
        op.rename_table(LEGACY_REL, BACKUP_REL)
    if has_dict:
        op.rename_table(LEGACY_DICT, BACKUP_DICT)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for legacy, backup in ((LEGACY_DICT, BACKUP_DICT), (LEGACY_REL, BACKUP_REL)):
        if legacy in tables and backup in tables:
            raise RuntimeError(f"{legacy} 与备份表 {backup} 同时存在，拒绝覆盖")

    # Restore the parent dictionary name before its relation table.
    if BACKUP_DICT in tables and LEGACY_DICT not in tables:
        op.rename_table(BACKUP_DICT, LEGACY_DICT)
    tables = _table_names(bind)
    if BACKUP_REL in tables and LEGACY_REL not in tables:
        op.rename_table(BACKUP_REL, LEGACY_REL)
