"""Regression tests for the asm_result user/talent identity migration."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "c9d4e7f1a203_fix_assessment_talent_identity.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("assessment_identity_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_connection(tmp_path: Path, *, ambiguous: bool = False):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    connection = engine.connect()
    connection.execute(sa.text("PRAGMA foreign_keys=ON"))
    connection.execute(sa.text("CREATE TABLE tal_talent (id INTEGER PRIMARY KEY)"))
    connection.execute(sa.text(
        "CREATE TABLE sys_user (id INTEGER PRIMARY KEY, talent_id INTEGER NULL, "
        "FOREIGN KEY(talent_id) REFERENCES tal_talent(id))"
    ))
    connection.execute(sa.text(
        "CREATE TABLE asm_result (id INTEGER PRIMARY KEY, talent_id INTEGER NOT NULL, "
        "FOREIGN KEY(talent_id) REFERENCES sys_user(id) ON DELETE RESTRICT)"
    ))
    connection.execute(sa.text("INSERT INTO tal_talent(id) VALUES (5), (6)"))
    connection.execute(sa.text("INSERT INTO sys_user(id, talent_id) VALUES (40, 5), (41, 6)"))
    if ambiguous:
        connection.execute(sa.text("INSERT INTO sys_user(id, talent_id) VALUES (5, 6)"))
    connection.execute(sa.text("INSERT INTO asm_result(id, talent_id) VALUES (1, 40), (2, 41)"))
    connection.commit()
    return engine, connection


def _operations(connection):
    return Operations(MigrationContext.configure(connection))


def test_upgrade_maps_ids_keeps_backup_and_downgrade_restores_legacy_schema(tmp_path):
    migration = _load_migration()
    engine, connection = _legacy_connection(tmp_path)
    migration.op = _operations(connection)

    migration.upgrade()
    connection.commit()

    rows = connection.execute(sa.text(
        "SELECT id, talent_id, user_id FROM asm_result ORDER BY id"
    )).all()
    assert rows == [(1, 5, 40), (2, 6, 41)]
    inspector = sa.inspect(connection)
    assert migration.BACKUP_TABLE in inspector.get_table_names()
    assert migration.BACKUP_META_TABLE in inspector.get_table_names()
    assert {fk["referred_table"] for fk in inspector.get_foreign_keys("asm_result")} == {
        "sys_user", "tal_talent"
    }
    assert "ix_asm_result_user_id" in {
        index["name"] for index in inspector.get_indexes("asm_result")
    }
    assert connection.execute(sa.text(
        f"SELECT result_id, talent_id, user_id FROM {migration.BACKUP_TABLE} ORDER BY result_id"
    )).all() == [(1, 40, None), (2, 41, None)]

    migration.op = _operations(connection)
    migration.downgrade()
    connection.commit()

    inspector = sa.inspect(connection)
    assert "user_id" not in {column["name"] for column in inspector.get_columns("asm_result")}
    assert [fk["referred_table"] for fk in inspector.get_foreign_keys("asm_result")] == ["sys_user"]
    assert connection.execute(sa.text(
        "SELECT id, talent_id FROM asm_result ORDER BY id"
    )).all() == [(1, 40), (2, 41)]
    assert migration.BACKUP_TABLE not in inspector.get_table_names()
    assert migration.BACKUP_META_TABLE not in inspector.get_table_names()
    connection.close()
    engine.dispose()


def test_upgrade_creates_tracked_compatibility_profile_and_downgrade_removes_it(tmp_path):
    migration = _load_migration()
    engine, connection = _legacy_connection(tmp_path)
    connection.execute(sa.text("UPDATE sys_user SET talent_id = NULL WHERE id = 41"))
    connection.commit()
    migration.op = _operations(connection)

    migration.upgrade()
    connection.commit()

    row = connection.execute(sa.text(
        "SELECT talent_id, user_id FROM asm_result WHERE id = 2"
    )).one()
    compatibility_talent_id = row.talent_id
    assert row.user_id == 41
    assert compatibility_talent_id not in {5, 6, 41}
    assert connection.execute(sa.text(
        "SELECT talent_id FROM sys_user WHERE id = 41"
    )).scalar_one() == compatibility_talent_id
    assert connection.execute(sa.text(
        f"SELECT user_id, talent_id, original_talent_id "
        f"FROM {migration.CREATED_TALENT_TABLE}"
    )).one() == (41, compatibility_talent_id, None)

    migration.op = _operations(connection)
    migration.downgrade()
    connection.commit()

    assert connection.execute(sa.text(
        "SELECT id, talent_id FROM asm_result ORDER BY id"
    )).all() == [(1, 40), (2, 41)]
    assert connection.execute(sa.text(
        "SELECT talent_id FROM sys_user WHERE id = 41"
    )).scalar_one() is None
    assert connection.execute(sa.text(
        "SELECT COUNT(*) FROM tal_talent WHERE id = :talent_id"
    ), {"talent_id": compatibility_talent_id}).scalar_one() == 0
    inspector = sa.inspect(connection)
    assert "user_id" not in {column["name"] for column in inspector.get_columns("asm_result")}
    assert migration.CREATED_TALENT_TABLE not in inspector.get_table_names()
    connection.close()
    engine.dispose()


def test_upgrade_backfills_user_for_database_already_using_talent_fk(tmp_path):
    migration = _load_migration()
    engine, connection = _legacy_connection(tmp_path)
    connection.execute(sa.text("PRAGMA foreign_keys=OFF"))
    connection.execute(sa.text("ALTER TABLE asm_result RENAME TO asm_result_old"))
    connection.execute(sa.text(
        "CREATE TABLE asm_result (id INTEGER PRIMARY KEY, talent_id INTEGER NOT NULL, "
        "FOREIGN KEY(talent_id) REFERENCES tal_talent(id) ON DELETE RESTRICT)"
    ))
    connection.execute(sa.text(
        "INSERT INTO asm_result(id, talent_id) VALUES (1, 5), (2, 6)"
    ))
    connection.execute(sa.text("DROP TABLE asm_result_old"))
    connection.commit()
    migration.op = _operations(connection)

    migration.upgrade()
    connection.commit()

    assert connection.execute(sa.text(
        "SELECT id, talent_id, user_id FROM asm_result ORDER BY id"
    )).all() == [(1, 5, 40), (2, 6, 41)]

    migration.op = _operations(connection)
    migration.downgrade()
    connection.commit()
    inspector = sa.inspect(connection)
    assert "user_id" not in {column["name"] for column in inspector.get_columns("asm_result")}
    assert [fk["referred_table"] for fk in inspector.get_foreign_keys("asm_result")] == [
        "tal_talent"
    ]
    assert connection.execute(sa.text(
        "SELECT id, talent_id FROM asm_result ORDER BY id"
    )).all() == [(1, 5), (2, 6)]
    connection.close()
    engine.dispose()


def test_fk_less_database_rejects_ambiguous_identity_mapping(tmp_path):
    migration = _load_migration()
    engine, connection = _legacy_connection(tmp_path, ambiguous=True)
    connection.execute(sa.text("PRAGMA foreign_keys=OFF"))
    connection.execute(sa.text("ALTER TABLE asm_result RENAME TO asm_result_old"))
    connection.execute(sa.text(
        "CREATE TABLE asm_result (id INTEGER PRIMARY KEY, talent_id INTEGER NOT NULL)"
    ))
    connection.execute(sa.text(
        "INSERT INTO asm_result(id, talent_id) SELECT id, talent_id FROM asm_result_old"
    ))
    connection.execute(sa.text("UPDATE asm_result SET talent_id = 5 WHERE id = 1"))
    connection.execute(sa.text("DROP TABLE asm_result_old"))
    connection.commit()
    migration.op = _operations(connection)

    # Value 5 can mean legacy user 5 -> talent 6 or already-new talent 5 -> user 40.
    with pytest.raises(RuntimeError, match="存在多条候选映射"):
        migration.upgrade()
    connection.close()
    engine.dispose()
