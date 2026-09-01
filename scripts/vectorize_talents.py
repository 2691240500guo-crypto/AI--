"""人才/岗位向量化重建脚本（M 域匹配 Agent 数据准备）。

用途：
- 从云 MySQL tal_talent 读取人才档案，组装带结构化标记的画像文本，
  经硅基流动 bge-m3(1024维) 向量化后写入 Milvus talent_vec；
- 从 pos_position 读取岗位，向量化后写入 position_vec；
- 支持 --drop 先删旧集合再重建（修复 pymilvus 3.x 遗留的坏集合）。

画像文本格式（硬性条件过滤依赖结构化标记）：
    【人才id:12|学历:硕士|经验:5年|技能:python,mysql】
    姓名：张三；学历：硕士；专业：计算机科学；经验：5年；技能：...；经历：...

用法：
    D:\\Aconda\\envs\\ai-talent\\python.exe scripts\\vectorize_talents.py --drop
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 项目根目录

import sqlalchemy
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.utils.llm import get_llm
from app.utils.vector_store import get_vector_store

POSITION_VEC_COLLECTION = "position_vec"
TALENT_VEC_COLLECTION = "talent_vec"


def _norm(text) -> str:
    if text is None:
        return ""
    return str(text).strip()


def build_talent_profile(row) -> str:
    """组装人才画像文本，前置结构化标记供硬过滤解析。"""
    tid = row.id
    degree = _norm(row.highest_education) or "未知"
    years = _norm(row.years_experience) or "0"
    m = re.search(r"(\d+)", years)
    years_num = m.group(1) if m else "0"
    skills = _norm(row.skills).replace(";", ",").replace("；", ",")
    parts = [
        f"【人才id:{tid}|学历:{degree}|经验:{years_num}年|技能:{skills}】",
        f"姓名：{_norm(row.name)}",
    ]
    if _norm(row.major):
        parts.append(f"专业：{row.major}")
    if _norm(row.years_experience):
        parts.append(f"从业经验：{row.years_experience}")
    if _norm(row.current_title):
        parts.append(f"当前职称：{row.current_title}")
    if skills:
        parts.append(f"技能：{skills}")
    if _norm(row.work_experience):
        parts.append(f"工作经历：{row.work_experience}")
    if _norm(row.project_experience):
        parts.append(f"项目经历：{row.project_experience}")
    if _norm(row.honors):
        parts.append(f"荣誉：{row.honors}")
    if _norm(row.summary):
        parts.append(f"自我评价：{row.summary}")
    return "；".join(parts)


def build_position_profile(row) -> str:
    """组装岗位画像文本（与 MatchingService.build_profile_text 对齐）。"""
    parts = [
        f"【岗位id:{row.id}|{row.name}】",
        f"岗位：{row.name}",
        f"岗位编码：{row.code}",
    ]
    if _norm(row.description):
        parts.append(f"岗位说明书：{row.description}")
    return "；".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="删除旧集合后重建（修复坏集合）")
    ap.add_argument("--skip-talent", action="store_true", help="跳过人才向量化")
    ap.add_argument("--skip-position", action="store_true", help="跳过岗位向量化")
    args = ap.parse_args()

    settings = get_settings()
    engine = sqlalchemy.create_engine(settings.DATABASE_URL)
    db = Session(engine)
    llm = get_llm()
    vec = get_vector_store()

    try:
        dim = len(llm.embed("维度探测"))
        print(f"embedding 维度: {dim}")

        if not args.skip_talent:
            if args.drop:
                if vec.has_collection(TALENT_VEC_COLLECTION):
                    vec.delete_collection(TALENT_VEC_COLLECTION)
                    print("已删除旧 talent_vec")
                vec.create_collection(TALENT_VEC_COLLECTION, dim=dim)
                print("已重建 talent_vec")
            elif not vec.has_collection(TALENT_VEC_COLLECTION):
                vec.create_collection(TALENT_VEC_COLLECTION, dim=dim)
                print("已创建 talent_vec")

            talents = db.execute(
                sqlalchemy.text("SELECT * FROM tal_talent WHERE id IS NOT NULL ORDER BY id")
            ).mappings().all()
            print(f"人才总数: {len(talents)}")
            ok = fail = 0
            for row in talents:
                text = build_talent_profile(row)
                try:
                    vec.insert(TALENT_VEC_COLLECTION, [llm.embed(text)], [text])
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    print(f"  人才 #{row.id} 向量化失败: {str(e)[:120]}")
            print(f"人才向量化完成: 成功 {ok}, 失败 {fail}")

        if not args.skip_position:
            if args.drop:
                if vec.has_collection(POSITION_VEC_COLLECTION):
                    vec.delete_collection(POSITION_VEC_COLLECTION)
                    print("已删除旧 position_vec")
                vec.create_collection(POSITION_VEC_COLLECTION, dim=dim)
                print("已重建 position_vec")
            elif not vec.has_collection(POSITION_VEC_COLLECTION):
                vec.create_collection(POSITION_VEC_COLLECTION, dim=dim)
                print("已创建 position_vec")

            positions = db.execute(
                sqlalchemy.text("SELECT * FROM pos_position WHERE id IS NOT NULL ORDER BY id")
            ).mappings().all()
            print(f"岗位总数: {len(positions)}")
            ok = fail = 0
            for row in positions:
                text = build_position_profile(row)
                try:
                    vec.insert(POSITION_VEC_COLLECTION, [llm.embed(text)], [text])
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    print(f"  岗位 #{row.id} 向量化失败: {str(e)[:120]}")
            print(f"岗位向量化完成: 成功 {ok}, 失败 {fail}")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
