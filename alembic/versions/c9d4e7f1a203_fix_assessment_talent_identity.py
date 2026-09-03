"""separate assessment talent identity from login account identity

Revision ID: c9d4e7f1a203
Revises: d4e5f6a7b8c9
Create Date: 2026-09-03

``asm_result.talent_id`` originally stored ``sys_user.id``. The application
now needs both identities: ``talent_id`` points at ``tal_talent.id`` and the
new ``user_id`` points at ``sys_user.id``.

The two backup tables deliberately remain after a successful upgrade. They
are migration-owned (not ORM tables) and let downgrade restore the exact
pre-upgrade values even on databases whose DDL is not transactional.
"""

from collections import defaultdict
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9d4e7f1a203"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKUP_TABLE = "asm_result_identity_backup"
BACKUP_META_TABLE = "asm_result_identity_backup_meta"
CREATED_TALENT_TABLE = "asm_result_identity_created_talent"
BACKUP_REVISION = revision
SQLITE_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
}


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _columns(inspector: sa.Inspector, table: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(table)}


def _foreign_keys(inspector: sa.Inspector, table: str, column: str) -> list[dict]:
    return [
        foreign_key
        for foreign_key in inspector.get_foreign_keys(table)
        if foreign_key.get("constrained_columns") == [column]
    ]


def _foreign_key_target(inspector: sa.Inspector, table: str, column: str) -> str | None:
    foreign_keys = _foreign_keys(inspector, table, column)
    targets = {foreign_key.get("referred_table") for foreign_key in foreign_keys}
    if len(targets) > 1:
        raise RuntimeError(f"{table}.{column} 存在多个目标不同的外键，无法安全迁移")
    return next(iter(targets), None)


def _constraint_name(table: str, column: str, foreign_key: dict) -> str:
    name = foreign_key.get("name")
    if name:
        return name
    return f"fk_{table}_{column}_{foreign_key.get('referred_table')}"


