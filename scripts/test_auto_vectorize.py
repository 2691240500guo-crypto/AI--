# -*- coding: utf-8 -*-
"""验证「新增岗位 → 自动解析 + 自动向量化入库」全链路。只创建并清理一个测试岗位。
用法：D:\\Aconda\\envs\\ai-talent\\python.exe scripts\\test_auto_vectorize.py [--base http://127.0.0.1:8000/api/v1]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 项目根目录，让 app/ 可导入

import requests
from pymilvus import MilvusClient

_ap = argparse.ArgumentParser()
_ap.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
_args = _ap.parse_args()
BASE = _args.base
CODE = "TEST-AUTO-VEC-01"
NAME = "测试自动向量化岗"
DESC = ("岗位职责：负责数据平台建设与后端服务开发，掌握 Python、SQL、Docker，"
        "统招本科及以上学历，3 年以上大数据开发经验，熟悉 Flink、Kafka、ClickHouse，"
        "具备数据治理与数仓建模能力，能够跨团队协调，责任心强。")

s = requests.Session()
r = s.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=15)
at = r.json()["data"]["access_token"]
s.headers["Authorization"] = f"Bearer {at}"
print("[1] 登录 OK")

mc = MilvusClient(uri="http://120.77.177.232:19530", db_name="default")


def vec_count():
    mc.load_collection("talent_position_vec")
    return int(mc.query("talent_position_vec", filter="", output_fields=["count(*)"], limit=1)[0].get("count(*)", 0))


def vec_count_fallback():
    # MilvusClient 统计口径不稳时用默认行数
    try:
        return int(mc.get_collection_stats("talent_position_vec")["row_count"])
    except Exception:
        return -1


before = vec_count_fallback()
print(f"[2] 向量化前 talent_position_vec 行数 = {before}")

# 3. 新增岗位（自动解析 + 自动向量化，预计 5~15 秒）
t0 = time.time()
r = s.post(f"{BASE}/matching/positions", json={
    "name": NAME, "code": CODE, "status": 1,
    "headcount": 2, "filled": 0, "description": DESC,
}, timeout=90)
print(f"[3] POST /positions → {r.status_code}  ({time.time() - t0:.1f}s)")
if r.status_code != 200:
    print("   ", r.text[:400]); raise SystemExit(1)
pid = r.json()["data"]["id"]
print(f"    新岗位 id = {pid}")

# 4. 校验 DB：description 在 & parsed_json 是否自动生成
import sqlalchemy
from sqlalchemy.orm import Session
from app.core.config import get_settings

settings = get_settings()
engine = sqlalchemy.create_engine(settings.DATABASE_URL)
db = Session(engine)
row = db.execute(
    sqlalchemy.text("SELECT id, name, status, parsed_json FROM pos_position WHERE id = :pid"),
    {"pid": pid},
).mappings().first()
parsed = (row or {}).get("parsed_json")
print("[4] DB parsed_json 自动生成:", "YES" if parsed else "NO/空",
      "" if parsed else f"(description={bool((row or {}).get('status'))})")
if parsed:
    print("    parsed_json 片段:", parsed[:150], "...")

# 5. 校验向量真实写入：按 text 含 【岗位id:{pid}】 判定（stats 有滞后，不采用）
def vec_has_position(pid, wait_s=12):
    import time as _t
    deadline = _t.time() + wait_s
    while _t.time() < deadline:
        try:
            mc.load_collection("talent_position_vec")
            rows = mc.query("talent_position_vec", filter="", output_fields=["text"], limit=200)
            if any(f"岗位id:{pid}" in (r.get("text") or "") for r in rows):
                return True
        except Exception:
            pass
        _t.sleep(2)
    return False

ok_vec = vec_has_position(pid)
print(f"[5] 向量库出现 岗位id:{pid} →", "PASS" if ok_vec else "FAIL")

# 6. 清理测试岗位（DB 删除 + 尽力清向量）
r = s.delete(f"{BASE}/matching/positions/{pid}", timeout=15)
print(f"[6] 清理测试岗位 DB: {r.status_code}")
try:
    expr = f"text like '%岗位id:{pid}%'"
    mc.delete("talent_position_vec", filter=expr)
    print("    清理 Milvus 测试向量 done")
except Exception as e:
    print(f"    Milvus 清理跳过（不阻塞）: {str(e)[:80]}")
db.close()
engine.dispose()
print("DONE")
