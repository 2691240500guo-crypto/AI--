"""Regression tests for retiring legacy talent tag tables."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e2f6a9c3d701_retire_legacy_talent_tag_tables.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("legacy_talent_cleanup_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _operations(connection):
    return Operations(MigrationContext.configure(connection))


def _connection(tmp_path: Path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy-cleanup.db'}")
    connection = engine.connect()
    connection.execute(sa.text("PRAGMA foreign_keys=ON"))
    connection.execute(sa.text("CREATE TABLE tal_talent (id INTEGER PRIMARY KEY)"))
    connection.execute(sa.text(
        "CREATE TABLE tal_tag ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(64) NOT NULL UNIQUE, "
        "category VARCHAR(32) NOT NULL, description VARCHAR(255), "
        "is_builtin INTEGER NOT NULL, created_at DATETIME NOT NULL)"
    ))
    connection.execute(sa.text(
        "CREATE TABLE tal_talent_tag ("
        "talent_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, source VARCHAR(16), score FLOAT, "
        "PRIMARY KEY(talent_id, tag_id), FOREIGN KEY(talent_id) REFERENCES tal_talent(id), "
        "FOREIGN KEY(tag_id) REFERENCES tal_tag(id))"
    ))
    connection.execute(sa.text(
        "CREATE TABLE tal_talent_dict ("
        "id INTEGER PRIMARY KEY, code VARCHAR(64) NOT NULL UNIQUE, name VARCHAR(64) NOT NULL, "
        "type VARCHAR(32) NOT NULL, sort INTEGER NOT NULL, enabled INTEGER NOT NULL, "
        "created_at DATETIME NOT NULL)"
    ))
    connection.execute(sa.text(
        "CREATE TABLE tal_talent_tag_rel ("
        "id INTEGER PRIMARY KEY, talent_id INTEGER NOT NULL, dict_id INTEGER NOT NULL, "
        "source VARCHAR(16) NOT NULL, weight NUMERIC(3,2) NOT NULL, created_at DATETIME NOT NULL, "
        "FOREIGN KEY(talent_id) REFERENCES tal_talent(id), "
        "FOREIGN KEY(dict_id) REFERENCES tal_talent_dict(id))"
    ))
    connection.execute(sa.text("INSERT INTO tal_talent(id) VALUES (1)"))
    connection.execute(sa.text(
        "INSERT INTO tal_tag(id,name,category,is_builtin,created_at) "
        "VALUES (2,'Python','skill',1,CURRENT_TIMESTAMP)"
    ))
    connection.execute(sa.text(
        "INSERT INTO tal_talent_tag(talent_id,tag_id,source,score) VALUES (1,2,'ai',NULL)"
    ))
    connection.execute(sa.text(
        "INSERT INTO tal_talent_dict(id,code,name,type,sort,enabled,created_at) VALUES "
        "(10,'python','Python','skill',1,1,CURRENT_TIMESTAMP),"
        "(11,'communication','沟通能力','quality',2,1,CURRENT_TIMESTAMP)"
    ))
    connection.execute(sa.text(
        "INSERT INTO tal_talent_tag_rel(id,talent_id,dict_id,source,weight,created_at) VALUES "
        "(100,1,10,'manual',0.80,CURRENT_TIMESTAMP),"
        "(101,1,11,'auto',0.60,CURRENT_TIMESTAMP)"
    ))
    connection.commit()
    return engine, connection


def test_upgrade_merges_data_retires_old_names_and_downgrade_restores_tables(tmp_path):
    migration = _load_migration()
    engine, connection = _connection(tmp_path)
    migration.op = _operations(connection)

    migration.upgrade()
    connection.commit()

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    assert migration.LEGACY_DICT not in tables
    assert migration.LEGACY_REL not in tables
    assert migration.BACKUP_DICT in tables
    assert migration.BACKUP_REL in tables
    tags = connection.execute(sa.text(
        "SELECT name,category FROM tal_tag ORDER BY name"
    )).all()
    assert tags == [("Python", "skill"), ("沟通能力", "quality")]
    relations = connection.execute(sa.text(
        "SELECT t.name,r.source,r.score FROM tal_talent_tag r "
        "JOIN tal_tag t ON t.id=r.tag_id ORDER BY t.name"
    )).all()
    assert relations == [("Python", "manual", 0.8), ("沟通能力", "auto", 0.6)]

    migration.op = _operations(connection)
    migration.downgrade()
    connection.commit()

    tables = set(sa.inspect(connection).get_table_names())
    assert migration.LEGACY_DICT in tables
    assert migration.LEGACY_REL in tables
    assert migration.BACKUP_DICT not in tables
    assert migration.BACKUP_REL not in tables
    assert connection.execute(sa.text(
        "SELECT id,code,name,type FROM tal_talent_dict ORDER BY id"
    )).all() == [
        (10, "python", "Python", "skill"),
        (11, "communication", "沟通能力", "quality"),
    ]
    assert connection.execute(sa.text(
        "SELECT id,talent_id,dict_id FROM tal_talent_tag_rel ORDER BY id"
    )).all() == [(100, 1, 10), (101, 1, 11)]
    connection.close()
    engine.dispose()