def _create_backup_tables(bind, meta: dict) -> None:
    inspector = sa.inspect(bind)
    has_data = _table_exists(inspector, BACKUP_TABLE)
    has_meta = _table_exists(inspector, BACKUP_META_TABLE)
    if has_data != has_meta:
        raise RuntimeError("测评身份迁移备份表不完整，请先人工检查数据库")

    if not has_data:
        op.create_table(
            BACKUP_META_TABLE,
            sa.Column("revision_id", sa.String(length=32), nullable=False),
            sa.Column("talent_fk_target", sa.String(length=64), nullable=True),
            sa.Column("user_fk_target", sa.String(length=64), nullable=True),
            sa.Column("user_id_column_existed", sa.Boolean(), nullable=False),
            sa.Column("user_id_nullable", sa.Boolean(), nullable=True),
            sa.Column("user_id_index_existed", sa.Boolean(), nullable=False),
            sa.Column("talent_id_nullable", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("revision_id"),
        )
        op.create_table(
            BACKUP_TABLE,
            sa.Column("result_id", sa.Integer(), nullable=False),
            sa.Column("talent_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("result_id"),
        )
        bind.execute(
            sa.text(
                f"INSERT INTO {BACKUP_META_TABLE} "
                "(revision_id, talent_fk_target, user_fk_target, "
                "user_id_column_existed, user_id_nullable, user_id_index_existed, "
                "talent_id_nullable) "
                "VALUES (:revision_id, :talent_fk_target, :user_fk_target, "
                ":user_id_column_existed, :user_id_nullable, :user_id_index_existed, "
                ":talent_id_nullable)"
            ),
            {**meta, "revision_id": BACKUP_REVISION},
        )
        bind.execute(
            sa.text(
                f"INSERT INTO {BACKUP_TABLE} (result_id, talent_id, user_id) "
                "SELECT id, talent_id, user_id FROM asm_result"
            )
        )
        return

    saved_meta = bind.execute(
        sa.text(
            f"SELECT revision_id FROM {BACKUP_META_TABLE} "
            "WHERE revision_id = :revision_id"
        ),
        {"revision_id": BACKUP_REVISION},
    ).first()
    if not saved_meta:
        # MySQL DDL is non-transactional: a failed first attempt can leave the
        # two empty tables behind while rolling back their INSERT statements.
        # Re-populating is safe only when both tables are still empty.
        meta_count = int(bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {BACKUP_META_TABLE}"
        )).scalar() or 0)
        backup_count = int(bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {BACKUP_TABLE}"
        )).scalar() or 0)
        if meta_count or backup_count:
            raise RuntimeError("测评身份迁移备份不完整，请先人工检查数据库")
        bind.execute(
            sa.text(
                f"INSERT INTO {BACKUP_META_TABLE} "
                "(revision_id, talent_fk_target, user_fk_target, "
                "user_id_column_existed, user_id_nullable, user_id_index_existed, "
                "talent_id_nullable) "
                "VALUES (:revision_id, :talent_fk_target, :user_fk_target, "
                ":user_id_column_existed, :user_id_nullable, :user_id_index_existed, "
                ":talent_id_nullable)"
            ),
            {**meta, "revision_id": BACKUP_REVISION},
        )
        bind.execute(sa.text(
            f"INSERT INTO {BACKUP_TABLE} (result_id, talent_id, user_id) "
            "SELECT id, talent_id, user_id FROM asm_result"
        ))
        return

    current_count = int(bind.execute(sa.text("SELECT COUNT(*) FROM asm_result")).scalar() or 0)
    backup_count = int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {BACKUP_TABLE}")).scalar() or 0)
    missing_count = int(bind.execute(sa.text(
        f"SELECT COUNT(*) FROM asm_result r LEFT JOIN {BACKUP_TABLE} b "
        "ON b.result_id = r.id WHERE b.result_id IS NULL"
    )).scalar() or 0)
    stale_count = int(bind.execute(sa.text(
        f"SELECT COUNT(*) FROM {BACKUP_TABLE} b LEFT JOIN asm_result r "
        "ON r.id = b.result_id WHERE r.id IS NULL"
    )).scalar() or 0)
    if current_count != backup_count or missing_count or stale_count:
        raise RuntimeError("asm_result 与已有身份备份不一致；禁止覆盖备份，请先停止写入并人工核对")


