# -*- coding: utf-8 -*-
"""M 域（岗位匹配）功能冒烟测试：只读 + 幂等为主，不修改业务状态。

覆盖：登录 / 岗位列表 / 发起匹配(幂等) / 结果列表(默认排序) /
     姓名筛选 / level/exp_years/quality_score 排序不 500 /
     解释生成 / 预警列表。可选 --agent 跑 3 条代表性自然语言指令。

用法：
    D:\\Aconda\\envs\\ai-talent\\python.exe scripts\\smoke_matching.py
    D:\\Aconda\\envs\\ai-talent\\python.exe scripts\\smoke_matching.py --base http://127.0.0.1:8000/api/v1 --agent
"""
from __future__ import annotations

import argparse
import sys

import requests

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{mark}] {name} {extra}")
    return cond


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000/api/v1", help="后端地址（含 /api/v1）")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    ap.add_argument("--agent", action="store_true", help="额外跑 Agent 自然语言（较慢）")
    args = ap.parse_args()

    s = requests.Session()
    print("== [1] 登录 ==")
    r = s.post(f"{args.base}/auth/login", json={
        "username": args.username, "password": args.password,
    }, timeout=15)
    if r.status_code != 200 or not (r.json().get("data") or {}).get("access_token"):
        print("  [FAIL] 登录失败:", r.status_code, r.text[:200])
        return 1
    at = r.json()["data"]["access_token"]
    s.headers["Authorization"] = f"Bearer {at}"
    print("  [PASS] 登录成功")

    print("== [2] 岗位管理 ==")
    r = s.get(f"{args.base}/matching/positions", params={"page": 1, "page_size": 50}, timeout=15)
    pos_items = (r.json().get("data") or {}).get("items") or []
    check("岗位列表", r.status_code == 200 and len(pos_items) >= 1, f"(岗位数={len(pos_items)})")

    print("== [3] 发起匹配（幂等，允许重跑） ==")
    try:
        r = s.post(f"{args.base}/matching/match", json={"top_k": 10}, timeout=120)
        n = len((r.json().get("data") or {}).get("saved") or [])
        check("发起匹配", r.status_code == 200, f"(本批新增/更新={n})")
    except requests.RequestException as e:
        check("发起匹配", False, str(e)[:100])

    print("== [4] 匹配结果列表（默认排序 + 不 500） ==")
    try:
        r = s.get(f"{args.base}/matching/results", params={"page": 1, "page_size": 5, "sort_by": "score"}, timeout=15)
        items = (r.json().get("data") or {}).get("items") or []
        ok = r.status_code == 200
        check("score 排序", ok, f"(返回={len(items)})")
        if ok and items:
            t0 = items[0]
            check("结果含姓名(方案B)", t0.get("talent_name") is not None, f"(首行={t0.get('talent_name') or 'NULL'} #{t0.get('talent_id')})")
        else:
            check("结果含姓名(方案B)", False, "无数据")
    except requests.RequestException as e:
        check("score 排序", False, str(e)[:100])

    for sb in ("level", "exp_years", "quality_score", "rank"):
        try:
            r = s.get(f"{args.base}/matching/results", params={"page": 1, "page_size": 5, "sort_by": sb}, timeout=15)
            check(f"sort_by={sb}", r.status_code == 200)
        except requests.RequestException as e:
            check(f"sort_by={sb}", False, str(e)[:80])

    print("== [5] 姓名筛选（方案B：talent_name） ==")
    try:
        r = s.get(f"{args.base}/matching/results", params={"talent_name": "陆", "page": 1, "page_size": 5}, timeout=15)
        ok = r.status_code == 200
        names = [(i.get("talent_name") or "") for i in (r.json().get("data") or {}).get("items") or []]
        check("talent_name 模糊筛选", ok and names and any("陆" in n for n in names), f"(命中={names[:3]})")
    except requests.RequestException as e:
        check("talent_name 模糊筛选", False, str(e)[:80])

    print("== [6] 匹配解释（LLM/规则） ==")
    try:
        r = s.get(f"{args.base}/matching/results", params={"page": 1, "page_size": 1, "sort_by": "score"}, timeout=15)
        mid = ((r.json().get("data") or {}).get("items") or [{}])[0].get("id")
        if mid:
            r = s.get(f"{args.base}/matching/result/{mid}/explain", timeout=60)
            ex = (r.json().get("data") or {}).get("explain") or ""
            check("解释生成", r.status_code == 200 and len(ex) >= 5, f"(前20字={ex[:20]!r})")
        else:
            check("解释生成", False, "无结果")
    except requests.RequestException as e:
        check("解释生成", False, str(e)[:80])

    print("== [7] 储备/空缺预警（列表只读） ==")
    try:
        r = s.get(f"{args.base}/matching/alerts", timeout=15)
        arr = r.json().get("data") or []
        check("预警列表", r.status_code == 200, f"(预警数={len(arr) if isinstance(arr, list) else 'n/a'})")
    except requests.RequestException as e:
        check("预警列表", False, str(e)[:80])

    if args.agent:
        print("== [8] Agent 自然语言（每条约 5~20 秒） ==")
        samples = ["张一鸣适合什么岗位", "把陆一鸣设为推荐到后端开发工程师岗位", "分析后端开发工程师的岗位要求"]
        for q in samples:
            try:
                r = s.post(f"{args.base}/matching/agent/chat", json={"message": q}, timeout=180)
                d = r.json()
                intent = (d.get("data") or {}).get("intent") or (d.get("data") or {}).get("params", {}).get("intent")
                reply = ((d.get("data") or {}).get("reply") or "")[:20]
                check(f"chat: {q[:18]}…", r.status_code == 200, f"(intent={intent}, reply={reply!r})")
            except requests.RequestException as e:
                check(f"chat: {q[:18]}…", False, str(e)[:80])

    print("=" * 50)
    print(f"SMOKE DONE  PASS={PASS}  FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
