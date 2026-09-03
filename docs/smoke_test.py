# -*- coding: utf-8 -*-
"""全系统 API 冒烟测试：登录后遍历各模块核心接口。"""
import os
import requests, json, time, sys

BASE = "http://127.0.0.1:8000/api/v1"
ADMIN_PASSWORD = os.getenv("SMOKE_ADMIN_PASSWORD")
results = []

def call(name, method, path, token=None, body=None, timeout=15):
    url = BASE + path
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    t0 = time.time()
    try:
        r = requests.request(method, url, headers=headers, json=body, timeout=timeout)
        cost = time.time() - t0
        ok = r.status_code < 400
        # 提取有效负载信息
        try:
            data = r.json()
            payload = data.get("data") if isinstance(data, dict) else data
            has_data = payload not in (None, [], {}) and not (isinstance(payload, dict) and payload.get("items") == [] and "items" in payload)
            summary = ""
            if isinstance(payload, dict) and "items" in payload:
                summary = f"items={len(payload['items'])} total={payload.get('total','?')}"
            elif isinstance(payload, list):
                summary = f"len={len(payload)}"
            elif isinstance(payload, dict) and payload:
                keys = list(payload.keys())[:4]
                summary = f"fields={keys}"
        except Exception:
            has_data, summary = False, r.text[:50]
        results.append((name, method, path, r.status_code, round(cost, 2), "有数据" if has_data else "空", summary))
        return r
    except Exception as e:
        results.append((name, method, path, "ERR", 0, "", str(e)[:60]))
        return None

# ========== 1. 登录 ==========
print("== 登录 ==")
if not ADMIN_PASSWORD:
    print("!! 请通过环境变量 SMOKE_ADMIN_PASSWORD 提供管理员密码")
    sys.exit(2)
r = call("登录", "POST", "/auth/login", body={"username": "admin", "password": ADMIN_PASSWORD})
if not r or r.status_code >= 400:
    print("!! 登录失败，无法继续。响应:", r.text[:300] if r else "无响应")
    sys.exit(1)
token = r.json()["data"]["access_token"]
user = r.json()["data"]["user"]
print("登录成功:", user.get("nickname"), "| 超管:", user.get("is_super"))

# ========== 2. 系统域 ==========
print("\n== 系统域 ==")
call("当前用户", "GET", "/auth/me", token)
call("用户列表", "GET", "/users?page=1&page_size=5", token)
call("角色列表", "GET", "/roles", token)
call("菜单列表", "GET", "/menus", token)
call("我的菜单", "GET", "/menus/mine", token)
call("部门列表", "GET", "/depts", token)
call("字典类型", "GET", "/dicts/types", token)

# ========== 3. 测评域 ==========
print("\n== 测评域 ==")
call("题库分页", "GET", "/assessment/banks", token)
call("题目分页", "GET", "/assessment/questions", token)
call("试卷列表", "GET", "/assessment/papers", token)
call("结果列表", "GET", "/assessment/results", token)
call("结果统计", "GET", "/assessment/results/statistics", token)
call("批次统计", "GET", "/assessment/results/statistics/batches", token)
call("能力模型", "GET", "/assessment/capability-models", token)

# ========== 4. 人才域 ==========
print("\n== 人才域 ==")
call("人才列表", "GET", "/talent?page=1&page_size=5", token)
call("人才统计", "GET", "/talent/stats", token)
call("标签列表", "GET", "/talent/tags", token)
call("标签字典", "GET", "/talent-dicts", token)
call("过期提醒", "GET", "/talent/expiring", token)

# ========== 5. 培训域 ==========
print("\n== 培训域 ==")
call("培训计划", "GET", "/training/plans", token)
call("课程列表", "GET", "/training/courses", token)
call("培训效果", "GET", "/training/effects", token)
call("培训人才", "GET", "/training/talents", token)

# ========== 6. 匹配域 ==========
print("\n== 匹配域 ==")
call("岗位列表", "GET", "/matching/positions", token)
call("匹配规则", "GET", "/matching/rules", token)
call("匹配结果", "GET", "/matching/results", token)
call("匹配预警", "GET", "/matching/alerts", token)

# ========== 7. 数据决策域 ==========
print("\n== 数据决策域 ==")
call("看板概览", "GET", "/analytics/overview", token)
call("趋势序列", "GET", "/analytics/trend", token)
call("分布统计", "GET", "/analytics/distribution?dim=education", token)
call("多维筛选", "GET", "/analytics/dim-filter", token)

# ========== 8. 消息/审计 ==========
print("\n== 消息/审计 ==")
call("消息列表", "GET", "/messages", token)
call("审计日志", "GET", "/audit/operations", token)
call("登录日志", "GET", "/audit/logins", token)

# ========== 9. 知识库/AI ==========
print("\n== 知识库/AI ==")
call("RAG问答", "POST", "/talent/rag", token, body={"question": "介绍一下公司"})

# ========== 输出汇总 ==========
print("\n" + "=" * 100)
print(f"{'接口':<14}{'方法':<6}{'路径':<42}{'状态':<6}{'耗时':<7}{'数据'}")
print("-" * 100)
fail = 0
for name, method, path, status, cost, has, summary in results:
    if status == "ERR":
        flag = "❌"
        fail += 1
    elif status == 200:
        flag = "✅"
    elif status < 400:
        flag = "⚠️"
    else:
        flag = "❌"
        fail += 1
    print(f"{flag} {name:<12}{method:<6}{path:<42}{str(status):<6}{str(cost):<7}{has} {summary}")
print("-" * 100)
print(f"总接口数: {len(results)} | 失败/异常: {fail}")
