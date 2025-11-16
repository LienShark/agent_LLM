import os
import json
import re
from typing import List, Dict
from datetime import datetime, timedelta

# LangChain 導入
from langchain_openai import ChatOpenAI
# from langchain.prompts import ChatPromptTemplate
# from langchain.schema.output_parser import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate       # <-- 修正
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import StructuredTool

# 導入你的工具
from tools.search_flights import search_flights
from tools.search_hotel import search_hotels
from tools.search_attractions import search_attractions

# 導入你的狀態模型
from state.model import PlanningState

# from dotenv import load_dotenv
# load_dotenv()

class PlannerAgent:
    def __init__(self, api_key: str , model_name: str = "gpt-4o"):
        self.llm = ChatOpenAI(api_key=api_key , model=model_name, temperature=0.0)
        # 包含景點搜尋工具
        self.tools = [search_flights, search_hotels, search_attractions]
        # 綁定工具到 LLM
        self.llm = self.llm.bind_tools(self.tools)
        self.available_tools = """
        - search_flights(departure_city: str, destination_city: str, departure_date: str, return_date: str = None): 搜尋航班資訊。departure_date 和 return_date 必須是 YYYY-MM-DD 格式，return_date 可選。
        - search_hotels(destination: str, checkin_date: str, checkout_date: str, sort_by: str = 'price', sort_order: str = 'asc'): 搜尋飯店資訊。checkin_date 和 checkout_date 必須是 YYYY-MM-DD 格式，sort_by 必須是 'price'、'rating' 或 'reviews'，sort_order 必須是 'asc' 或 'desc'。
        - search_attractions(destination: str, interest: str): 搜尋指定目的地的興趣相關景點（例如 '動漫' 或 '美食'）。
        """

    @staticmethod
    def is_valid_date(date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def generate_initial_plan(self, current_state: PlanningState) -> PlanningState:
        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一位頂級的問題解決專家和專案規劃師。
                    你的任務是根據使用者的請求，生成一個搜尋計劃，並執行任務。
                    你擁有以下工具可以使用：
                    {tools}

                    **重要規則**：
                    1. 每個工具的參數必須嚴格符合其定義的簽名和格式要求。
                    2. 日期參數（例如 departure_date, checkin_date, checkout_date）必須是有效的 YYYY-MM-DD 格式。
                    3. 使用者請求提到「某月份」，請在這個月份生成多個使用者要求的日期範圍（例如 要求九月份的五天四夜則有 2025-09-01 到 2025-09-05、2025-09-06 到 2025-09-10 等，最多 5 個範圍）。
                    4. 對於每個日期範圍，生成 search_flights 和 search_hotels 工具呼叫，確保 departure_date 等於 checkin_date，return_date 等於 checkout_date。
                    5. 為興趣生成 search_attractions 工具呼叫。
                    6. 確保計劃中的工具呼叫語法正確，例如：search_flights(departure_city="台北", destination_city="東京", departure_date="2025-09-01", return_date="2025-09-05")。
                    7. 你的回答必須是純 JSON 格式，不包含任何額外的文字或 Markdown 標記（例如 ```json 或 ```）。

                    JSON 格式必須是：
                    {{
                        "plan": ["工具呼叫1", "工具呼叫2", ...]
                    }}
                    """,
                ),
                ("human", "這是我的請求：{query}"),
            ]
        )

        chain = prompt_template | self.llm | StrOutputParser()

        print("--- Planner Agent 正在呼叫 LLM 進行思考... ---")

        response_str = chain.invoke({
            "tools": self.available_tools,
            "query": current_state.user_query
        })

        print(f"--- LLM 回應的原始字串: ---\n{response_str}")

        response_str = re.sub(r'^```json\n|\n```$', '', response_str).strip()

        try:
            response_json = json.loads(response_str)
            plan = response_json.get("plan", [])

            # 驗證計劃中的工具呼叫
            validated_plan = []
            for step in plan:
                if "search_flights" in step:
                    if "departure_date=" in step:
                        date_match = re.search(r'departure_date="(\d{4}-\d{2}-\d{2})"', step)
                        if not date_match or not self.is_valid_date(date_match.group(1)):
                            print(f"--- 無效的日期格式在 {step}，跳過此步驟 ---")
                            continue
                    if "return_date=" in step and "return_date=\"None\"" not in step:
                        date_match = re.search(r'return_date="(\d{4}-\d{2}-\d{2})"', step)
                        if not date_match or not self.is_valid_date(date_match.group(1)):
                            print(f"--- 無效的回程日期格式在 {step}，跳過此步驟 ---")
                            continue
                    validated_plan.append(step)
                elif "search_hotels" in step:
                    if "checkin_date=" in step and "checkout_date=" in step:
                        checkin_match = re.search(r'checkin_date="(\d{4}-\d{2}-\d{2})"', step)
                        checkout_match = re.search(r'checkout_date="(\d{4}-\d{2}-\d{2})"', step)
                        if not checkin_match or not checkout_match or not self.is_valid_date(checkin_match.group(1)) or not self.is_valid_date(checkout_match.group(1)):
                            print(f"--- 無效的日期格式在 {step}，跳過此步驟 ---")
                            continue
                        validated_plan.append(step)
                elif "search_attractions" in step:
                    validated_plan.append(step)
                else:
                    print(f"--- 未知工具呼叫: {step}，跳過此步驟 ---")

            current_state.current_plan = validated_plan
            print(f"--- 成功解析並更新計劃: {validated_plan} ---")
        except json.JSONDecodeError as e:
            print(f"--- LLM 回應格式錯誤，無法解析 JSON：{e}。將使用空計劃。 ---")
            current_state.current_plan = []

        return current_state

    def execute_plan(self, current_state: PlanningState) -> PlanningState:
        """執行生成的計劃，調用對應的工具"""
        print("\n--- 執行計劃 ---")
        execution_results = []

        for step in current_state.current_plan:
            print(f"執行步驟: {step}")
            try:
                # 解析工具名稱和參數
                tool_name = step.split("(")[0]
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if not tool:
                    print(f"--- 找不到工具 {tool_name}，跳過此步驟 ---")
                    continue

                # 提取參數
                param_str = step[step.find("(")+1:step.rfind(")")]
                params = {}
                for param in param_str.split(", "):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        # 移除引號並處理 None
                        value = value.strip('"')
                        if value == "None":
                            value = None
                        params[key] = value

                # 調用工具
                result = tool.invoke(params)
                execution_results.append({"tool": tool_name, "params": params, "result": json.loads(result) if isinstance(result, str) else result})
                print(f"--- 工具 {tool_name} 執行結果: {result} ---")
            except Exception as e:
                print(f"--- 執行 {step} 失敗: {str(e)} ---")
                execution_results.append({"tool": tool_name, "params": params, "error": str(e)})

        # 更新執行歷史
        current_state.execution_history = execution_results
        # 儲存搜尋結果，以日期為鍵
        current_state.search_results = {}
        for result in execution_results:
            if "result" in result:
                date_key = result["params"].get("departure_date") or result["params"].get("checkin_date") or result["params"].get("destination")
                if date_key not in current_state.search_results:
                    current_state.search_results[date_key] = []
                current_state.search_results[date_key].append(result)
        return current_state

    def optimize_itinerary(self, current_state: PlanningState) -> PlanningState:
        """使用 LLM 分析搜尋結果，選擇總成本最低的行程，並生成最終行程計劃"""
        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一位頂級的行程規劃師，任務是分析多個日期範圍的航班和飯店搜尋結果，選擇總成本（航班+飯店）最低的行程，並生成最終行程計劃，包含航班、飯店和動漫/美食景點建議。

                    **輸入資料**：
                    {search_results}

                    **要求**：
                    1. 計算每個日期範圍的總成本（航班價格 + 飯店價格 * 4晚）。
                    2. 選擇總成本最低的日期範圍。
                    3. 使用動漫和美食景點建議，生成一個五天四夜的行程計劃（每天包含合理的數個活動，不會太少也不至於太趕）。
                    4. 回傳 JSON 格式的最終行程計劃：
                    {{
                        "selected_date_range": {{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}},
                        "total_cost": float,
                        "flights": {{...}},
                        "hotel": {{...}},
                        "itinerary": [
                            {{"day": 1, "activities": ["活動1", "活動2"]}},
                            ...
                        ]
                    }}
                    5.簡單說一下每一個時間段的最小花費，讓使用者明白為何選擇當前的行程

                    **注意**：
                    - 如果某個日期範圍缺少航班或飯店資料，跳過該範圍。
                    - 航班價格取最低價格，飯店價格取最低價格（每晚）。
                    - 動漫和美食景點從 search_attractions 結果中選擇。
                    - 你的回答必須是純 JSON 格式，不包含任何額外的文字或 Markdown 標記。
                    """,
                ),
            ]
        )

        chain = prompt_template | self.llm | StrOutputParser()

        print("--- LLM 正在分析搜尋結果並優化行程... ---")

        response_str = chain.invoke({
            "search_results": json.dumps(current_state.search_results, ensure_ascii=False)
        })

        print(f"--- LLM 優化行程回應: ---\n{response_str}")

        # 清理 Markdown 標記
        response_str = re.sub(r'^```json\n|\n```$', '', response_str).strip()

        try:
            final_itinerary = json.loads(response_str)
            current_state.final_itinerary = final_itinerary
            current_state.global_score = final_itinerary.get("total_cost")
            print(f"--- 成功生成最終行程: {final_itinerary} ---")
        except json.JSONDecodeError as e:
            print(f"--- LLM 行程優化回應格式錯誤: {e} ---")
            current_state.final_itinerary = {"error": "無法解析行程優化結果"}

        return current_state


if __name__ == '__main__':
    state = PlanningState(
        user_query="今年2025年的十月我想去東京，幫我找最便宜的五天四夜行程，我對動漫和美食有興趣。"
    )
    planner = PlannerAgent()
    updated_state = planner.generate_initial_plan(state)
    updated_state = planner.execute_plan(updated_state)
    updated_state = planner.optimize_itinerary(updated_state)

    # 檢視最終狀態
    print("\n--- 最終更新後的狀態 ---")
    print(updated_state.model_dump_json(indent=2))
