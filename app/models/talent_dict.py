"""人才标签字典（批次2.1 → 合并后适配 tal_tag）。

2026-09-01 合并说明（hq+）：
- 方案 A：标签统一用袁文武的 ``tal_tag`` 表（name/category/description/is_builtin）
- 我的 128 条字典种子导入 tal_tag（is_builtin=1）
- 本文件改为 re-export ``tal_tag`` 的 model，保持旧 import 链（TalentDictDAO 等）可用
"""
# hq新增内容 - 人才档案批次2.1 + 合并
from app.models.talent import TalentTag as TalentDict  # noqa: F401  hq+  tal_tag 字典
