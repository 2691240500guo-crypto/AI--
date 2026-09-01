"""Agent④ 培训推送（TR-3）：读短板+岗位能力 → 选课 → 生成计划 → 推送。

设计要点：
- LLM 只做「选课推理」，返回结构化课程 id；LLM 不可用时走规则兜底（按 allow_tags 匹配）。
- 推送调用 MessageService（消息域，同事负责），本模块仅「调用」。
"""
from app.dao.training import CourseDAO, PlanDAO
from app.utils.llm import get_llm


class TrainingAgentService:
    @staticmethod
    def recommend(db, *, talent_id: int, shortage_tags: list[str],
                  allow_courses: list, generated_by: str = "agent") -> dict:
        """选课推荐，返回 {course_ids, reason}。LLM 失败降级为规则匹配。"""
        # 规则兜底：allow_tags 命中短缺标签的课程
        matched = [c for c in allow_courses
                   if any(tag in (c.allow_tags or "").split(",") for tag in shortage_tags)]
        if not matched:
            matched = allow_courses[:3]  # 无命中则取前 3 门兜底

        reason = f"规则匹配：短缺 {shortage_tags}"
        course_ids = [c.id for c in matched]

        # 尝试 LLM 增强选课（失败则保持规则结果）
        try:
            llm = get_llm()
            prompt = (
                f"人才短缺能力标签：{shortage_tags}。可选课程："
                f"{[{'id': c.id, 'title': c.title, 'tags': c.allow_tags} for c in allow_courses]}。"
                "请选出最合适的课程，只返回课程 id 的 JSON 数组，如 [1,3]。"
            )
            import json
            resp = llm.chat(prompt)
            ids = json.loads(resp.strip().strip("`"))
            if isinstance(ids, list) and ids:
                course_ids = [int(i) for i in ids if str(i).isdigit()]
                reason = f"Agent④ 推理：{resp[:100]}"
        except Exception:
            pass  # 降级到规则结果

        return {"course_ids": course_ids, "reason": reason}

    @staticmethod
    def generate_plan(db, *, talent_id: int, shortage_tags: list[str],
                      title: str = "个性化培训计划", deadline=None) -> dict:
        """生成学习计划并推送消息（TR-3 主流程）。"""
        from app.services.training_service import PlanService
        from app.services.message_service import MessageService

        courses = CourseDAO.list(db, CourseDAO.__model__.status == 1, limit=500)
        rec = TrainingAgentService.recommend(
            db, talent_id=talent_id, shortage_tags=shortage_tags, allow_courses=courses)
        plan = PlanService.create(
            db, talent_id=talent_id, title=title, course_ids=rec["course_ids"],
            deadline=deadline, generated_by="agent", weakness_tags=shortage_tags,
        )
        # 推送消息（调用消息域 MessageService，不修改其代码）
        MessageService.send(
            db, type_code="train", title=title,
            content=f"已为你生成个性化培训计划（含 {len(rec['course_ids'])} 门课程）",
            receiver_ids=[talent_id], biz_type="training", biz_id=plan.id,
        )
        return {"plan_id": plan.id, "course_ids": rec["course_ids"], "reason": rec["reason"]}
