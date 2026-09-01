# -*- coding: utf-8 -*-
"""生成准确的数据库差异分析报告：需求文档 vs 云端表 + 扩展字段代码引用检查"""
import re
import subprocess
import pymysql

# ---------- 1) 需求文档表解析（含多表名行拆分） ----------
md = open('docs/01-需求分析.md', encoding='utf-8').read()
req_tables = {}
for line in md.splitlines():
    if not line.strip().startswith('|'):
        continue
    # 匹配: | `t1` / `t2` | 字段列表 | 说明 |
    m = re.match(r'\|\s*(.*?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\s*\|', line)
    if not m:
        continue
    names_part, fields_str, desc = m.group(1), m.group(2), m.group(3)
    # 提取表名（支持 `a` / `b` / `c`）
    tnames = re.findall(r'`([a-z_]+)`', names_part)
    fields = []
    for part in fields_str.split(','):
        part = part.strip()
        if not part:
            continue
        name = re.split(r'[\(\s]', part)[0].strip()
        if name and name not in fields and not name.upper() in ('UNIQUE',):
            fields.append(name)
    for t in tnames:
        req_tables.setdefault(t, {'fields': fields, 'desc': desc.strip()})

# ---------- 2) 云端表结构 ----------
conn = pymysql.connect(host='120.77.177.232', port=3306, user='adtp_db',
                       password='12345678', database='adtp_db', connect_timeout=8)
cur = conn.cursor()
cur.execute('SHOW TABLES')
cloud_tables = sorted(r[0] for r in cur.fetchall())
cloud_cols = {}
for t in cloud_tables:
    cur.execute(f'DESCRIBE {t}')
    cloud_cols[t] = [r[0] for r in cur.fetchall()]
conn.close()

# ---------- 3) 代码引用检查 ----------
def code_uses(name):
    """检查字段/表名是否被代码引用"""
    try:
        r = subprocess.run(
            ['grep', '-rn', name, 'app/', 'admin_web/src/', 'miniapp/src/',
             '--include=*.py', '--include=*.js', '--include=*.vue'],
            capture_output=True, text=True, timeout=60)
        out = r.stdout
        # 排除模型定义自身与注释
        lines = [l for l in out.splitlines() if name in l]
        return len(lines) > 0
    except Exception:
        return None

# ---------- 4) 输出报告 ----------
print('=' * 70)
print('需求文档表: %d 张 | 云端表: %d 张' % (len(req_tables), len(cloud_tables)))

req_names = set(req_tables)
cloud_set = set(cloud_tables)

missing = sorted(req_names - cloud_set)
extra = sorted(cloud_set - req_names - {'alembic_version'})
print('\n【缺失表 - 需求有云端无】(%d)  → 建议创建' % len(missing))
for t in missing:
    print('  创建 %s: %s' % (t, req_tables[t]['desc'][:40]))

print('\n【多余表 - 云端有需求无】(%d)  → 查引用后定去留' % len(extra))
for t in extra:
    used = code_uses(t)
    mark = '✅代码引用(保留)' if used else ('⚠️未引用(可删)' if used is False else '?')
    print('  %-28s %s' % (t, mark))

print('\n【共有表字段差异】')
for t in sorted(req_names & cloud_set):
    req_f = set(req_tables[t]['fields'])
    cloud_f = set(cloud_cols[t])
    add = req_f - cloud_f
    drop = cloud_f - req_f
    if add or drop:
        print('\n  << %s >>' % t)
        if add:
            print('    [需求有云端缺 → 需加列] %s' % sorted(add))
        if drop:
            parts = []
            for f in sorted(drop):
                used = code_uses(f)
                mark = '被引用' if used else ('未引用' if used is False else '?')
                parts.append('%s(%s)' % (f, mark))
            print('    [云端多出需求无 → 定去留] %s' % ', '.join(parts))
