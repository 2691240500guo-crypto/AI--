"""幂等新增 HR 岗位到岗位管理(pos_position)。

- 已存在同名/同编码岗位则跳过（不重复插入）。
- 只新增 1 条，不改动其它岗位数据。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.matching import PosPosition

CODE = "HR-ADMIN-01"
NAME = "HR 专员"


def _exists(db, field) -> bool:
    stmt = select(PosPosition.id).where(field).limit(1)
    return db.scalar(stmt) is not None


def main() -> None:
    db = SessionLocal()
    try:
        if _exists(db, PosPosition.code == CODE):
            print(f"已存在岗位编码 {CODE}，跳过新增（幂等）。")
            return
        if _exists(db, PosPosition.name == NAME):
            print(f"已存在岗位名称 {NAME!r}，跳过新增（幂等）。")
            return

        p = PosPosition(
            code=CODE,
            name=NAME,
            dept_id=None,
            headcount=2,
            filled=0,
            status=1,
            description=(
                "负责招聘、人才发展与员工关系管理，保障组织人力配置与人才梯队建设。"
                "要求熟悉人力资源六大模块、招聘流程与员工关系处理，具备 3 年以上 HR 相关经验，"
                "熟练使用 HR 信息系统（E-HR）与 Office 办公软件，具备良好的沟通协调与人际理解能力。"
            ),
        )
        db.add(p)
        db.commit()
        print(f"已新增 HR 岗位：id={p.id} code={p.code} name={p.name} 编制={p.headcount}")
    finally:
        db.close()


if __name__ == "__main__":
    main()