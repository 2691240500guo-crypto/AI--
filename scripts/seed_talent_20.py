"""一次性种子：生成 20 条与现有岗位高度匹配的人才（简历解析全链路演示数据）。

链路（每条）：
  构造中文简历文本 → ResumeUploadService.handle(bytes) [落MinIO→抽文本→落库草稿→规则打标签
  → LLM 解析(ResumeLLMService.apply 写 report/ability_level/composite_score/potential)
  → 去重检测 → T域四维向量] → 本脚本再按种子口径回写主档关键字段（保证排序口径可控）。

岗位对齐（云端 pos_position 8 个，全部启用）：
  1 HR专员 2 运维 3 测试开发 4 前端 5 AIGC设计 6 AI架构 7 AI产品 8 后端

用法：
  python scripts/seed_talent_20.py            # 全部 20 条（幂等：按 phone 查重跳过）
  python scripts/seed_talent_20.py --only 5   # 只跑第 5 条（排错用，1 起）
说明：保留库中原有人才不动；失败单条不阻塞后续。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text as sa_text  # noqa: E402

# ---------------------------------------------------------------------------
# 20 条种子定义：与岗位要求强对齐（技能覆盖 JD 关键词，学历/年限满足门槛）
# level: S/A/B/C（主表排序键，字典序即等级序）；ability: P5~P8（研判口径）
# score: composite_score 0-100，与 level 大致同向
# ---------------------------------------------------------------------------
# 字段：name, gender, phone, email, school, major, degree, years, title, company,
#       skills(list), work(3-4条str), project(2条str), summary, level, ability, score, edu_year
SEEDS = [
    # ---- 1 HR 专员（2 条） ----
    dict(name="苏雅", gender="女", phone="13800002001", email="suya@example.com",
         school="华东师范大学", major="人力资源管理", degree="本科", years=8,
         title="资深HR主管", company="方舟人力集团",
         skills=["招聘配置", "员工关系", "薪酬考勤核算", "绩效统计", "培训组织", "劳动法规", "Excel", "Word", "HR系统"],
         work=["2019-至今 方舟人力集团 资深HR主管：负责招聘配置与员工关系全流程，年度招聘到岗 60+ 人，核心岗位 30 天内到岗率 90%；主导薪酬考勤核算与绩效统计，准确率 100%。",
               "2016-2019 云帆网络 HR专员：负责培训组织与入离职办理，处理劳动纠纷 10+ 起零仲裁，熟悉劳动法规应用。"],
         project=["主导搭建公司 HR 数据看板，用 Excel 数据透视实现人员编制、流失率、到岗时效的月度分析，供管理层决策。",
                  "设计并落地新员工 90 天培养计划，覆盖招聘→入职→培训→转正全链路，试用期通过率提升至 95%。"],
         summary="8 年人力资源全模块经验，招聘配置与员工关系扎实，熟悉劳动法与 HR 系统，沟通协调与数据能力并重，责任心强。",
         level="A", ability="P7 高级", score=82, edu_year="2012"),
    dict(name="唐欣", gender="女", phone="13800002002", email="tangxin@example.com",
         school="华南师范大学", major="工商管理", degree="本科", years=5,
         title="HR专员", company="悦动出行科技",
         skills=["招聘", "员工关系", "考勤", "薪酬核算", "劳动法基础", "Excel", "PPT", "绩效统计", "培训支持"],
         work=["2021-至今 悦动出行科技 HR专员：独立负责一线岗位招聘与考勤薪酬核算，月处理入离职 15+ 人，招聘达成率 85%。",
               "2019-2021 盛泰信息 人事助理：协助员工关系与培训组织，维护 HR 系统数据准确率 99%。"],
         project=["上线考勤异常自动预警表，每月节省 HR 核对工时 8 小时；配合搭建校招面试流程文档库。"],
         summary="5 年 HR 执行经验，招聘与员工服务扎实，办公软件熟练，学习能力强，适合独立承接模块化 HR 事务。",
         level="B", ability="P6 中级", score=74, edu_year="2017"),
    # ---- 2 运维工程师（2 条） ----
    dict(name="孟川", gender="男", phone="13800002003", email="mengchuan@example.com",
         school="北京邮电大学", major="网络工程", degree="本科", years=6,
         title="高级运维工程师", company="星辰云服务",
         skills=["Linux", "Shell", "Python", "Docker", "Kubernetes", "Prometheus", "Grafana", "CI/CD", "Jenkins", "Nginx", "故障排查", "安全加固", "容量规划"],
         work=["2020-至今 星辰云服务 高级运维工程师：负责 200+ 台云服务器与 Kubernetes 集群运维，Prometheus/Grafana 监控告警全覆盖，SLA 99.95%；维护 Jenkins CI/CD 流水线，发布效率提升 3 倍。",
               "2017-2020 蓝盾科技 运维工程师：负责 Linux 系统与 Nginx 网关运维、故障应急与安全加固，主导过 3 次大促扩容。"],
         project=["主导容器化改造：Docker+Kubernetes 承接全部核心服务，弹性伸缩秒级生效，故障自愈率 90%。",
                  "搭建监控告警体系：Prometheus + Grafana + Alertmanager 统一指标告警，MTTR 从 2h 降到 20min。"],
         summary="6 年运维经验，Linux/容器/监控/CI-CD 全栈熟练，擅长故障应急与容量规划，具备生产环境安全加固实战。",
         level="A", ability="P7 高级", score=85, edu_year="2016"),
    dict(name="白鹤", gender="男", phone="13800002004", email="baihe@example.com",
         school="杭州电子科技大学", major="计算机科学与技术", degree="本科", years=4,
         title="运维工程师", company="极光电商",
         skills=["Linux", "Shell", "Docker", "Kubernetes", "Prometheus", "Grafana", "CI/CD", "Python", "Nginx", "Redis", "故障排查"],
         work=["2022-至今 极光电商 运维工程师：负责电商集群日常运维与监控告警处理，日均处理告警 20+，容器化服务可用性 99.9%。",
               "2020-2022 睿云网络 运维助理：负责服务器巡检与基础脚本编写，参与 CI/CD 流水线建设。"],
         project=["优化 Kubernetes 调度与资源配额，月度云成本下降 18%；编写 Shell/Python 自动化巡检脚本 30+。"],
         summary="4 年 Linux/容器运维经验，监控与 CI/CD 熟练，故障响应快，能在高压下稳定执行生产变更。",
         level="B", ability="P6 中级", score=72, edu_year="2018"),
    # ---- 3 测试开发工程师（3 条） ----
    dict(name="江凯", gender="男", phone="13800002005", email="jiangkai@example.com",
         school="华中科技大学", major="软件工程", degree="硕士", years=5,
         title="测试开发工程师", company="拓扑软件",
         skills=["pytest", "Python", "Selenium", "JMeter", "接口测试", "性能测试", "MySQL", "自动化测试", "CI/CD", "质量门禁", "测试用例", "缺陷跟踪"],
         work=["2021-至今 拓扑软件 测试开发工程师：搭建 pytest+Selenium 自动化测试框架，覆盖核心业务用例 1200+，回归效率提升 60%；接口自动化接入 CI 质量门禁，漏测率下降 40%。",
               "2019-2021 恒通信息 测试工程师：负责功能/接口测试与缺陷跟踪，主导大版本发布前的性能压测（JMeter）。"],
         project=["设计接口自动化平台：pytest+requests+allure，对接 MySQL 数据校验，日跑 800+ 接口用例，全自动出报告。",
                  "性能专项：JMeter 压测下单链路，定位慢 SQL 与连接池瓶颈，推动优化后 P99 从 1.8s 降到 400ms。"],
         summary="5 年测试开发经验，自动化框架与性能压测扎实，Python/MySQL 熟练，能独立建设质量保障体系。",
         level="A", ability="P7 高级", score=83, edu_year="2017"),
    dict(name="温岚", gender="女", phone="13800002006", email="wenlan@example.com",
         school="武汉理工大学", major="软件工程", degree="本科", years=4,
         title="测试工程师", company="微澜科技",
         skills=["pytest", "Selenium", "接口测试", "Python", "MySQL", "测试用例", "缺陷跟踪", "JMeter", "Postman", "自动化测试"],
         work=["2022-至今 微澜科技 测试工程师：负责 Web 端功能与接口测试，编写 pytest 自动化用例 300+，接口覆盖率 70%。",
               "2020-2022 汇智软件 测试助理：手工测试与回归，负责缺陷生命周期管理。"],
         project=["主导移动端 App 核心链路自动化回归：Appium+Selenium 体系，发布前全回归从 1 天缩至 2 小时。"],
         summary="4 年测试经验，接口/自动化测试熟练，Python 与 SQL 基础扎实，用例设计细致，缺陷定位快。",
         level="B", ability="P6 中级", score=76, edu_year="2018"),
    dict(name="顾彬", gender="男", phone="13800002007", email="gubin@example.com",
         school="重庆邮电大学", major="计算机技术", degree="本科", years=3,
         title="自动化测试工程师", company="领航信息",
         skills=["pytest", "Selenium", "Python", "接口测试", "JMeter", "MySQL", "自动化", "缺陷跟踪", "Linux", "Git"],
         work=["2023-至今 领航信息 自动化测试工程师：维护 Web 自动化用例 200+，参与接口自动化从 0 到 1 建设。",
               "2022-2023 润和软件 QA：功能测试与缺陷管理，参与 CI 门禁脚本维护。"],
         project=["搭建轻量接口自动化回归集：pytest+requests 每日定时跑 150 用例，失败自动 @ 责任人。"],
         summary="3 年测试开发方向经验，自动化与接口测试熟练，Python 功底好，成长快、执行强。",
         level="C", ability="P6 中级", score=70, edu_year="2019"),
    # ---- 4 前端开发工程师（3 条） ----
    dict(name="纪泽宇", gender="男", phone="13800002008", email="jizeyu@example.com",
         school="东南大学", major="计算机科学与技术", degree="硕士", years=6,
         title="高级前端开发工程师", company="青藤数字",
         skills=["Vue3", "TypeScript", "Element Plus", "uni-app", "微信小程序", "Vite", "ES6", "Webpack", "HTTP", "响应式布局", "性能优化", "Node.js"],
         work=["2020-至今 青藤数字 高级前端工程师：主导管理端与 H5 前端架构，Vue3+TypeScript+Element Plus 组件库建设，页面性能 LCP 优化至 1.8s；负责微信小程序（uni-app）从 0 到 1 上线，DAU 10w+。",
               "2018-2020 乐智科技 前端工程师：负责 PC/移动端业务开发与公共组件沉淀，参与 Vite 工程化升级。"],
         project=["搭建前端工程化基座：Vite+TypeScript 模板、ESLint/Prettier 规范、按需路由分包，构建时长减少 45%。",
                  "小程序性能专项：分包预下载、骨架屏、列表虚拟化，首屏耗时从 3.2s 降到 1.5s。"],
         summary="6 年前端经验，Vue3/TypeScript/小程序/工程化全覆盖，注重性能与体验，能独立负责大型前端模块。",
         level="A", ability="P7 高级", score=84, edu_year="2016"),
    dict(name="罗雅", gender="女", phone="13800002009", email="luoya@example.com",
         school="南京邮电大学", major="软件工程", degree="本科", years=3,
         title="前端开发工程师", company="蔚蓝互联",
         skills=["Vue3", "JavaScript", "ES6", "Element Plus", "uni-app", "微信小程序", "HTML", "CSS", "Vite", "HTTP", "Axios", "响应式"],
         work=["2023-至今 蔚蓝互联 前端工程师：基于 Vue3+Element Plus 开发管理系统页面 20+，负责接口联调与交互优化。",
               "2022-2023 字节跳动实习转正 前端：参与 H5 活动页与组件开发。"],
         project=["开发 uni-app 跨端商城小程序：支付/订单/物流全流程，日活 2w+，crash 率低于 0.1%。"],
         summary="3 年前端经验，Vue3 生态熟练，小程序与 H5 双端可做，代码规范，交付质量稳定。",
         level="B", ability="P6 中级", score=74, edu_year="2019"),
    dict(name="齐晟", gender="男", phone="13800002010", email="qisheng@example.com",
         school="西安电子科技大学", major="计算机科学与技术", degree="本科", years=2,
         title="前端开发工程师", company="启明科技",
         skills=["Vue", "Vue3", "JavaScript", "ES6", "HTML", "CSS", "Element Plus", "Axios", "Vite", "uni-app", "小程序", "Git"],
         work=["2024-至今 启明科技 前端工程师：负责管理系统页面开发与公共组件编写，参与 uni-app 小程序迭代。",
               "2023-2024 云图网络 前端实习生：完成多个活动页面与可视化大屏。"],
         project=["参与低代码表单引擎开发：schema 驱动渲染，复用到 3 个后台项目，开发效率提升 40%。"],
         summary="2 年前端经验，Vue 全家桶熟练，小程序可独立开发，学习能力强，愿意承担挑战性任务。",
         level="C", ability="P5 初级", score=66, edu_year="2020"),
    # ---- 5 AIGC 内容设计师（2 条） ----
    dict(name="韩梦", gender="女", phone="13800002011", email="hanmeng@example.com",
         school="中国美术学院", major="视觉传达设计", degree="本科", years=4,
         title="AIGC 内容设计师", company="引力创意",
         skills=["Stable Diffusion", "Midjourney", "提示词工程", "Photoshop", "Figma", "海报设计", "插画", "UI设计", "LoRA", "ComfyUI", "风格库", "多模态素材管理"],
         work=["2022-至今 引力创意 AIGC 设计师：负责电商/品牌 AIGC 内容产出，SD/Midjourney 提示词工程化，搭建品牌风格 LoRA 12 套，海报/插画产能提升 5 倍；用 Photoshop/Figma 完成视觉物料与 UI 规范落地。",
               "2020-2022 未然设计 视觉设计师：负责品牌 VI 与海报插画设计，服务快消/3C 客户 10+。"],
         project=["建设 AIGC 素材工作流：ComfyUI 批量出图 + 风格库沉淀 + 人工精修，单月产出物料 800+ 张。",
                  "主导智能体多模态物料生产试点：文生图批量 banner 替换人工，成本下降 60%。"],
         summary="4 年视觉+AIGC 设计经验，提示词与模型生态熟练，审美在线，能搭建从出图到落地的 AIGC 内容管线。",
         level="A", ability="P7 高级", score=80, edu_year="2018"),
    dict(name="阮琳", gender="女", phone="13800002012", email="ruanlin@example.com",
         school="四川美术学院", major="视觉传达", degree="本科", years=3,
         title="视觉设计师", company="像素工场",
         skills=["Photoshop", "Figma", "Stable Diffusion", "Midjourney", "提示词", "海报", "插画", "UI", "配色", "排版"],
         work=["2023-至今 像素工场 视觉设计师：负责活动海报与社媒视觉，将 SD/Midjourney 融入日常产出，效率与创意并行。",
               "2022-2023 橙意互动 设计师：负责 UI 与插画延展。"],
         project=["沉淀部门 Midjourney 提示词库与视觉风格手册，新同学 1 周即可上手出图。"],
         summary="3 年设计经验，传统视觉功底扎实并积极拥抱 AIGC 工具，效率型选手，适合内容生产型团队。",
         level="B", ability="P6 中级", score=71, edu_year="2019"),
    # ---- 6 AI 架构师（3 条） ----
    dict(name="云深", gender="男", phone="13800002013", email="yunshen@example.com",
         school="清华大学", major="计算机科学与技术", degree="博士", years=10,
         title="AI 架构师", company="智源未来",
         skills=["Python", "LangChain", "LangGraph", "RAG", "Milvus", "向量数据库", "PyTorch", "Ollama", "Agent", "分布式系统", "微服务", "推理服务", "GPU", "大模型", "架构设计"],
         work=["2019-至今 智源未来 AI 架构师：主导企业级大模型平台架构，LangGraph 多 Agent 编排 + RAG 检索增强 + Milvus 向量检索全链路设计，支撑 10+ 业务线；设计 Ollama/GPU 推理服务与弹性调度，推理 QPS 提升 4 倍。",
               "2015-2019 云图 AI 高级算法工程师：负责推荐系统与深度学习模型上线，PyTorch 训练/推理体系从 0 到 1。"],
         project=["企业 RAG 知识库架构：多路召回 + 重排 + 引用溯源，回答准确率 92%，覆盖 500w+ 文档。",
                  "Agent 智能体平台：LangGraph 状态编排 + 工具调用 + 人工介入闭环，服务 3 个业务域日调用 50w 次。"],
         summary="10 年 AI 工程经验，大模型应用、RAG、向量库、Agent 编排架构能力突出，能整体把控 AI 平台从模型到落地的工程化。",
         level="S", ability="P8 专家", score=92, edu_year="2008"),
    dict(name="凌峰", gender="男", phone="13800002014", email="lingfeng@example.com",
         school="浙江大学", major="人工智能", degree="硕士", years=7,
         title="AI 架构师", company="昆仑智能",
         skills=["Python", "LangChain", "LangGraph", "RAG", "Milvus", "PyTorch", "Ollama", "Agent", "FastAPI", "Docker", "Kubernetes", "深度学习"],
         work=["2020-至今 昆仑智能 AI 架构师：负责 RAG 问答与 Agent 平台设计，LangChain/LangGraph 编排 + Milvus 向量检索 + Ollama 本地推理；设计 FastAPI 网关与容器化部署，支撑问答服务日请求 30w+。",
               "2017-2020 深度引擎 算法工程师：负责 NLP 模型训练与上线（PyTorch），主导文本分类与抽取服务。"],
         project=["私有化大模型问答平台：RAG + 重排 + 权限隔离，交付 5 家政企客户，平均准确率 88%。",
                  "LangGraph 多 Agent 业务流：意图路由 + 工具调用 + 状态持久化，落地 2 条业务闭环。"],
         summary="7 年算法与架构经验，RAG/向量库/Agent 全栈实践丰富，能带团队完成 AI 平台从方案到交付。",
         level="A", ability="P7 高级", score=86, edu_year="2015"),
    dict(name="邵逸", gender="男", phone="13800002015", email="shaoyi@example.com",
         school="哈尔滨工业大学", major="计算机技术", degree="硕士", years=6,
         title="后端架构工程师", company="图灵引擎",
         skills=["Python", "LangChain", "RAG", "Milvus", "FastAPI", "SQLAlchemy", "MySQL", "Redis", "Docker", "Kubernetes", "微服务", "分布式", "NLP"],
         work=["2021-至今 图灵引擎 架构工程师：负责大模型服务后端架构，LangChain RAG 链路 + Milvus 向量检索服务化，支撑 10 个知识库应用；FastAPI 微服务治理与 Kubernetes 部署，可用性 99.95%。",
               "2018-2021 海岳网络 后端工程师：负责分布式任务与消息系统，参与 MySQL/Redis 优化。"],
         project=["知识库检索服务中台：Milvus 向量 + BM25 混合召回 + 重排，P95 < 300ms，服务 8 条产品线。"],
         summary="6 年后端/AI 工程经验，RAG 与向量检索链路服务化扎实，具备分布式与容器化实操，能承担 AI 平台核心模块。",
         level="B", ability="P7 高级", score=79, edu_year="2016"),
    # ---- 7 AI 产品经理（2 条） ----
    dict(name="温书宁", gender="女", phone="13800002016", email="wenshuning@example.com",
         school="复旦大学", major="信息管理与信息系统", degree="硕士", years=5,
         title="AI 产品经理", company="矩阵智能",
         skills=["AI产品规划", "需求分析", "PRD", "智能体", "RAG问答", "数字人", "数据分析", "版本排期", "用户洞察", "跨团队协作", "竞品分析", "Axure"],
         work=["2021-至今 矩阵智能 AI 产品经理：负责企业智能体与 RAG 问答产品从 0 到 1，定义交互与评估指标，上线 6 个月服务 20+ 企业客户；主导数字人问答场景 PRD 与多轮迭代。",
               "2019-2021 风行信息 产品经理：负责 B 端数据产品，指标看板与报表体系。"],
         project=["智能客服 Agent 产品：从需求挖掘到上线 3 个月，转人工率下降 45%，沉淀评估集 2000+ 条。",
                  "定义大模型应用评估体系：准确率/拒答率/幻觉率北极星指标，驱动模型与 RAG 持续调优。"],
         summary="5 年 AI/B 端产品经验，懂技术（能写 SQL、看得懂 RAG 链路），用户与指标双驱动，推进力强。",
         level="A", ability="P7 高级", score=82, edu_year="2017"),
    dict(name="易安", gender="女", phone="13800002017", email="yian@example.com",
         school="中山大学", major="市场营销", degree="本科", years=4,
         title="产品经理", company="新维度科技",
         skills=["产品规划", "需求分析", "PRD", "数据分析", "用户研究", "智能体", "AI应用", "版本管理", "Axure", "SQL"],
         work=["2022-至今 新维度科技 产品经理：负责 AI 问答与智能体产品需求分析与迭代，独立撰写 PRD 与埋点方案，周版本节奏稳定。",
               "2020-2022 蜂巢电商 产品助理：负责后台与数据产品需求。"],
         project=["AI 招聘助手 MVP：从 0 到 1 定义候选人筛选问答场景，上线试用 300+ HR，留存 40%。"],
         summary="4 年产品经验，AI 应用方向转型积极，执行力强、数据意识好，能独立从调研到上线闭环。",
         level="B", ability="P6 中级", score=73, edu_year="2018"),
    # ---- 8 后端开发工程师（3 条） ----
    dict(name="程亦凡", gender="男", phone="13800002018", email="chengyifan@example.com",
         school="中国科学院大学", major="计算机应用技术", degree="硕士", years=7,
         title="高级后端开发工程师", company="磐石科技",
         skills=["Python", "FastAPI", "SQLAlchemy", "MySQL", "Redis", "Docker", "微服务", "RESTful API", "性能调优", "分布式", "消息队列", "Nginx", "系统设计"],
         work=["2019-至今 磐石科技 高级后端工程师：负责核心服务 FastAPI 架构与开发，SQLAlchemy 建模 + MySQL/Redis 缓存优化，接口 QPS 支撑 2w+；主导微服务拆分与 Docker 容器化部署，发布效率提升 70%。",
               "2017-2019 中科软智 后端工程师：负责订单与支付系统，Redis 分布式锁与消息队列实践。"],
         project=["交易链路性能专项：慢 SQL 改写 + 缓存分层 + 连接池调优，P99 从 900ms 降至 180ms，成本下降 25%。",
                  "微服务治理：RESTful API 网关 + 限流熔断 + 全链路日志，双 11 大促 0 事故。"],
         summary="7 年 Python 后端经验，FastAPI/SQLAlchemy/MySQL/Redis 深度实践，微服务与性能调优扎实，能扛核心系统。",
         level="S", ability="P8 专家", score=90, edu_year="2014"),
    dict(name="陆一鸣", gender="男", phone="13800002019", email="luyiming@example.com",
         school="电子科技大学", major="软件工程", degree="硕士", years=5,
         title="后端开发工程师", company="长风科技",
         skills=["Python", "FastAPI", "SQLAlchemy", "MySQL", "Redis", "Docker", "RESTful API", "Linux", "Git", "Celery", "单元测试", "性能优化"],
         work=["2021-至今 长风科技 后端工程师：负责业务 API 开发（FastAPI + SQLAlchemy），MySQL 索引与 Redis 缓存设计，单接口 QPS 3k+；参与 Docker 化部署与 CI 流水线建设。",
               "2019-2021 云帆互联 后端工程师：负责后台系统与数据报表接口，Python/Flask 转 FastAPI 技术栈升级主力。"],
         project=["订单中心重构：FastAPI 异步化 + Redis 缓存 + 事务边界收紧，吞吐提升 2.5 倍，可用性 99.99%。",
                  "数据报表微服务：SQLAlchemy 原生 SQL 优化大表查询，千亿数据量分钟级出报表。"],
         summary="5 年 Python 后端经验，FastAPI/SQLAlchemy 熟练，数据库与缓存功底扎实，代码质量高、测试意识强。",
         level="A", ability="P7 高级", score=85, edu_year="2017"),
    dict(name="伍洲", gender="男", phone="13800002020", email="wuzhou@example.com",
         school="深圳大学", major="计算机科学与技术", degree="本科", years=4,
         title="后端开发工程师", company="云启科技",
         skills=["Python", "FastAPI", "Flask", "SQLAlchemy", "MySQL", "Redis", "Docker", "RESTful API", "Linux", "Git", "Celery", "单元测试"],
         work=["2022-至今 云启科技 后端工程师：负责 RESTful API 开发与维护（Python/FastAPI），SQLAlchemy 模型设计与 MySQL 查询优化，参与 Redis 缓存与 Celery 异步任务建设。",
               "2020-2022 金桥软件 后端开发：负责后台管理系统接口与第三方对接。"],
         project=["营销活动接口服务：高并发接口限流与幂等设计，峰值 QPS 5000 稳定运行；推动接口单测覆盖到 60%。"],
         summary="4 年 Python 后端经验，FastAPI/SQLAlchemy/MySQL 实战扎实，工程规范好，能独立交付中型模块。",
         level="B", ability="P6 中级", score=75, edu_year="2018"),
]

EDU_YEAR_DESC = {  # 按毕业年份给教育经历文案（本科4年/硕士3年/博士5年简化）
}
def build_resume(s: dict) -> str:
    """把种子定义渲染成一段中文简历文本（供 ResumeUploadService 真实解析）。"""
    degree_year = s["edu_year"]
    grad = degree_year
    lines = []
    lines.append(f"个人简历")
    lines.append(f"姓名：{s['name']}")
    lines.append(f"性别：{s['gender']}")
    lines.append(f"手机：{s['phone']}")
    lines.append(f"邮箱：{s['email']}")
    lines.append(f"求职意向：{s['title']}")
    lines.append("")
    lines.append("教育背景")
    # 本科默认4年、硕士3年、博士5年（大致，供年份推算）
    dur = {"本科": 4, "硕士": 3, "博士": 5}.get(s["degree"], 4)
    ent = int(grad) - dur
    lines.append(f"{ent}.09-{grad}.06  {s['school']}  {s['major']}  {s['degree']}")
    lines.append("")
    lines.append("专业技能")
    lines.append("、".join(s["skills"]))
    lines.append("")
    lines.append("工作经历")
    for w in s["work"]:
        lines.append(f"- {w}")
    lines.append("")
    lines.append("项目经历")
    for p in s["project"]:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("自我评价")
    lines.append(s["summary"])
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, default=0, help="只处理第 N 条(1起)，排错用")
    args = ap.parse_args()

    from app.db.session import SessionLocal
    from app.services.resume_upload_service import ResumeUploadService

    targets = SEEDS
    if args.only:
        targets = [SEEDS[args.only - 1]]

    ok = fail = 0
    for i, s in enumerate(targets, 1):
        # 幂等：按 phone 查已存在则跳过（避免重复灌）
        from app.models.talent import Talent
        from sqlalchemy import select
        with SessionLocal() as db:
            dup = db.execute(select(Talent.id).where(Talent.phone == s["phone"])).scalar()
        if dup:
            print(f"[{i}/{len(SEEDS)}] {s['name']} phone={s['phone']} 已存在(talent={dup})，跳过")
            ok += 1
            continue

        text = build_resume(s)
        content = text.encode("utf-8")
        print(f"[{i}/{len(SEEDS)}] 解析入库: {s['name']} / {s['title']} / {len(text)}字符 ...")
        try:
            with SessionLocal() as db:
                talent, _duplicate = ResumeUploadService.handle(
                    db, content=content, filename=f"{s['name']}.txt", content_type="text/plain")
                tid = talent.id
                db.commit()
                db.refresh(talent)
            print(f"   -> talent_id={tid}（handle 全链完成）")
        except Exception as e:
            fail += 1
            print(f"   !! handle 失败: {type(e).__name__}: {e}")
            continue

        # 回写主档关键字段 + 研判字段（口径可控；handle 内 LLM 已写过 report，此处覆盖为种子口径）
        try:
            _apply_override(tid, s)
            print(f"   -> 主档字段 + 研判(level={s['level']}, ability={s['ability']}, composite={s['score']}) 回写完成")
            ok += 1
        except Exception as e:
            fail += 1
            print(f"   !! 回写失败: {type(e).__name__}: {e}")

        time.sleep(0.3)  # 轻微节流，避免连续 LLM 请求过载

    print(f"\n完成：成功 {ok} / 失败 {fail}")
    if ok and not args.only:
        print("下一步：python scripts/vectorize_talents.py --drop   # 重建人才向量（新数据入 Milvus）")


def _apply_override(tid: int, s: dict) -> None:
    """按种子口径覆写主档与报告字段（排序/展示依赖）。"""
    from app.db.session import SessionLocal
    from sqlalchemy import text as _t
    skills_txt = ", ".join(s["skills"])
    work_txt = "\n".join(s["work"])
    proj_txt = "\n".join(s["project"])
    with SessionLocal() as db:
        db.execute(_t("""UPDATE tal_talent SET
            name=:name, gender=:gender, degree=:degree, school=:school, major=:major,
            years_experience=:years, current_title=:title, current_company=:company,
            skills=:skills, work_experience=:work, project_experience=:proj,
            summary=:summary, level=:level, phone=:phone, email=:email, status=1
            WHERE id=:tid"""),
            {"name": s["name"], "gender": s["gender"], "degree": s["degree"],
             "school": s["school"], "major": s["major"], "years": s["years"],
             "title": s["title"], "company": s["company"], "skills": skills_txt,
             "work": work_txt, "proj": proj_txt, "summary": s["summary"],
             "level": s["level"], "phone": s["phone"], "email": s["email"], "tid": tid})
        # 研判报告字段覆盖（保留 LLM 生成的 parsed_json/summary_report 原文，仅纠正等级口径字段）
        db.execute(_t("""UPDATE tal_talent_report SET
            ability_level=:ability, composite_score=:score, potential=:pot,
            experience_summary=:exp
            WHERE talent_id=:tid"""),
            {"ability": s["ability"], "score": s["score"],
             "pot": "P8" if s["ability"] == "P8 专家" else ("P7" if "P7" in s["ability"] else ("P6" if "P6" in s["ability"] else "P5")),
             "exp": f"{s['years']} 年 {s['title']} 经验，深耕{_field(s)}，项目与技能与岗位要求高度匹配。",
             "tid": tid})
        db.commit()


def _field(s: dict) -> str:
    key = {"HR专员": "招聘配置/员工关系", "运维工程师": "云原生运维", "测试开发工程师": "自动化测试体系",
           "前端开发工程师": "Vue3 与小跨端开发", "AIGC 内容设计师": "AIGC 内容生产",
           "AI 架构师": "大模型应用与 RAG 架构", "AI 产品经理": "AI 产品规划",
           "后端开发工程师": "Python 后端工程"} 
    # 按 title 近似取领域描述
    for k, v in key.items():
        if k in (s["title"] or ""):
            return v
    return "相关领域"


if __name__ == "__main__":
    main()
