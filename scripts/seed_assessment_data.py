"""初始化可重复执行的 C 智能测评演示数据。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.init_db import init_db


if __name__ == "__main__":
    init_db()
    print("C 智能测评演示数据已幂等初始化。账号：admin / admin123")
