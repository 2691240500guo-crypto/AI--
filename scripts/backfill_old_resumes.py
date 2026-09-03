"""老档案（169-192，19人）简历回填脚本：基于档案已有字段生成简历文本 →
写入 resume_text + 上传 MinIO(object_key) → ResumeLLMService.apply 生成研判报告。
不新建档案（避免去重重复人），仅补全原档案。幂等：resume_text 已非空则跳过。

用法: python scripts/backfill_old_resumes.py [--ids 169,170]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OLD_IDS = [169, 170, 171, 172, 173, 174, 179, 180, 181, 182,
           183, 184, 185, 186, 188, 189, 190, 191, 192]


def build_resume(r) -> str:
    """基于档案字段如实生成简历文本（不凭空捏造经历）。"""
    L = ["个人简历"]
    for k, label in [("name", "姓名"), ("gender", "性别"), ("phone", "手机"),
                     ("email", "邮箱"), ("current_title", "求职意向")]:
        if r.get(k):
            L.append(f"{label}：{r[k]}")
    L += ["", "教育背景"]
    edu = r.get("degree") or r.get("highest_education") or "未知"
    if r.get("school") or r.get("major"):
        L.append(f"院校：{r.get('school') or '未知'}　专业：{r.get('major') or '未知'}　学历：{edu}")
    else:
        L.append(f"学历：{edu}")
    if r.get("skills"):
        L += ["", "专业技能"]
        L.append(str(r["skills"]))
    if r.get("work_experience"):
        L += ["", "工作经历"]
        L.append(str(r["work_experience"]))
    if r.get("project_experience"):
        L += ["", "项目经历"]
        L.append(str(r["project_experience"]))
    if r.get("honors"):
        L += ["", "荣誉奖项"]
        L.append(str(r["honors"]))
    if r.get("summary"):
        L += ["", "自我评价"]
        L.append(str(r["summary"]))
    return "\n".join(L)


def main() -> None:
    ids = OLD_IDS
    if "--ids" in sys.argv:
        ids = [int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(",")]

    from app.db.session import SessionLocal
    from app.models.talent import Talent
    from app.services.resume_llm_service import ResumeLLMService
    from app.utils.object_storage import ObjectStorage
    from sqlalchemy import text

    storage = None
    try:
        storage = ObjectStorage()
        storage.ensure_bucket()
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ MinIO 初始化失败，将跳过附件上传: {type(e).__name__}: {e}")

    with SessionLocal() as db:
        for tid in ids:
            r = db.execute(text("SELECT * FROM tal_talent WHERE id=:id"), {"id": tid}).mappings().first()
            if not r:
                print(f"#{tid} 不存在，跳过")
                continue
            if (r["resume_text"] or "").strip():
                print(f"#{tid} {r['name']} 已有简历文本，跳过")
                continue
            rt = build_resume(r)
            # 1) 写 resume_text（如实基于档案字段）
            db.execute(text("UPDATE tal_talent SET resume_text=:rt WHERE id=:id"),
                       {"rt": rt, "id": tid})
            # 2) 上传 MinIO（可选增强，失败不阻塞）
            try:
                if storage:
                    storage.put_bytes(f"backfill/resume_{tid}.txt", rt.encode("utf-8"), "text/plain")
                    db.execute(text("UPDATE tal_talent SET object_key=:k WHERE id=:id"),
                               {"k": f"backfill/resume_{tid}.txt", "id": tid})
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠️ MinIO 上传失败(忽略): {type(e).__name__}")
            # 3) LLM 研判 → 报告 + 主档填空
            talent = db.get(Talent, tid)
            try:
                ResumeLLMService.apply(db, talent, rt)
                db.commit()
                rpt = db.execute(text("SELECT ability_level, composite_score, potential, summary_report "
                                      "FROM tal_talent_report WHERE talent_id=:id"), {"id": tid}).mappings().first()
                ok = "✅" if rpt else "⚠️(无报告行)"
                print(f"#{tid} {r['name']} {ok} 简历{len(rt)}字 | "
                      f"ability={rpt['ability_level'] if rpt else '-'} score={rpt['composite_score'] if rpt else '-'} "
                      f"potential={rpt['potential'] if rpt else '-'}")
            except Exception as e:  # noqa: BLE001
                db.rollback()
                print(f"#{tid} {r['name']} ❌ apply 失败: {type(e).__name__}: {str(e)[:150]}")


if __name__ == "__main__":
    main()
