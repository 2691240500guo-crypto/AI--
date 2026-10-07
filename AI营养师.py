import json
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_ollama import OllamaLLM
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import tool



# 自定义工具类
class CustomTools:
    """自定义工具集合"""

    @tool
    def get_weather(city: str) -> str:
        """获取指定城市的天气信息"""
        # 这里使用模拟数据，实际应用中可以使用天气API
        weather_data = {
            "北京": "晴天，温度 25°C，湿度 40%",
            "上海": "多云，温度 28°C，湿度 60%",
            "广州": "阵雨，温度 30°C，湿度 80%",
            "深圳": "晴天，温度 32°C，湿度 55%",
            "杭州": "阴天，温度 26°C，湿度 65%"
        }

        if city in weather_data:
            return f"{city}的天气：{weather_data[city]}"
        else:
            return f"抱歉，没有找到{city}的天气信息"

    @tool
    def calculate_bmi(weight: float, height: float) -> str:
        """计算BMI指数"""
        height_m = height / 100  # 厘米转米
        bmi = weight / (height_m ** 2)

        if bmi < 18.5:
            category = "体重过轻"
        elif bmi < 24:
            category = "正常范围"
        elif bmi < 28:
            category = "体重过重"
        else:
            category = "肥胖"

        return f"您的BMI指数为 {bmi:.1f}，属于'{category}'范围。建议：{get_bmi_advice(category)}"

    @tool
    def get_current_time(timezone: str = "Asia/Shanghai") -> str:
        """获取当前时间"""
        now = datetime.now()
        if timezone == "Asia/Shanghai":
            return f"当前时间（北京时间）：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"
        else:
            return f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')} ({timezone})"

    @tool
    def search_knowledge(query: str) -> str:
        """搜索知识库信息（模拟）"""
        knowledge_base = {
            "python": "Python是一种高级编程语言，以简洁易读著称，广泛应用于Web开发、数据科学、人工智能等领域。",
            "机器学习": "机器学习是人工智能的一个分支，让计算机通过数据学习并改进性能，而无需显式编程。",
            "深度学习": "深度学习是机器学习的一个子集，使用多层神经网络来学习数据的复杂模式。",
            "大模型": "大语言模型是基于Transformer架构的AI模型，能够理解和生成人类语言，如GPT系列、LLaMA等。",
            "量化": "模型量化是通过降低数值精度来减少模型大小和加速推理的技术，包括INT8、INT4等量化方法。"
        }

        query_lower = query.lower()
        for key, value in knowledge_base.items():
            if key in query_lower:
                return value

        return f"关于'{query}'的信息：这是当前热门的技术话题，建议查阅相关文档获取详细信息。"

    @tool
    def nrs2002_assessment(age: int, bmi: float, weight_change: str = "", disease_condition: str = "") -> str:
        """NRS2002营养风险评估"""
        # 营养状况评分
        nutritional_score = 0
        if bmi < 18.5:
            nutritional_score = 3
        elif bmi < 20.5:
            nutritional_score = 1

        # 疾病严重度评分
        disease_score = 0
        if "重症" in disease_condition or "ICU" in disease_condition:
            disease_score = 3
        elif "中等" in disease_condition:
            disease_score = 2
        elif "轻度" in disease_condition:
            disease_score = 1

        # 年龄评分
        age_score = 1 if age >= 70 else 0

        # 总分
        total_score = nutritional_score + disease_score + age_score

        # 风险等级
        if total_score >= 3:
            risk_level = "高风险"
            recommendation = "需要立即进行营养干预，建议肠内营养支持"
        elif total_score >= 1:
            risk_level = "中风险"
            recommendation = "需要营养支持治疗，建议高蛋白高能量饮食"
        else:
            risk_level = "低风险"
            recommendation = "建议定期监测营养状况，保持均衡饮食"

        result = {
            "assessment": "NRS2002营养风险评估",
            "scores": {
                "营养状况评分": nutritional_score,
                "疾病严重度评分": disease_score,
                "年龄评分": age_score,
                "总分": total_score
            },
            "风险等级": risk_level,
            "建议": recommendation
        }

        return json.dumps(result, ensure_ascii=False, indent=2)


def get_bmi_advice(category: str) -> str:
    """根据BMI分类提供建议"""
    advice_map = {
        "体重过轻": "建议增加营养摄入，适当进行力量训练",
        "正常范围": "继续保持健康的生活习惯和均衡饮食",
        "体重过重": "建议控制饮食，增加有氧运动",
        "肥胖": "建议咨询营养师，制定科学的减重计划"
    }
    return advice_map.get(category, "请咨询专业医生")


