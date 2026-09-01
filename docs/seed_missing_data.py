# -*- coding: utf-8 -*-
"""
数据补齐种子脚本（2026-09-01）
1. 清理菜单残留（答题台/题库管理/题目管理）
2. 培训：补正常课程+课节+5 条计划（覆盖 4 状态）+ 进度
3. 匹配预警：调用系统生成接口
4. 人才过期：补 expire_at
全部幂等可重跑。
"""
import pymysql, requests, json, datetime, sys

BASE = "http://127.0.0.1:8000/api/v1"
DB = dict(host='120.77.177.232', port=3306, user='adtp_db', password='12345678',
          database='adtp_db', connect_timeout=8, autocommit=True, charset='utf8mb4')

def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=15)
    r.raise_for_status()
    return r.json()["data"]["access_token"]

def api(method, path, token, body=None):
    r = requests.request(method, f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"},
                         json=body, timeout=20)
    print(f"  [{r.status_code}] {method} {path} {str(body)[:60]}")
    if r.status_code >= 400:
        print(f"    !! {r.text[:200]}")
    return r

# ========== 0. 登录 ==========
print("== 登录 ==")
token = login()
print("OK")

# ========== 1. 菜单残留清理（SQL）==========
print("\n== 1. 清理菜单残留 ==")
conn = pymysql.connect(**DB)
cur = conn.cursor()
cur.execute("DELETE FROM sys_role_menu WHERE menu_id IN (18,35,36)")
print(f"  删角色关联: {cur.rowcount} 条")
cur.execute("DELETE FROM sys_menu WHERE id IN (18,35,36)")
print(f"  删菜单: {cur.rowcount} 条")

# ========== 2. 培训课程 + 课节 ==========
print("\n== 2. 补培训课程与课节 ==")
courses = [
    {"title": "Python后端开发实战", "category": "技术", "intro": "FastAPI/MySQL 后端开发核心技能训练",
     "score": 20, "allow_tags": "后端开发,数据库", "status": 1,
     "lessons": [("环境搭建与FastAPI入门", 30), ("ORM与数据库建模", 45), ("接口设计与安全", 45)]},
    {"title": "AI数据分析实战", "category": "技术", "intro": "基于大模型的数据分析与可视化",
     "score": 16, "allow_tags": "数据分析,AI", "status": 1,
     "lessons": [("数据分析基础", 30), ("大模型辅助分析", 45), ("可视化看板", 30)]},
    {"title": "高效沟通与项目管理", "category": "管理", "intro": "职场沟通与项目协作方法论",
     "score": 8, "allow_tags": "项目管理,沟通", "status": 1,
     "lessons": [("高效会议与沟通", 30), ("项目计划与跟进", 45)]},
]
new_course_ids = []
for c in courses:
    r = api("POST", "/training/courses", token, {k: v for k, v in c.items() if k != "lessons"})
    if r.status_code < 400:
        cid = r.json()["data"]["id"]
        new_course_ids.append(cid)
        for title, dur in c["lessons"]:
            api("POST", f"/training/courses/{cid}/lessons", token,
                {"title": title, "content": "", "duration": dur, "sort": 0})
print(f"  新课程 id: {new_course_ids}")

# ========== 3. 培训计划（覆盖 4 状态）==========
print("\n== 3. 补培训计划 ==")
now = datetime.date(2026, 9, 1)
plans = [
    {"talent_id": 4, "title": "Python后端开发能力提升计划", "course_ids": [new_course_ids[0]],
     "deadline": "2026-09-20", "weakness_tags": ["后端开发", "数据库"], "status": 1,
     "generated_by": "manual", "improvement": 15},
    {"talent_id": 6, "title": "AI数据分析专项训练计划", "course_ids": [new_course_ids[1]],
     "deadline": "2026-09-30", "weakness_tags": ["数据分析"], "status": 0,
     "generated_by": "agent", "improvement": 10},
    {"talent_id": 7, "title": "新人融入与后端基础培训", "course_ids": [new_course_ids[0]],
     "deadline": "2026-08-15", "weakness_tags": ["Python基础"], "status": 2,
     "generated_by": "manual", "improvement": 20},
    {"talent_id": 10, "title": "项目管理能力提升计划", "course_ids": [new_course_ids[2]],
     "deadline": "2026-08-05", "weakness_tags": ["项目管理"], "status": 3,
     "generated_by": "agent", "improvement": 10},
    {"talent_id": 5, "title": "AI办公效能提升计划", "course_ids": [1, new_course_ids[1]],
     "deadline": "2026-09-25", "weakness_tags": ["AI工具"], "status": 1,
     "generated_by": "agent", "improvement": 12},
]
plan_ids = []
for p in plans:
    r = api("POST", "/training/plans", token, p)
    if r.status_code < 400:
        plan_ids.append(r.json()["data"]["id"])

# ========== 4. 计划进度（已完成/进行中）==========
print("\n== 4. 打学习进度 ==")
progress = [
    (plan_ids[0], new_course_ids[0], 60, 600),   # 进行中 60%
    (plan_ids[2], new_course_ids[0], 100, 1200), # 已完成 100%
    (plan_ids[4], new_course_ids[1], 40, 400),   # 进行中 40%
]
for pid, cid, prog, minutes in progress:
    api("PUT", f"/training/plan/{pid}/progress", token,
        {"course_id": cid, "lesson_id": 0, "progress": prog, "learned_minutes": minutes})

# ========== 5. 匹配预警（系统生成）==========
print("\n== 5. 生成匹配预警 ==")
api("POST", "/matching/alerts/generate", token, {})

# ========== 6. 人才过期（SQL）==========
print("\n== 6. 补人才过期提醒 ==")
updates = [
    (1, "2026-08-20"),    # 已过期 12 天
    (6, "2026-09-10"),    # 9 天后过期
    (10, "2026-09-15"),   # 14 天后过期
    (18, "2026-09-25"),   # 24 天后过期
]
for tid, exp in updates:
    cur.execute("UPDATE tal_talent SET expire_at=%s WHERE id=%s AND expire_at IS NULL", (exp, tid))
    print(f"  人才 {tid} expire_at={exp} 影响 {cur.rowcount} 行")
conn.close()
print("\n全部执行完成 ✅")