def _ensure_created_talent_table(bind) -> None:
    if _table_exists(sa.inspect(bind), CREATED_TALENT_TABLE):
        return
    op.create_table(
        CREATED_TALENT_TABLE,
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("talent_id", sa.Integer(), nullable=False),
        sa.Column("original_talent_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("talent_id"),
    )


def _create_missing_talent_mappings(bind, source_fk_target: str | None) -> None:
    """Create traceable compatibility profiles for legacy account-only results.

    Historic data allowed an assessment result to point directly at any
    ``sys_user`` row. Some of those accounts (notably old demo admins) never
    had a talent profile, so there is no existing target for the new foreign
    key. Keeping the original result is preferable to deleting it: create one
    minimal profile per affected account and record the exact mapping for
    downgrade.
    """
    if source_fk_target not in {None, "sys_user"}:
        return
    _ensure_created_talent_table(bind)
    inspector = sa.inspect(bind)
    user_columns = _columns(inspector, "sys_user")
    username_expression = "u.username" if "username" in user_columns else "NULL"
    nickname_expression = "u.nickname" if "nickname" in user_columns else "NULL"
    rows = bind.execute(sa.text(
        f"SELECT DISTINCT u.id, {username_expression} AS username, "
        f"{nickname_expression} AS nickname, u.talent_id "
        f"FROM {BACKUP_TABLE} b JOIN sys_user u ON u.id = b.talent_id "
        "WHERE u.talent_id IS NULL ORDER BY u.id"
    )).mappings().all()
    talent_table = sa.Table("tal_talent", sa.MetaData(), autoload_with=bind)
    talent_columns = set(talent_table.c.keys())
    for row in rows:
        tracked = bind.execute(sa.text(
            f"SELECT talent_id FROM {CREATED_TALENT_TABLE} WHERE user_id = :user_id"
        ), {"user_id": int(row["id"])}).scalar()
        if tracked is not None:
            exists = bind.execute(sa.text(
                "SELECT COUNT(*) FROM tal_talent WHERE id = :talent_id"
            ), {"talent_id": int(tracked)}).scalar()
            if not exists:
                raise RuntimeError(
                    f"迁移记录的兼容人才档案 {tracked} 已丢失，禁止继续"
                )
            bind.execute(sa.text(
                "UPDATE sys_user SET talent_id = :talent_id WHERE id = :user_id"
            ), {"talent_id": int(tracked), "user_id": int(row["id"])})
            continue

        display_name = (row["nickname"] or row["username"] or f"历史用户{row['id']}")[:64]
        candidate_values = {
            "name": display_name,
            "years_experience": 0,
            "resume_source": "assessment_migration",
            "status": 1,
            "data_quality": "warning",
            "quality_remark": f"由测评身份迁移自动补建（历史账号 #{row['id']}）",
            "created_by": int(row["id"]),
        }
        values = {
            name: value
            for name, value in candidate_values.items()
            if name in talent_columns
        }
        result = bind.execute(talent_table.insert().values(**values))
        inserted_key = result.inserted_primary_key[0] if result.inserted_primary_key else None
        talent_id = int(inserted_key if inserted_key is not None else result.lastrowid)
        bind.execute(sa.text(
            f"INSERT INTO {CREATED_TALENT_TABLE} "
            "(user_id, talent_id, original_talent_id) VALUES (:user_id, :talent_id, NULL)"
        ), {"user_id": int(row["id"]), "talent_id": talent_id})
        bind.execute(sa.text(
            "UPDATE sys_user SET talent_id = :talent_id WHERE id = :user_id"
        ), {"talent_id": talent_id, "user_id": int(row["id"])})


def _remove_created_talent_mappings(bind) -> None:
    if not _table_exists(sa.inspect(bind), CREATED_TALENT_TABLE):
        return
    mappings = bind.execute(sa.text(
        f"SELECT user_id, talent_id, original_talent_id FROM {CREATED_TALENT_TABLE} "
        "ORDER BY user_id"
    )).mappings().all()
    if not mappings:
        return

    for row in mappings:
        current = bind.execute(sa.text(
            "SELECT talent_id FROM sys_user WHERE id = :user_id"
        ), {"user_id": int(row["user_id"])}).scalar()
        if current != row["talent_id"]:
            raise RuntimeError(
                f"无法回滚：历史账号 {row['user_id']} 的人才映射已被业务修改"
            )

    # Reject downgrade if a compatibility profile acquired business records
    # after the migration; silently deleting those records would be data loss.
    tracked_ids = [int(row["talent_id"]) for row in mappings]
    inspector = sa.inspect(bind)
    ignored_tables = {"sys_user", "asm_result", CREATED_TALENT_TABLE}
    for table in inspector.get_table_names():
        if table in ignored_tables:
            continue
        for foreign_key in inspector.get_foreign_keys(table):
            if (
                foreign_key.get("referred_table") != "tal_talent"
                or foreign_key.get("referred_columns") != ["id"]
                or len(foreign_key.get("constrained_columns") or []) != 1
            ):
                continue
            column = foreign_key["constrained_columns"][0]
            quoted_table = bind.dialect.identifier_preparer.quote(table)
            quoted_column = bind.dialect.identifier_preparer.quote(column)
            count = int(bind.execute(
                sa.text(
                    f"SELECT COUNT(*) FROM {quoted_table} "
                    f"WHERE {quoted_column} IN :talent_ids"
                ).bindparams(sa.bindparam("talent_ids", expanding=True)),
                {"talent_ids": tracked_ids},
            ).scalar() or 0)
            if count:
                raise RuntimeError(
                    f"无法回滚：迁移创建的人才档案已被 {table}.{column} 引用"
                )

    for row in mappings:
        bind.execute(sa.text(
            "UPDATE sys_user SET talent_id = :original_talent_id WHERE id = :user_id"
        ), {
            "original_talent_id": row["original_talent_id"],
            "user_id": int(row["user_id"]),
        })
    bind.execute(
        sa.text("DELETE FROM tal_talent WHERE id IN :talent_ids").bindparams(
            sa.bindparam("talent_ids", expanding=True)
        ),
        {"talent_ids": tracked_ids},
    )


def _load_backup_meta(bind) -> dict:
    row = bind.execute(
        sa.text(
            "SELECT talent_fk_target, user_fk_target, user_id_column_existed, "
            "user_id_nullable, user_id_index_existed, talent_id_nullable "
            f"FROM {BACKUP_META_TABLE} WHERE revision_id = :revision_id"
        ),
        {"revision_id": BACKUP_REVISION},
    ).mappings().first()
    if not row:
        raise RuntimeError("找不到测评身份迁移备份元数据，无法安全回滚")
    return dict(row)


def _resolve_identity_rows(bind, source_fk_target: str | None) -> list[dict[str, int]]:
    user_rows = bind.execute(sa.text("SELECT id, talent_id FROM sys_user")).mappings().all()
    users = {int(row["id"]): row["talent_id"] for row in user_rows}
    users_by_talent: dict[int, list[int]] = defaultdict(list)
    for user_id, talent_id in users.items():
        if talent_id is not None:
            users_by_talent[int(talent_id)].append(user_id)
    talents = {int(row[0]) for row in bind.execute(sa.text("SELECT id FROM tal_talent")).all()}

    mappings: list[dict[str, int]] = []
    problems: list[str] = []
    backup_rows = bind.execute(sa.text(
        f"SELECT result_id, talent_id, user_id FROM {BACKUP_TABLE} ORDER BY result_id"
    )).mappings().all()

    for row in backup_rows:
        result_id = int(row["result_id"])
        original_talent_id = int(row["talent_id"])
        original_user_id = int(row["user_id"]) if row["user_id"] is not None else None
        candidates: set[tuple[int, int]] = set()

        if source_fk_target == "sys_user":
            mapped_talent_id = users.get(original_talent_id)
            if mapped_talent_id is not None and int(mapped_talent_id) in talents:
                candidates.add((original_talent_id, int(mapped_talent_id)))
            if original_user_id is not None and original_user_id != original_talent_id:
                problems.append(
                    f"result_id={result_id} 的原 user_id={original_user_id} "
                    f"与旧 talent_id={original_talent_id} 冲突"
                )
                continue
        elif source_fk_target == "tal_talent":
            if original_talent_id in talents:
                if original_user_id is not None:
                    if users.get(original_user_id) == original_talent_id:
                        candidates.add((original_user_id, original_talent_id))
                else:
                    candidates.update(
                        (user_id, original_talent_id)
                        for user_id in users_by_talent.get(original_talent_id, [])
                    )
        else:
            # A manually-created database may have no FK. Resolve only when a
            # row has exactly one possible (user, talent) pair.
            if original_user_id is not None:
                linked_talent_id = users.get(original_user_id)
                if linked_talent_id is not None and int(linked_talent_id) in talents:
                    candidates.add((original_user_id, int(linked_talent_id)))
            else:
                linked_talent_id = users.get(original_talent_id)
                if linked_talent_id is not None and int(linked_talent_id) in talents:
                    candidates.add((original_talent_id, int(linked_talent_id)))
                if original_talent_id in talents:
                    candidates.update(
                        (user_id, original_talent_id)
                        for user_id in users_by_talent.get(original_talent_id, [])
                    )

        if len(candidates) != 1:
            reason = "无有效映射" if not candidates else "存在多条候选映射"
            problems.append(f"result_id={result_id} {reason}")
            continue
        user_id, talent_id = candidates.pop()
        mappings.append({"result_id": result_id, "user_id": user_id, "talent_id": talent_id})

    if problems:
        preview = "；".join(problems[:10])
        suffix = "……" if len(problems) > 10 else ""
        raise RuntimeError(
            f"无法安全迁移 {len(problems)} 条 asm_result：{preview}{suffix}。"
            "请先补齐或去重 sys_user.talent_id 映射"
        )
    return mappings


def _drop_identity_foreign_keys(batch_op, inspector: sa.Inspector) -> None:
    for column in ("talent_id", "user_id"):
        for foreign_key in _foreign_keys(inspector, "asm_result", column):
            batch_op.drop_constraint(
                _constraint_name("asm_result", column, foreign_key), type_="foreignkey"
            )


def _remove_identity_foreign_keys(bind) -> None:
    """Remove old identity constraints before rewriting their key values."""
    inspector = sa.inspect(bind)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "asm_result", recreate="always", naming_convention=SQLITE_NAMING_CONVENTION
        ) as batch_op:
            _drop_identity_foreign_keys(batch_op, inspector)
        return
    for column in ("talent_id", "user_id"):
        for foreign_key in _foreign_keys(inspector, "asm_result", column):
            op.drop_constraint(
                _constraint_name("asm_result", column, foreign_key),
                "asm_result", type_="foreignkey",
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required = {"asm_result", "sys_user", "tal_talent"}
    missing = sorted(table for table in required if not _table_exists(inspector, table))
    if missing:
        raise RuntimeError("assessment identity migration requires tables: " + ", ".join(missing))
    if "talent_id" not in _columns(inspector, "sys_user"):
        raise RuntimeError("assessment identity migration requires sys_user.talent_id")

    result_columns = _columns(inspector, "asm_result")
    user_id_existed = "user_id" in result_columns
    # Recover the precise pre-migration shape after a MySQL failure that
    # committed ADD COLUMN / CREATE TABLE but rolled back all backup rows.
    empty_partial_attempt = False
    if user_id_existed and all(
        _table_exists(inspector, table) for table in (BACKUP_TABLE, BACKUP_META_TABLE)
    ):
        meta_count = int(bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {BACKUP_META_TABLE}"
        )).scalar() or 0)
        backup_count = int(bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {BACKUP_TABLE}"
        )).scalar() or 0)
        populated_user_ids = int(bind.execute(sa.text(
            "SELECT COUNT(*) FROM asm_result WHERE user_id IS NOT NULL"
        )).scalar() or 0)
        empty_partial_attempt = not meta_count and not backup_count and not populated_user_ids
    original_user_id_existed = user_id_existed and not empty_partial_attempt
    talent_fk_target = _foreign_key_target(inspector, "asm_result", "talent_id")
    user_fk_target = (
        _foreign_key_target(inspector, "asm_result", "user_id") if user_id_existed else None
    )
    if talent_fk_target not in {None, "sys_user", "tal_talent"}:
        raise RuntimeError(f"不支持的 asm_result.talent_id 外键目标：{talent_fk_target}")
    indexes = {index["name"] for index in inspector.get_indexes("asm_result")}
    backup_meta = {
        "talent_fk_target": talent_fk_target,
        "user_fk_target": user_fk_target,
        "user_id_column_existed": original_user_id_existed,
        "user_id_nullable": result_columns.get("user_id", {}).get("nullable"),
        "user_id_index_existed": "ix_asm_result_user_id" in indexes,
        "talent_id_nullable": bool(result_columns["talent_id"]["nullable"]),
    }

    if not user_id_existed:
        op.add_column("asm_result", sa.Column("user_id", sa.Integer(), nullable=True))
    _create_backup_tables(bind, backup_meta)
    saved_meta = _load_backup_meta(bind)
    _create_missing_talent_mappings(bind, saved_meta["talent_fk_target"])
    mappings = _resolve_identity_rows(bind, saved_meta["talent_fk_target"])
    _remove_identity_foreign_keys(bind)
    if mappings:
        bind.execute(
            sa.text(
                "UPDATE asm_result SET user_id = :user_id, talent_id = :talent_id "
                "WHERE id = :result_id"
            ),
            mappings,
        )

    unresolved = int(bind.execute(sa.text(
        "SELECT COUNT(*) FROM asm_result r "
        "LEFT JOIN sys_user u ON u.id = r.user_id "
        "LEFT JOIN tal_talent t ON t.id = r.talent_id "
        "WHERE r.user_id IS NULL OR u.id IS NULL OR r.talent_id IS NULL OR t.id IS NULL "
        "OR u.talent_id <> r.talent_id OR u.talent_id IS NULL"
    )).scalar() or 0)
    if unresolved:
        raise RuntimeError(f"迁移校验失败：仍有 {unresolved} 条 asm_result 身份关系不一致")

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "asm_result", recreate="always", naming_convention=SQLITE_NAMING_CONVENTION
        ) as batch_op:
            batch_op.alter_column("talent_id", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(
                "fk_asm_result_talent_id_tal_talent",
                "tal_talent", ["talent_id"], ["id"], ondelete="RESTRICT",
            )
            batch_op.create_foreign_key(
                "fk_asm_result_user_id_sys_user",
                "sys_user", ["user_id"], ["id"], ondelete="RESTRICT",
            )
    else:
        op.alter_column("asm_result", "talent_id", existing_type=sa.Integer(), nullable=False)
        op.alter_column("asm_result", "user_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            "fk_asm_result_talent_id_tal_talent", "asm_result", "tal_talent",
            ["talent_id"], ["id"], ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_asm_result_user_id_sys_user", "asm_result", "sys_user",
            ["user_id"], ["id"], ondelete="RESTRICT",
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("asm_result")}
    if "ix_asm_result_user_id" not in indexes:
        op.create_index("ix_asm_result_user_id", "asm_result", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "asm_result"):
        return
    if not _table_exists(inspector, BACKUP_TABLE) or not _table_exists(inspector, BACKUP_META_TABLE):
        raise RuntimeError("缺少 asm_result 身份迁移备份表，拒绝执行不可恢复的回滚")
    if "user_id" not in _columns(inspector, "asm_result"):
        raise RuntimeError("asm_result.user_id 已缺失，数据库可能处于不完整回滚状态")

    meta = _load_backup_meta(bind)
    source_talent_fk = meta["talent_fk_target"]
    source_user_fk = meta["user_fk_target"]
    keep_user_column = bool(meta["user_id_column_existed"])

    # Restore rows that existed at upgrade time. Rows created after upgrade
    # are converted to the legacy account identity when necessary.
    _remove_identity_foreign_keys(bind)
    if keep_user_column:
        bind.execute(sa.text(
            f"UPDATE asm_result SET talent_id = (SELECT b.talent_id FROM {BACKUP_TABLE} b "
            "WHERE b.result_id = asm_result.id), "
            f"user_id = (SELECT b.user_id FROM {BACKUP_TABLE} b WHERE b.result_id = asm_result.id) "
            f"WHERE EXISTS (SELECT 1 FROM {BACKUP_TABLE} b WHERE b.result_id = asm_result.id)"
        ))
    else:
        bind.execute(sa.text(
            f"UPDATE asm_result SET talent_id = (SELECT b.talent_id FROM {BACKUP_TABLE} b "
            "WHERE b.result_id = asm_result.id) "
            f"WHERE EXISTS (SELECT 1 FROM {BACKUP_TABLE} b WHERE b.result_id = asm_result.id)"
        ))
    if source_talent_fk == "sys_user":
        bind.execute(sa.text(
            f"UPDATE asm_result SET talent_id = user_id WHERE NOT EXISTS "
            f"(SELECT 1 FROM {BACKUP_TABLE} b WHERE b.result_id = asm_result.id)"
        ))
        invalid = int(bind.execute(sa.text(
            "SELECT COUNT(*) FROM asm_result r LEFT JOIN sys_user u ON u.id = r.talent_id "
            "WHERE r.talent_id IS NULL OR u.id IS NULL"
        )).scalar() or 0)
        if invalid:
            raise RuntimeError(f"无法回滚：{invalid} 条 asm_result 没有可恢复的登录账号")
    elif source_talent_fk == "tal_talent":
        invalid = int(bind.execute(sa.text(
            "SELECT COUNT(*) FROM asm_result r LEFT JOIN tal_talent t ON t.id = r.talent_id "
            "WHERE r.talent_id IS NULL OR t.id IS NULL"
        )).scalar() or 0)
        if invalid:
            raise RuntimeError(f"无法回滚：{invalid} 条 asm_result 没有可恢复的人才档案")

    _remove_created_talent_mappings(bind)

    inspector = sa.inspect(bind)
    user_index_exists = "ix_asm_result_user_id" in {
        index["name"] for index in inspector.get_indexes("asm_result")
    }
    drop_user_index = user_index_exists and not bool(meta["user_id_index_existed"])

    def restore_batch_constraints(batch_op) -> None:
        if source_talent_fk:
            batch_op.create_foreign_key(
                f"fk_asm_result_talent_id_{source_talent_fk}",
                source_talent_fk, ["talent_id"], ["id"], ondelete="RESTRICT",
            )
        if keep_user_column and source_user_fk:
            batch_op.create_foreign_key(
                f"fk_asm_result_user_id_{source_user_fk}",
                source_user_fk, ["user_id"], ["id"], ondelete="RESTRICT",
            )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "asm_result", recreate="always", naming_convention=SQLITE_NAMING_CONVENTION
        ) as batch_op:
            if drop_user_index:
                batch_op.drop_index("ix_asm_result_user_id")
            batch_op.alter_column(
                "talent_id", existing_type=sa.Integer(),
                nullable=bool(meta["talent_id_nullable"]),
            )
            if keep_user_column:
                batch_op.alter_column(
                    "user_id", existing_type=sa.Integer(),
                    nullable=bool(meta["user_id_nullable"]),
                )
            else:
                batch_op.drop_column("user_id")
            restore_batch_constraints(batch_op)
    else:
        if drop_user_index:
            op.drop_index("ix_asm_result_user_id", table_name="asm_result")
        op.alter_column(
            "asm_result", "talent_id", existing_type=sa.Integer(),
            nullable=bool(meta["talent_id_nullable"]),
        )
        if keep_user_column:
            op.alter_column(
                "asm_result", "user_id", existing_type=sa.Integer(),
                nullable=bool(meta["user_id_nullable"]),
            )
        else:
            op.drop_column("asm_result", "user_id")
        if source_talent_fk:
            op.create_foreign_key(
                f"fk_asm_result_talent_id_{source_talent_fk}",
                "asm_result", source_talent_fk, ["talent_id"], ["id"],
                ondelete="RESTRICT",
            )
        if keep_user_column and source_user_fk:
            op.create_foreign_key(
                f"fk_asm_result_user_id_{source_user_fk}",
                "asm_result", source_user_fk, ["user_id"], ["id"],
                ondelete="RESTRICT",
            )

    if _table_exists(sa.inspect(bind), CREATED_TALENT_TABLE):
        op.drop_table(CREATED_TALENT_TABLE)
    op.drop_table(BACKUP_TABLE)
    op.drop_table(BACKUP_META_TABLE)
