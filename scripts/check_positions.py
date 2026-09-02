"""只读检查当前岗位管理(pos_position)现状，不下发任何写入。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.matching import PosPosition


def main() -> None:
    settings = get_settings()
    print("DATABASE_URL:", settings.DATABASE_URL.split("@")[-1])
    db = SessionLocal()
    try:
        rows = db.execute(select(PosPosition).order_by(PosPosition.id)).scalars().all()
        print(f"当前岗位总数: {len(rows)}")
        for p in rows:
            desc = (p.description or "").replace("\n", " ")[:60]
            print(f"  id={p.id} code={p.code!r} name={p.name!r} dept_id={p.dept_id} "
                  f"编制={p.headcount} 到岗={p.filled} status={p.status} 说明书={desc!r}")
        hr = db.execute(select(PosPosition).where(
            PosPosition.name.contains("HR") | PosPosition.name.contains("hr") |
            PosPosition.code.contains("HR") | PosPosition.code.contains("hr") |
            PosPosition.name.contains("人力") | PosPosition.name.contains("招聘")
        )).scalars().all()
        print(f"疑似 HR/人力/招聘 岗位: {len(hr)} 条")
        for p in hr:
            print(f"  id={p.id} code={p.code!r} name={p.name!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()