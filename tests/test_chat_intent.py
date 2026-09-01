import sys
sys.path.insert(0, '.')

from app.ai.agents.match_agent import MatchAgent
from app.db.session import SessionLocal

db = SessionLocal()
cases = [
    '分析后端开发工程师的岗位要求',
    '帮我找适合后端开发的人才',
    '生成后端开发的折线图',
    '生成AI架构师的柱状图',
    '生成前端开发的饼图',
    '人才5适合什么岗位',
    '为什么人才4排第一',
    '分析AI架构师岗位的要求',
    '生成AI 架构师的折线图',
    '画一下AI架构师岗位的柱状图',
    '帮我找适合前端开发的人才，本科、2年经验',
    '生成AIGC内容设计师的饼图',
    '生成后端工程师的折线图',
    '显示运维工程师的柱状图',
    '看测试开发工程师的饼图',
    '帮我找适合后端开发的资深人才，要求会Python',
    '生成柱状图',
    '画饼图',
    '你好',
    'XXX',
]
ok = 0
fail = []
for q in cases:
    try:
        r = MatchAgent.chat(db, q)
        good = r['intent'] in ('parse', 'match', 'reverse', 'explain', 'chart')
        mark = 'OK' if good else 'NG'
        if good: ok += 1
        else: fail.append(q)
        n = 0
        if r.get('result') and isinstance(r['result'], dict) and r['result'].get('results'):
            n = len(r['result']['results'])
        ctype = r.get('chart_type') or ''
        print(f"{mark:<3} [{q[:32]:<32}] intent={r['intent']:<7} type={ctype:<5} res={n}")
    except Exception as e:
        print(f"ERR [{q[:32]:<32}] {type(e).__name__}: {str(e)[:80]}")
        fail.append(q)
print(f"\n通过 {ok}/{len(cases)}")
if fail:
    print("失败:")
    for f in fail:
        print(f"  - {f}")
db.close()