"""幂等补齐 C 智能测评演示数据（不会删除已有演示结果）。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import create_tables, seed
from app.db.seed_assessment import seed_assessment
from app.db.session import SessionLocal


if __name__ == "__main__":
    create_tables()
    db = SessionLocal()
    try:
        seed(db)
        seed_assessment(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print("C 智能测评演示数据已幂等初始化。演示账号默认密码：assessment123")
