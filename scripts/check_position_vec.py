"""只读对比 MySQL pos_position 与 Milvus position_vec 的岗位覆盖情况，不下发任何写入。"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.matching import PosPosition
from app.utils.vector_store import get_vector_store

POSITION_VEC_COLLECTION = "position_vec"


def _parse_pid(text: str) -> int | None:
    m = re.search(r"【岗位id[:：](\d+)", text or "")
    return int(m.group(1)) if m else None


def main() -> None:
    settings = get_settings()
    print("数据库:", settings.DATABASE_URL.split("@")[-1])
    print("Milvus:", f"{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
          "前缀:", settings.MILVUS_COLLECTION_PREFIX)

    db = SessionLocal()
    try:
        positions = db.execute(
            select(PosPosition.id, PosPosition.code, PosPosition.name, PosPosition.status)
            .order_by(PosPosition.id)
        ).all()
        db_ids = {p.id for p in positions}
        print(f"\nMySQL pos_position 岗位数: {len(positions)}")

        vec = get_vector_store()
        name = f"{vec.prefix}{POSITION_VEC_COLLECTION}"
        if not vec.has_collection(POSITION_VEC_COLLECTION):
            print(f"Milvus 集合 {name} 不存在！尚未向量化。")
            return

        client = vec._client
        # 1) row_count
        try:
            num = client.get_collection_stats(name).get("row_count")
            print(f"Milvus {name} 向量数(row_count): {num}")
        except Exception as e:  # noqa: BLE001
            print(f"读取 row_count 失败: {str(e)[:120]}")

        # 2) 抓取全部 text，解析其中的岗位id
        try:
            client.load_collection(name)
            vec_ids: set[int] = set()
            offset, batch, total = 0, 500, 0
            while True:
                page = client.query(collection_name=name, filter="id >= 0",
                                    output_fields=["id", "text"], limit=batch, offset=offset)
                if not page:
                    break
                for row in page:
                    total += 1
                    pid = _parse_pid(row.get("text", ""))
                    if pid is not None:
                        vec_ids.add(pid)
                if len(page) < batch:
                    break
                offset += batch
            print(f"抓取实体: {total} 条，能解析出岗位id的去重数: {len(vec_ids)}")
        except Exception as e:  # noqa: BLE001
            print(f"抓取实体失败: {str(e)[:150]}")
            return

        print("\n=== 覆盖对照 ===")
        missing = sorted(db_ids - vec_ids)
        stale = sorted(vec_ids - db_ids)
        print(f"MySQL 有但向量库缺失的岗位(目标：空): {missing}")
        print(f"向量库存在但 MySQL 已无对应岗位(陈旧，可接受): {stale}")
        hr = {p.id: p for p in positions if "HR" in (p.code or "").upper() or "HR" in (p.name or "").upper()}
        for pid in hr:
            p = hr[pid]
            print(f"  HR岗位 id={p.id} code={p.code!r} 是否已向量化: {pid in vec_ids}")
    finally:
        db.close()


if __name__ == "__main__":
    main()