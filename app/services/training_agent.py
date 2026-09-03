"""Agent④ 培训推送（TR-3）：读短板 + 岗位需求 → 选课 → 生成计划 → 推送。

v2 增强：
- 短板来源：``tal_talent_report.summary_report``（人才研判评估总结）→ LLM 提取短板标签，
  降级用结构化 ``shortcomings`` 字段 / 规则关键词。
- 岗位需求来源：人才适配岗位（``match_result`` 按 score 取最高）→ ``pos_position.description``
  岗位说明书 → LLM 总结岗位能力需求，降级规则化提取。
- 选课：结合「短板 + 岗位需求」双维度（LLM 增强 + allow_tags 规则兜底）。
- 兼容旧契约：shortage_tags / position_ids 均可为空，为空时自动读取，不影响既有调用。

设计原则：LLM 只做提取/推理，失败即降级；推送调用 MessageService（消息域，同事负责）。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.dao.training import CourseDAO
from app.models.training import Lesson
from app.utils.llm import get_llm
from app.utils.logger import logger
from app.utils.response import BusinessError


# ========== JSON 列表提取容错 ==========
def _extract_json_list(content: str) -> list[Any]:
    """从 LLM 返回中稳健提取 JSON 数组（容忍 markdown 代码块/前后噪音）。"""
    if not content:
        return []
    text = content.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except ValueError:
        pass
    m = re.search(r"$$[\s\S]*$$", text)
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, list) else []
        except ValueError:
            return []
    return []


class TrainingAgentService:
    """智能培训 Agent 服务（TR-3）。"""

    # ==================== 短板提取 ====================

    @staticmethod
    def _read_shortcomings(db: Session, talent_id: int) -> tuple[list[str], str]:
        """读人才短板：优先 summary_report 提取，降级 shortcomings 结构化字段。

        返回 (shortage_tags, raw_context)。
        """
        from app.dao.talent_report import TalentReportDAO

        report = TalentReportDAO.get_by(db, talent_id=talent_id)
        raw_context = ""
        # 降级源：结构化 shortcomings 字段（JSON list）
        struct_short: list[str] = []
        if report and report.shortcomings:
            try:
                v = json.loads(report.shortcomings)
                struct_short = [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
            except (ValueError, TypeError):
                struct_short = []
        # 主源：summary_report 评估总结
        summary = (report.summary_report or "").strip() if report else ""
        if summary:
            raw_context = summary
            tags = TrainingAgentService._extract_shortages_llm(summary)
            if tags:
                return tags, raw_context
            tags = TrainingAgentService._extract_shortages_rule(summary)
            if tags:
                return tags, raw_context
        return struct_short, raw_context

    @staticmethod
    def _extract_shortages_llm(summary: str) -> list[str]:
        """LLM 从评估总结提取短板标签（失败返回 []）。"""
        try:
            llm = get_llm()
            prompt = (
                "你是人才发展专家。请从下面的人才研判评估总结中，提取能力短板标签，"
                "输出**纯 JSON 数组**（不要 markdown 代码块），例如 [\"沟通协作\",\"数据建模\"]。\n"
                "要求：标签用 2~6 字中文短语；只提取短板，不要优势；没有短板输出 []。\n"
                f"评估总结：{summary[:3000]}"
            )
            resp = llm.chat(prompt, system="只输出合法 JSON 数组，不要任何解释。", temperature=0.2)
            return [str(x).strip() for x in _extract_json_list(resp) if str(x).strip()]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _extract_shortages_rule(summary: str) -> list[str]:
        """规则化提取短板：抓「短板/不足/欠缺/待提升」等后的短语。"""
        tags: list[str] = []
        for m in re.finditer(
            r"(?:短板|不足|欠缺|待提升|薄弱|缺乏|不够|需加强)[：:、\s]*([\u4e00-\u9fa5A-Za-z]{2,8})",
            summary,
        ):
            tags.append(m.group(1).strip())
        return list(dict.fromkeys(tags))[:6]

    # ==================== 岗位需求提取 ====================

    @staticmethod
    def _read_positions(db: Session, talent_id: int,
                        position_ids: list[int] | None) -> list[dict]:
        """读人才适配岗位：显式 position_ids 优先，否则从 match_result 取最高分岗位。

        返回 [{position_id, name, description}]。
        """
        from app.dao.matching import MatchResultDAO, PosPositionDAO

        positions: list[dict] = []
        if position_ids:
            for pid in position_ids:
                p = PosPositionDAO.get(db, pid)
                if p:
                    positions.append({"position_id": p.id, "name": p.name,
                                      "description": p.description or ""})
            return positions
        # 从匹配结果取该人才最高分岗位（前 3）
        recs = db.execute(
            select(MatchResultDAO.__model__)
            .where(MatchResultDAO.__model__.talent_id == talent_id)
            .order_by(MatchResultDAO.__model__.score.desc())
            .limit(3)
        ).scalars().all()
        for r in recs:
            p = PosPositionDAO.get(db, r.position_id)
            if p:
                positions.append({"position_id": p.id, "name": p.name,
                                  "description": p.description or ""})
        return positions

    @staticmethod
    def _summarize_position_llm(name: str, description: str) -> list[str]:
        """LLM 总结岗位说明书 → 岗位能力要求标签（失败返回 []）。"""
        if not description.strip():
            return []
        try:
            llm = get_llm()
            prompt = (
                "你是岗位分析师。请根据岗位名称和岗位说明书，总结该岗位的核心能力要求标签，"
                "输出**纯 JSON 数组**（不要 markdown 代码块），例如 [\"Python\",\"系统架构设计\",\"团队管理\"]。\n"
                "要求：标签用 2~6 字中文/英文短语，覆盖技能、经验、素质维度；5~10 个。\n"
                f"岗位名称：{name}\n岗位说明书：{description[:3000]}"
            )
            resp = llm.chat(prompt, system="只输出合法 JSON 数组，不要任何解释。", temperature=0.2)
            return [str(x).strip() for x in _extract_json_list(resp) if str(x).strip()]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _summarize_position_rule(name: str, description: str) -> list[str]:
        """规则化总结岗位需求：关键词提取（复用 M 域思路）。"""
        desc = description or ""
        stop = {"岗位", "要求", "负责", "具备", "熟悉", "掌握", "能够", "以及", "或者", "优先",
                "能力", "相关", "工作", "学历", "经验", "以上", "本科", "硕士", "开发", "设计",
                "任职", "资格", "职责"}
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fa5]{2,6}", desc)
        skills = [w for w in words if w not in stop and len(w) > 1]
        tags = list(dict.fromkeys(skills))[:10]
        if name and name not in tags:
            tags.insert(0, name)
        return tags

    # ==================== 选课 ====================

    @staticmethod
    def recommend(db, *, talent_id: int, shortage_tags: list[str],
                  allow_courses: list, generated_by: str = "agent",
                  position_tags: list[str] | None = None) -> dict:
        """选课推荐：结合短板 + 岗位需求（position_tags 可选），返回 {course_ids, reason}。"""
        position_tags = position_tags or []
        all_tags = shortage_tags + position_tags

        # 规则兜底：allow_tags 命中短板或岗位标签，按命中数排序
        def _hit(course) -> int:
            course_tags = [t.strip() for t in (course.allow_tags or "").split(",") if t.strip()]
            if not course_tags:
                return 0
            score = 0
            for tag in all_tags:
                for ct in course_tags:
                    if tag and (tag.lower() in ct.lower() or ct.lower() in tag.lower()):
                        score += 1
            return score

        matched = sorted(allow_courses, key=_hit, reverse=True)
        matched = [c for c in matched if _hit(c) > 0]
        if not matched:
            matched = allow_courses[:3]  # 无命中则取前 3 门兜底

        reason = f"规则匹配：短板 {shortage_tags} + 岗位需求 {position_tags}"
        course_ids = [c.id for c in matched]

        # LLM 增强选课（失败保持规则结果）
        try:
            llm = get_llm()
            catalog = [{"id": c.id, "title": c.title, "tags": c.allow_tags} for c in allow_courses]
            prompt = (
                f"人才短板标签：{shortage_tags}。岗位能力需求：{position_tags}。可选课程：{catalog}。"
                "请选出最能补足短板并满足岗位需求的课程，只返回课程 id 的 JSON 数组，如 [1,3]。"
            )
            resp = llm.chat(prompt)
            ids = _extract_json_list(resp)
            if ids:
                course_ids = [int(i) for i in ids if str(i).isdigit()]
                reason = f"Agent④ 推理：{resp[:100]}"
        except Exception:  # noqa: BLE001
            pass

        return {"course_ids": course_ids, "reason": reason}

    # ==================== 主流程 ====================




    @staticmethod
    def _catalog_has_video(db: Session) -> list:
        """候选课程 = 状态上架 且 至少含一个 video_id 课节（培训必有视频）。"""
        Course = CourseDAO.__model__
        has_video = exists().where(and_(Lesson.course_id == Course.id,
                                        Lesson.video_id.is_not(None)))
        return list(db.scalars(
            select(Course).where(Course.status == 1, has_video).limit(500)))

    @staticmethod
    def preview(db, *, talent_id: int, shortage_tags: list[str] | None = None,
                position_ids: list[int] | None = None) -> dict:
        """预览：读短板 + 岗位需求 → 选课，返回课程明细，不写库、不发消息。"""

        # 1. 短板
        if shortage_tags:
            tags = [str(t).strip() for t in shortage_tags if str(t).strip()]
        else:
            tags, _ = TrainingAgentService._read_shortcomings(db, talent_id)

        # 2. 岗位需求
        positions = TrainingAgentService._read_positions(db, talent_id, position_ids)
        position_tags: list[str] = []
        position_names: list[str] = []
        for p in positions:
            position_names.append(p["name"])
            tags_llm = TrainingAgentService._summarize_position_llm(p["name"], p["description"])
            if not tags_llm:
                tags_llm = TrainingAgentService._summarize_position_rule(p["name"], p["description"])
            position_tags.extend(tags_llm)
        position_tags = list(dict.fromkeys(position_tags))

        # 3. 选课
        courses = TrainingAgentService._catalog_has_video(db)
        if not courses:
            return {"talent_id": talent_id, "course_ids": [], "courses": [],
                    "reason": "暂无可推荐课程：课程库中尚无含视频课节的课程，请先在管理端给课程挂接视频",
                    "shortage_tags": tags, "position_tags": position_tags,
                    "positions": [{"position_id": p["position_id"], "name": p["name"]} for p in positions],
                    "video_only": True}
        rec = TrainingAgentService.recommend(
            db, talent_id=talent_id, shortage_tags=tags,
            position_tags=position_tags, allow_courses=courses,
        )

        # 4. 组装课程明细（供前端预览展示）
        course_map = {c.id: c for c in courses}
        course_details = [
            {
                "id": cid,
                "title": course_map[cid].title if cid in course_map else f"课程#{cid}",
                "category": course_map[cid].category if cid in course_map else "",
                "score": course_map[cid].score if cid in course_map else 0,
                "allow_tags": course_map[cid].allow_tags if cid in course_map else "",
            }
            for cid in rec["course_ids"]
        ]

        return {
            "talent_id": talent_id,
            "course_ids": rec["course_ids"],
            "courses": course_details,
            "reason": rec["reason"],
            "shortage_tags": tags,
            "position_tags": position_tags,
            "positions": [{"position_id": p["position_id"], "name": p["name"]} for p in positions],
        }


    @staticmethod
    def generate_plan(db, *, talent_id: int, course_ids: list[int],
                      shortage_tags: list[str] | None = None,
                      position_tags: list[str] | None = None,
                      position_names: list[str] | None = None,
                      title: str = "个性化培训计划", deadline=None,
                      push: bool = True) -> dict:
        """确认生成计划：按已选 course_ids 建计划 + （可选）推送消息。

        与 preview 分离：preview 只选课不落库，本方法负责落库 + 推送。
        """
        from app.services.training_service import PlanService
        from app.services.message_service import MessageService

        shortage_tags = shortage_tags or []
        position_tags = position_tags or []
        position_names = position_names or []

        # 培训必有视频：剔除无视频课节的课程（防御 preview 外的直接调用）
        if course_ids:
            Course = CourseDAO.__model__
            has_video = exists().where(and_(Lesson.course_id == Course.id,
                                            Lesson.video_id.is_not(None)))
            valid_ids = set(db.scalars(
                select(Course.id).where(Course.id.in_(course_ids), has_video)).all())
            dropped = [cid for cid in course_ids if cid not in valid_ids]
            if dropped:
                logger.warning("[train] 剔除无视频课节的课程(培训必有视频): %s", dropped)
            course_ids = [cid for cid in course_ids if cid in valid_ids]

        # 推送接收人必须是登录账号 user_id。先校验再建计划，避免无账号时
        # 只创建计划、未发送消息，却向前端返回“已推送”的假成功。
        receiver_user_id = None
        if push:
            receiver_user_id = MessageService.user_id_for_talent(db, talent_id)
            if receiver_user_id is None:
                raise BusinessError(400, "该人才档案未关联有效员工账号，无法推送培训计划")

        # 建计划（weakness_tags 存短板 + 岗位名 + 岗位需求标签）
        weakness_tags = list(dict.fromkeys(
            shortage_tags + [f"岗位:{n}" for n in position_names] + position_tags))
        plan = PlanService.create(
            db, talent_id=talent_id, title=title, course_ids=course_ids,
            deadline=deadline, generated_by="agent", weakness_tags=weakness_tags,
        )

        # 推送
        if push:
            try:
                MessageService.send(
                    db, type_code="train", title=title,
                    content=f"已为你生成个性化培训计划（含 {len(course_ids)} 门课程，"
                            f"针对短板与适配岗位 {position_names or '通用能力'}）",
                    receiver_ids=[receiver_user_id], biz_type="training", biz_id=plan.id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("[train] 培训消息推送失败，事务将回滚：%s", exc)
                raise BusinessError(500, "培训计划消息推送失败，请稍后重试") from exc

        return {
            "plan_id": plan.id,
            "course_ids": course_ids,
            "shortage_tags": shortage_tags,
            "position_tags": position_tags,
            "positions": [{"name": n} for n in position_names],
            "pushed": bool(push and receiver_user_id),
        }