# 手动工具调用处理器
class ManualToolHandler:
    """手动工具调用处理器 - 兼容 OllamaLLM"""

    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}

    def should_use_tool(self, user_input: str) -> tuple:
        """判断是否应该使用工具（修复：调整工具匹配顺序，具体工具优先）"""
        user_input_lower = user_input.lower()

        # 工具触发关键词（修复：将具体工具放在前面，避免被通用工具误匹配）
        tool_keywords = {
            "nrs2002_assessment": ["营养风险", "nrs2002", "营养评估", "营养筛查"],  # 具体工具优先
            "calculate_bmi": ["bmi", "体重指数", "身体质量指数"],  # 移除"体重""身高"，避免与营养评估冲突
            "get_weather": ["天气", "weather", "气候"],
            "get_current_time": ["时间", "几点", "现在", "当前时间", "time"],
            "search_knowledge": ["什么是", "介绍", "解释", "搜索", "知识", "定义"]  # 补充关键词
        }

        for tool_name, keywords in tool_keywords.items():
            for keyword in keywords:
                if keyword in user_input_lower and tool_name in self.tools:
                    return True, tool_name

        return False, None

    def extract_tool_parameters(self, tool_name: str, user_input: str) -> dict:
        """从用户输入中提取工具参数（修复：补充search_knowledge参数，优化nrs2002提取）"""
        user_input_lower = user_input.lower()
        user_input_raw = user_input  # 保留原始输入，避免小写丢失信息

        if tool_name == "get_weather":
            # 提取城市名
            cities = ["北京", "上海", "广州", "深圳", "杭州"]
            for city in cities:
                if city in user_input_raw:
                    return {"city": city}
            return {"city": "北京"}  # 默认城市

        elif tool_name == "calculate_bmi":
            # 提取体重和身高（优化：仅匹配明确的"体重X公斤"和"身高X厘米"）
            import re
            weight_match = re.search(r'(\d+(?:\.\d+)?)\s*公斤', user_input_raw)
            height_match = re.search(r'(\d+(?:\.\d+)?)\s*厘米', user_input_raw)

            if weight_match and height_match:
                return {
                    "weight": float(weight_match.group(1)),
                    "height": float(height_match.group(1))
                }
            return {"weight": 70.0, "height": 175.0}  # 默认值

        elif tool_name == "search_knowledge":
            # 修复：提取query参数（用户输入即为查询关键词，或提取核心问题）
            import re
            # 移除触发关键词（如"什么是""介绍"），提取核心查询内容
            patterns = [
                r'什么是(.*?)\?*',    # 匹配"什么是XX？"
                r'介绍一下(.*?)\?*',  # 匹配"介绍一下XX？"
                r'解释(.*?)\?*',      # 匹配"解释XX？"
                r'搜索(.*?)\?*',      # 匹配"搜索XX？"
                r'(.*?)是什么\?*'      # 匹配"XX是什么？"
            ]
            query = user_input_raw.strip()  # 默认用完整输入作为query
            for pattern in patterns:
                match = re.search(pattern, user_input_raw)
                if match and match.group(1).strip():
                    query = match.group(1).strip()
                    break
            return {"query": query}  # 确保返回必填的query参数

        elif tool_name == "nrs2002_assessment":
            # 优化：更精准提取年龄、BMI、体重变化、疾病情况
            import re
            # 提取年龄（匹配"X岁"）
            age_match = re.search(r'(\d+)\s*岁', user_input_raw)
            age = int(age_match.group(1)) if age_match else 30

            # 提取BMI（匹配"BMI X.X"或"BMI X"）
            bmi_match = re.search(r'bmi\s*(\d+(?:\.\d+)?)', user_input_lower)
            bmi = float(bmi_match.group(1)) if bmi_match else 22.0

            # 提取体重变化（匹配"体重下降X%"或"体重稳定"）
            weight_change = "体重稳定"
            if re.search(r'体重下降\s*(\d+%)', user_input_raw):
                weight_change = re.search(r'体重下降\s*(\d+%)', user_input_raw).group(0)
            elif "体重下降" in user_input_raw:
                weight_change = "体重下降（未明确比例）"

            # 提取疾病情况（匹配"糖尿病""高血压""重症""ICU"等）
            disease_condition = "无明确疾病"
            if "糖尿病" in user_input_raw:
                disease_condition = "慢性疾病（糖尿病）"
            elif "高血压" in user_input_raw:
                disease_condition = "慢性疾病（高血压）"
            elif "重症" in user_input_raw or "icu" in user_input_lower:
                disease_condition = "重症（ICU/重症监护）"
            elif "中等" in user_input_raw:
                disease_condition = "中等严重疾病"

            return {
                "age": age,
                "bmi": bmi,
                "weight_change": weight_change,
                "disease_condition": disease_condition
            }

        elif tool_name == "get_current_time":
            # 可选：提取时区（如"纽约时间"），无则用默认
            import re
            timezone_match = re.search(r'([^，。\s]+)时间', user_input_raw)
            if timezone_match:
                timezone_map = {
                    "纽约": "America/New_York",
                    "伦敦": "Europe/London",
                    "东京": "Asia/Tokyo"
                }
                timezone = timezone_map.get(timezone_match.group(1), "Asia/Shanghai")
                return {"timezone": timezone}
            return {}  # 无参数则用工具默认值

        return {}


