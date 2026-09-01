# -*- coding: utf-8 -*-
"""核对测评域云端表 vs 需求文档 4.2 字段"""
import re
import pymysql

md = open('docs/01-需求分析.md', encoding='utf-8').read()
sec = md.split('### 4.2')[1].split('### 4.3')[0]
req = {}
for line in sec.splitlines():
    m = re.match(r'\|\s*(`[a-z_]+`(?:\s*/\s*`[a-z_]+`)*)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\s*\|', line)
    if not m:
        continue
    names = re.findall(r'`([a-z_]+)`', m.group(1))
    fields = []
    for p in m.group(2).split(','):
        p = p.strip()
        if not p or 'UNIQUE' in p.upper():
            continue
        name = re.split(r'[\(\s]', p)[0].strip()
        if name and name not in fields:
            fields.append(name)
    for n in names:
        req.setdefault(n, fields)

conn = pymysql.connect(host='120.77.177.232', port=3306, user='adtp_db',
                       password='12345678', database='adtp_db', connect_timeout=8)
cur = conn.cursor()
print('=== 测评域 6 表：需求文档 4.2 vs 云端 ===')
for t in ['asm_question_bank', 'asm_question', 'asm_paper', 'asm_paper_question',
          'asm_result', 'asm_result_detail']:
    cur.execute(f'DESCRIBE {t}')
    cloud = [r[0] for r in cur.fetchall()]
    rf = set(req.get(t, []))
    cf = set(cloud)
    only_cloud = sorted(cf - rf)
    only_req = sorted(rf - cf)
    print(f'\n<< {t} >>  需求 {len(rf)} 字段 / 云端 {len(cf)} 列')
    print(f'  需求字段: {sorted(rf)}')
    if only_req:
        print(f'  [需求有云端缺→需加列] {only_req}')
    if only_cloud:
        print(f'  [云端多出需求无→扩展字段] {only_cloud}')
conn.close()
