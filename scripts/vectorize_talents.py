"""人才/岗位向量化重建脚本（M 域匹配 Agent 数据准备）。

用途：
- 从云 MySQL tal_talent 读取人才档案，组装带结构化标记的画像文本，
经硅基流动 bge-m3(1024维) 向量化后由 upsert_talent_vectors 实时写入四维集合(skill/exp/quality/resume)；
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


def _norm(text) -> str:
    if text is None:
        return ""
    return str(text).strip()


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
            # 2026-09-03：人才向量统一走实时四维集合（upsert_talent_vectors，skill/exp/quality/resume），
            # 档案增改即实时 upsert，本脚本仅用于存量数据一次性回灌；批处理 talent_vec 集合已退役。
            if args.drop:
                print("提示：--drop 对人才四维不生效（幂等 upsert 维护）；如需清空请删除 Milvus 集合 talent_skill/talent_exp/talent_quality/talent_resume")
            from app.services.talent_vector_service import upsert_talent_vectors
            talents = db.execute(
                # 过滤：停用(status!=1)不处理；无简历文本的空档案不参与匹配召回（合并两边口径）
                sqlalchemy.text("SELECT * FROM tal_talent WHERE status=1 "
                                "AND TRIM(COALESCE(resume_text, '')) <> '' ORDER BY id")
            ).mappings().all()
            print(f"人才总数(在档): {len(talents)}")
            ok = fail = 0
            for i, row in enumerate(talents, 1):
                try:
                    dims = upsert_talent_vectors(row)
                    if dims:
                        ok += 1
                    else:
                        fail += 1
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    print(f"  人才 #{row.id} 向量化失败: {str(e)[:120]}")
                if i % 10 == 0:
                    print(f"  进度 {i}/{len(talents)}（成功 {ok} 失败 {fail}）")
            print(f"人才四维向量回灌完成: 成功 {ok}, 失败 {fail}")

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