# 多轮对话管理器
class MultiTurnConversationManager:
    """支持多轮对话和函数调用的对话管理器 - 修复版本"""

    def __init__(self, llm_model="qwen3:0.6b", system_message=None):
        self.llm = OllamaLLM(model=llm_model)
        self.store = {}
        self.system_message = system_message or """
        你是一个友好的AI助手，可以帮用户查询天气、计算BMI、获取时间、搜索知识，以及进行NRS2002营养风险评估。
        当用户的问题涉及到这些功能时，请使用相应的工具来获取准确信息。
        """

        # 初始化工具
        self.tools = [
            CustomTools.get_weather,
            CustomTools.calculate_bmi,
            CustomTools.get_current_time,
            CustomTools.search_knowledge,
            CustomTools.nrs2002_assessment
        ]

        # 初始化手动工具处理器
        self.tool_handler = ManualToolHandler(self.tools)

        # 创建提示模板
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_message),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        # 创建基础链
        self.chain = self.prompt | self.llm

        # 创建带历史的链
        self.conversation = RunnableWithMessageHistory(
            self.chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def get_session_history(self, session_id: str) -> ChatMessageHistory:
        """获取会话历史"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def chat(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """发送消息并获取回复（带手动工具调用）"""
        try:
            # 检查是否应该使用工具
            should_use_tool, tool_name = self.tool_handler.should_use_tool(message)

            if should_use_tool and tool_name in self.tool_handler.tools:
                # 提取参数并调用工具
                parameters = self.tool_handler.extract_tool_parameters(tool_name, message)
                tool = self.tool_handler.tools[tool_name]

                print(f"🔧 使用工具: {tool_name}, 参数: {parameters}")
                tool_result = tool.invoke(parameters)

                # 将工具结果整合到回复中
                final_response = f"{tool_result}\n\n（以上信息通过工具 {tool_name} 获取）"

                # 更新会话历史
                history = self.get_session_history(session_id)
                history.add_user_message(message)
                history.add_ai_message(final_response)

                return {
                    "success": True,
                    "response": final_response,
                    "tools_used": [tool_name],
                    "session_id": session_id
                }
            else:
                # 使用普通对话
                config = {"configurable": {"session_id": session_id}}
                response = self.conversation.invoke({"input": message}, config=config)

                return {
                    "success": True,
                    "response": response,
                    "tools_used": [],
                    "session_id": session_id
                }

        except Exception as e:
            error_msg = f"对话过程中出错: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "response": "抱歉，处理您的消息时出现了错误。",
                "error": str(e),
                "session_id": session_id
            }

    def clear_history(self, session_id: str = "default"):
        """清除会话历史"""
        if session_id in self.store:
            self.store[session_id].clear()
            print(f"已清除会话历史: {session_id}")

    def get_history(self, session_id: str = "default") -> List[Dict]:
        """获取会话历史"""
        if session_id in self.store:
            messages = []
            for msg in self.store[session_id].messages:
                messages.append({
                    "type": msg.type,
                    "content": msg.content
                })
            return messages
        return []

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return [tool.name for tool in self.tools]


# 演示函数
def demo_multi_turn_conversation():
    """演示多轮对话和函数调用"""
    print("🚀 启动多轮对话演示（支持函数调用）")
    print("=" * 60)

    # 创建对话管理器
    chat_manager = MultiTurnConversationManager(
        llm_model="qwen3:0.6b",
        system_message="你是一个智能助手，可以帮助用户完成各种任务。请根据用户需求提供准确信息。"
    )

    print("可用工具:", chat_manager.get_available_tools())
    print("\n开始对话:")

    session_id = "demo_session"

    # 演示对话流程
    demo_messages = [
        "今天北京天气怎么样？",
        "我的体重70公斤，身高175厘米，请帮我计算BMI",
        "什么是机器学习？",
        "我今年65岁，BMI 19.2，有糖尿病，请帮我做营养风险评估",
        "现在几点了？"
    ]

    for i, message in enumerate(demo_messages, 1):
        print(f"\n[{i}] 用户: {message}")
        result = chat_manager.chat(message, session_id)

        if result["success"]:
            print(f"AI: {result['response']}")
            if result["tools_used"]:
                print(f"使用的工具: {result['tools_used']}")
        else:
            print(f"错误: {result['error']}")

        print("-" * 50)


def interactive_conversation():
    """交互式对话模式"""
    chat_manager = MultiTurnConversationManager(
        llm_model="qwen3:0.6b",
        system_message="你是一个多功能的智能助手，可以帮助用户查询信息、进行计算和健康评估。"
    )

    print("🤖 智能助手已启动（支持函数调用）")
    print("我可以帮您：查询天气、计算BMI、获取时间、搜索知识、营养风险评估")
    print("输入'退出'结束对话，输入'历史'查看对话历史，输入'清除'清除历史")
    print("=" * 60)

    session_id = "interactive_session"

    while True:
        try:
            user_input = input("\n您: ").strip()

            if user_input.lower() in ['退出', 'exit', 'quit']:
                print("再见！")
                break

            elif user_input.lower() in ['历史', 'history']:
                # 显示对话历史
                history = chat_manager.get_history(session_id)
                print("\n对话历史:")
                for i, msg in enumerate(history, 1):
                    role = "用户" if msg["type"] == "human" else "AI"
                    print(f"{i}. {role}: {msg['content']}")

            elif user_input.lower() in ['清除', 'clear']:
                # 清除对话历史
                chat_manager.clear_history(session_id)
                print("对话历史已清除")

            elif user_input.lower() in ['工具', 'tools']:
                # 显示可用工具
                tools = chat_manager.get_available_tools()
                print("\n可用工具:")
                for tool in tools:
                    print(f"- {tool}")

            elif user_input:
                # 正常对话
                print("AI: 思考中...", end="")
                result = chat_manager.chat(user_input, session_id)
                print("\r" + " " * 20 + "\r", end="")  # 清除"思考中"提示

                if result["success"]:
                    print(f"AI: {result['response']}")
                    if result["tools_used"]:
                        print(f"[使用的工具: {', '.join(result['tools_used'])}]")
                else:
                    print(f"AI: {result['response']}")

            else:
                print("请输入有效内容")

        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")


def health_assessment_demo():
    """健康评估专项演示"""
    print("🏥 健康评估专项演示")
    print("=" * 60)

    chat_manager = MultiTurnConversationManager(
        llm_model="qwen3:0.6b",
        system_message="你是一个专业的健康助手，专门帮助用户进行健康评估和营养风险筛查。"
    )

    session_id = "health_session"

    health_scenarios = [
        "请帮我计算BMI，我体重65公斤，身高170厘米",
        "我今年45岁，BMI 22，最近体重稳定，请评估我的营养风险",
        "我爷爷72岁，BMI 17.5，有高血压，最近体重下降了8%，请评估营养风险",
        "糖尿病患者应该如何控制饮食？",
        "正常的BMI范围是多少？"
    ]

    for i, scenario in enumerate(health_scenarios, 1):
        print(f"\n[{i}] 场景: {scenario}")
        result = chat_manager.chat(scenario, session_id)

        if result["success"]:
            print(f"💡 回答: {result['response']}")
            if result["tools_used"]:
                print(f"🔧 使用的工具: {result['tools_used']}")
        print("-" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "demo":
            demo_multi_turn_conversation()
        elif sys.argv[1] == "health":
            health_assessment_demo()
        elif sys.argv[1] == "interactive":
            interactive_conversation()
        else:
            print("用法: python script.py [demo|health|interactive]")
    else:
        # 默认运行交互式模式
        interactive_conversation()