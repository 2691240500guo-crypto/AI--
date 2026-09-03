"""Generate a complete database table/column audit without modifying data."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401,E402 - register all ORM tables
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "数据库表字段审计清单.md"


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _actual_column_notes(inspector: sa.Inspector, table_name: str) -> dict[str, list[str]]:
    notes: dict[str, list[str]] = {}
    primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
    for column in primary_key:
        notes.setdefault(column, []).append("PK")
    for foreign_key in inspector.get_foreign_keys(table_name):
        target_table = foreign_key.get("referred_table")
        target_columns = foreign_key.get("referred_columns") or []
        for index, column in enumerate(foreign_key.get("constrained_columns") or []):
            target_column = target_columns[index] if index < len(target_columns) else "?"
            notes.setdefault(column, []).append(f"FK→{target_table}.{target_column}")
    for index in inspector.get_indexes(table_name):
        label = "UNIQUE INDEX" if index.get("unique") else "INDEX"
        if index.get("name"):
            label += f" {index['name']}"
        for column in index.get("column_names") or []:
            if column:
                notes.setdefault(column, []).append(label)
    for constraint in inspector.get_unique_constraints(table_name):
        label = "UNIQUE"
        if constraint.get("name"):
            label += f" {constraint['name']}"
        for column in constraint.get("column_names") or []:
            notes.setdefault(column, []).append(label)
    return notes


def _row_count(connection: sa.Connection, table_name: str) -> int | str:
    quoted = connection.dialect.identifier_preparer.quote(table_name)
    try:
        return int(connection.execute(sa.text(f"SELECT COUNT(*) FROM {quoted}")).scalar() or 0)
    except Exception as exc:  # audit must continue when one table lacks SELECT permission
        return f"不可读取：{type(exc).__name__}"


def generate_audit(output: Path, *, include_row_counts: bool = True) -> None:
    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        actual_tables = set(inspector.get_table_names())
        model_tables = set(Base.metadata.tables)
        all_tables = sorted(actual_tables | model_tables)
        only_actual = sorted(actual_tables - model_tables)
        only_model = sorted(model_tables - actual_tables)
        shared = sorted(actual_tables & model_tables)

        revisions: list[str] = []
        if "alembic_version" in actual_tables:
            revisions = [str(row[0]) for row in connection.execute(
                sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).all()]

        lines = [
            "# 数据库表/字段审计清单",
            "",
            f"> 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"> 数据库类型：`{connection.dialect.name}`（连接地址和凭据已隐藏）",
            f"> Alembic revision：{', '.join(f'`{item}`' for item in revisions) if revisions else '未记录'}",
            "",
            "## 总览",
            "",
            "| 项目 | 数量 |",
            "|---|---:|",
            f"| 数据库实际表 | {len(actual_tables)} |",
            f"| ORM metadata 表 | {len(model_tables)} |",
            f"| 数据库与 ORM 共有 | {len(shared)} |",
            f"| 仅数据库存在 | {len(only_actual)} |",
            f"| 仅 ORM 存在（数据库缺表） | {len(only_model)} |",
            "",
            "### 漂移摘要",
            "",
            f"- 仅数据库：{', '.join(f'`{name}`' for name in only_actual) if only_actual else '无'}",
            f"- 仅 ORM：{', '.join(f'`{name}`' for name in only_model) if only_model else '无'}",
            f"- 冗余旧表 `tal_talent_dict`：{'存在' if 'tal_talent_dict' in actual_tables else '不存在'}",
            f"- 冗余旧表 `tal_talent_tag_rel`：{'存在' if 'tal_talent_tag_rel' in actual_tables else '不存在'}",
            "",
            "## 表级清单",
            "",
            "| 表名 | 状态 | 行数 | 数据库字段数 | ORM 字段数 |",
            "|---|---|---:|---:|---:|",
        ]

        table_row_counts: dict[str, int | str] = {}
        for table_name in all_tables:
            in_actual = table_name in actual_tables
            in_model = table_name in model_tables
            status = "一致存在" if in_actual and in_model else "仅数据库" if in_actual else "仅 ORM"
            row_count: int | str = _row_count(connection, table_name) if in_actual and include_row_counts else "—"
            table_row_counts[table_name] = row_count
            actual_count = len(inspector.get_columns(table_name)) if in_actual else 0
            model_count = len(Base.metadata.tables[table_name].columns) if in_model else 0
            lines.append(
                f"| `{table_name}` | {status} | {_cell(row_count)} | {actual_count} | {model_count} |"
            )

        lines.extend(["", "## 逐表字段审计", ""])
        for table_name in all_tables:
            in_actual = table_name in actual_tables
            in_model = table_name in model_tables
            lines.extend([
                f"### `{table_name}`",
                "",
                f"- 状态：{'数据库 + ORM' if in_actual and in_model else '仅数据库' if in_actual else '仅 ORM'}",
                f"- 行数：{_cell(table_row_counts[table_name])}",
            ])

            if in_actual:
                actual_columns = inspector.get_columns(table_name)
                notes = _actual_column_notes(inspector, table_name)
                model_column_names = set(Base.metadata.tables[table_name].columns.keys()) if in_model else set()
                actual_column_names = {column["name"] for column in actual_columns}
                missing_in_db = sorted(model_column_names - actual_column_names)
                extra_in_db = sorted(actual_column_names - model_column_names)
                lines.extend([
                    f"- ORM 缺失字段：{', '.join(f'`{name}`' for name in missing_in_db) if missing_in_db else '无'}",
                    f"- 数据库额外字段：{', '.join(f'`{name}`' for name in extra_in_db) if extra_in_db else '无'}",
                    "",
                    "| 字段 | 数据库类型 | 可空 | 默认值 | 约束/索引 | ORM |",
                    "|---|---|---|---|---|---|",
                ])
                for column in actual_columns:
                    name = column["name"]
                    lines.append(
                        f"| `{name}` | `{_cell(column['type'])}` | "
                        f"{'是' if column.get('nullable') else '否'} | {_cell(column.get('default'))} | "
                        f"{_cell('; '.join(notes.get(name, [])))} | "
                        f"{'有' if name in model_column_names else '无'} |"
                    )
            else:
                model_table = Base.metadata.tables[table_name]
                lines.extend([
                    "- ORM 缺失字段：该表整体尚未创建",
                    "- 数据库额外字段：无",
                    "",
                    "| 字段 | ORM 类型 | 可空 | 主键 | 外键 |",
                    "|---|---|---|---|---|",
                ])
                for column in model_table.columns:
                    foreign_keys = ", ".join(str(fk.target_fullname) for fk in column.foreign_keys)
                    lines.append(
                        f"| `{column.name}` | `{_cell(column.type)}` | "
                        f"{'是' if column.nullable else '否'} | {'是' if column.primary_key else '否'} | "
                        f"{_cell(foreign_keys)} |"
                    )
            lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-row-count", action="store_true", help="不执行逐表 COUNT(*)")
    args = parser.parse_args()
    generate_audit(args.output.resolve(), include_row_counts=not args.no_row_count)
    print(f"数据库审计清单已生成：{args.output.resolve()}")


if __name__ == "__main__":
    main()
