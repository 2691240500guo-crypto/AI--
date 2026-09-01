"""人才 ↔ 标签 关联（批次2.1 → 合并后适配 tal_talent_tag）。

2026-09-01 合并说明（hq+）：
- 方案 A：关联统一用袁文武的 ``tal_talent_tag`` 表（talent_id/tag_id/source/score）
- 本文件改为 re-export ``tal_talent_tag`` 的 model，保持旧 import 链（TalentTagDAO 等）可用
"""
# hq新增内容 - 人才档案批次2.1 + 合并
from app.models.talent import TalentTalentTag as TalentTag  # noqa: F401  hq+  tal_talent_tag 关联
