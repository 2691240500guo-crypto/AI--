"""删除旧的 C 智能测评演示业务数据，并按当前模型重新生成。"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.seed_assessment import reset_assessment_demo_data
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="确认删除并重新生成固定名称的 C 测评演示业务数据",
    )
    args = parser.parse_args()
    if not args.yes:
        parser.error("这是删除并重建操作；确认目标 DATABASE_URL 后请传入 --yes")

    db = SessionLocal()
    try:
        deleted = reset_assessment_demo_data(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("C 智能测评演示数据已按当前 schema 重新生成。")
    print("已删除：" + json.dumps(deleted, ensure_ascii=False, sort_keys=True))
    print("演示账号保持不变，默认密码：assessment123")


if __name__ == "__main__":
    main()
