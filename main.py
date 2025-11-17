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
        """
        (這是修改後的函數)
        使用 LLM 分析「已被 Python 選出的最佳選項」，並發揮創意生成最終行程。
        LLM 不再需要計算成本，專注於創意和總結。
        """
        print("\n--- LLM 正在分析最佳選項並發揮創意... ---")

        # 檢查 Python 計算步驟是否成功
        if "error" in current_state.final_itinerary:
            print(f"--- 由於計算錯誤，跳過創意優化: {current_state.final_itinerary['error']} ---")
            # 狀態已經包含錯誤，直接回傳
            return current_state

        # 提取景點資訊
        # (修正) 確保 "東京" 這個 key 存在，如果不存在則給一個空列表
        attractions_results = current_state.search_results.get("東京", [])
        anime_spots = []
        food_spots = []
        for res in attractions_results:
            if res["tool"] == "search_attractions" and "result" in res:
                if res["params"].get("interest") == "動漫":
                    anime_spots.extend(res["result"])
                elif res["params"].get("interest") == "美食":
                    food_spots.extend(res["result"])

        # 準備傳給 LLM 的資料
        input_data = {
            "user_query": current_state.user_query,
            "best_option_details": current_state.final_itinerary,
            "cost_analysis_summary": current_state.constraints.get("cost_analysis", []),
            "anime_spots": [f"{spot.get('title')}: {spot.get('snippet')}" for spot in anime_spots[:5]],
            "food_spots": [f"{spot.get('title')}: {spot.get('snippet')}" for spot in food_spots[:5]],
        }

        # --- ***【錯誤修正】*** ---
        # 1. 將 "human" 訊息改為 placeholder "{input_json}"
        # 2. 將 system prompt 中所有範例的 {var} 改為 {{var}} 來跳脫
        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一位頂級的東京旅遊規劃師，風格風趣且貼心。
                    你的任務不是計算價格（Python 已經算好了），而是將「數據」轉化為「美好的回憶」。

                    **你的輸入資料包含：**
                    1.  `user_query`: 使用者的原始需求 (例如：他對什麼感興趣)。
                    2.  `best_option_details`: Python 幫你算出的「CP值最高」的機票和飯店。
                    3.  `cost_analysis_summary`: (選用) 其他日期的價格，讓你知道這個選項有多划算。
                    4.  `anime_spots`: 動漫景點列表。
                    5.  `food_spots`: 美食景點列表。

                    **你的工作：**
                    1.  **總結與確認**：以熱情的口吻告訴使用者，你已經幫他找到了最划算的日期，並簡要總結航班和飯店 (例如：飯店的特色、評分)。
                    2.  **創意行程**：根據使用者的興趣 (例如 `user_query` 提到的動漫、美食)，將 `anime_spots` 和 `food_spots` 融合到一個五天四夜的行程中。
                    3.  **主題包裝**：如果使用者提到特定興趣 (如動漫)，嘗試規劃一個「主題日」，例如「秋葉原動漫聖地巡禮日」。
                    4.  **動態應變**：(如果 `best_option_details` 中有 `error` 欄位) 程式在抓取資料時出錯了，你需要安撫使用者，並根據現有資訊提供替代方案 (例如：建議手動查詢 Airbnb，或更換景點)。

                    **輸出格式：** 必須是純 JSON 格式，不含任何 Markdown。
                    {{
                        "title": "為你量身打造的東京五天四夜之旅！",
                        "summary": "（你對這個行程的總結，例如：我幫你找到了 12/18 出發的最棒組合，住在超方便的新宿，總花費才 TWD XXXXX！）",
                        "chosen_option": {{
                            "date_range": "YYYY-MM-DD 至 YYYY-MM-DD",
                            "total_cost": 12345,
                            "flight": "（航班資訊，例如：搭乘 華航 CI100 前往成田）",
                            "hotel": "（飯店資訊，例如：入住 新宿格拉斯麗飯店，評分 4.5/5，哥吉拉在等你！）」"
                        }},
                        "itinerary": [
                            {{"day": 1, "theme": "抵達與探索", "activities": ["搭乘 {{flight}} 抵達東京", "入住 {{hotel}}", "晚餐：{{food_spot}}"]}},
                            {{"day": 2, "theme": "動漫聖地巡禮", "activities": ["上午：{{anime_spot_1}}", "下午：{{anime_spot_2}}", "晚餐：{{food_spot}}"]}},
                            {{"day": 3, "theme": "美食與文化", "activities": ["上午：{{spot_3}}", "下午：{{spot_4}}", "晚餐：{{food_spot}}"]}},
                            {{"day": 4, "theme": "...待定...", "activities": ["..."]}},
                            {{"day": 5, "theme": "伴手禮與返程", "activities": ["..."]}}
                        ],
                        "tips": "（給予使用者一些貼心提醒）"
                    }}
                    """
                ),
                # 1. (修正) 這裡使用 placeholder
                ("human", "{input_json}"),
            ]
        )
        # --- ***【修正結束】*** ---

        chain = prompt_template | self.llm | StrOutputParser()

        # 2. (修正) 將 input_data 透過 'input_json' 傳入 invoke
        response_str = chain.invoke({
            "input_json": json.dumps(input_data, ensure_ascii=False)
        })

        print(f"--- LLM 創意行程回應 (原始): ---\n{response_str}")

        # --- 使用你強大的 JSON 提取方法 ---
        json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if not json_match:
            print(f"--- LLM 回應中找不到 JSON 區塊 ---")
            current_state.final_itinerary["error_message"] = "LLM 創意規劃失敗"
            return current_state

        response_str = json_match.group(0)
        # --- JSON 提取結束 ---

        try:
            # 將 LLM 的創意行程 (JSON) 與 Python 的計算結果 (Dict) 合併
            creative_itinerary = json.loads(response_str)

            # 我們保留 Python 算出來的精確數字，但用 LLM 的創意包裝
            # 將 creative_itinerary 的內容更新回 current_state.final_itinerary
            # 注意：current_state.final_itinerary 已經被 find_best_option 填入基礎資料

            current_state.final_itinerary["creative_plan"] = creative_itinerary
            current_state.global_score = current_state.final_itinerary.get("total_cost")  # 確保分數仍然是 Python 算的

            print(f"--- 成功生成最終創意行程 ---")
        except json.JSONDecodeError as e:
            print(f"--- LLM 行程優化回應格式錯誤: {e} ---")
            current_state.final_itinerary["error_message"] = "無法解析 LLM 創意行程"

        return current_state

    # def optimize_itinerary(self, current_state: PlanningState) -> PlanningState:
    #     """使用 LLM 分析搜尋結果，選擇總成本最低的行程，並生成最終行程計劃"""
    #     prompt_template = ChatPromptTemplate.from_messages(
    #         [
    #             (
    #                 "system",
    #                 """你是一位頂級的行程規劃師，任務是分析多個日期範圍的航班和飯店搜尋結果，選擇總成本（航班+飯店）最低的行程，並生成最終行程計劃，包含航班、飯店和動漫/美食景點建議。
    #
    #                 **輸入資料**：
    #                 {search_results}
    #
    #                 **要求**：
    #                 1. 計算每個日期範圍的總成本（航班價格 + 飯店價格 * 4晚）。
    #                 2. 選擇總成本最低的日期範圍。
    #                 3. 使用動漫和美食景點建議，生成一個五天四夜的行程計劃（每天包含合理的數個活動，不會太少也不至於太趕）。
    #                 4. 回傳 JSON 格式的最終行程計劃：
    #                 {{
    #                     "selected_date_range": {{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}},
    #                     "total_cost": float,
    #                     "flights": {{...}},
    #                     "hotel": {{...}},
    #                     "itinerary": [
    #                         {{"day": 1, "activities": ["活動1", "活動2"]}},
    #                         ...
    #                     ]
    #                 }}
    #                 5.簡單說一下每一個時間段的最小花費，讓使用者明白為何選擇當前的行程
    #
    #                 **注意**：
    #                 - 如果某個日期範圍缺少航班或飯店資料，跳過該範圍。
    #                 - 航班價格取最低價格，飯店價格取最低價格（每晚）。
    #                 - 動漫和美食景點從 search_attractions 結果中選擇。
    #                 - 你的回答必須是純 JSON 格式，不包含任何額外的文字或 Markdown 標記。
    #                 """,
    #             ),
    #         ]
    #     )
    #
    #     chain = prompt_template | self.llm | StrOutputParser()
    #
    #     print("--- LLM 正在分析搜尋結果並優化行程... ---")
    #
    #     response_str = chain.invoke({
    #         "search_results": json.dumps(current_state.search_results, ensure_ascii=False)
    #     })
    #
    #     print(f"--- LLM 優化行程回應 (原始): ---\n{response_str}")
    #
    #     # --- ***【強力修改】*** ---
    #     # 舊的清理方法 (太弱):
    #     # response_str = re.sub(r'^```json\n|\n```$', '', response_str).strip()
    #
    #     # 新的提取方法 (更強大):
    #     # 尋找從第一個 '{' 到最後一個 '}' 的所有內容
    #     json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
    #
    #     if not json_match:
    #         print(f"--- LLM 回應中找不到 JSON 區塊 ---")
    #         current_state.final_itinerary = {"error": "LLM 回應中找不到 JSON 區塊"}
    #         return current_state
    #
    #     response_str = json_match.group(0)
    #     print(f"--- 提取到的 JSON 字串: ---\n{response_str}")
    #     # --- ***【修改結束】*** ---
    #
    #     try:
    #         final_itinerary = json.loads(response_str)
    #         current_state.final_itinerary = final_itinerary
    #         current_state.global_score = final_itinerary.get("total_cost")
    #         print(f"--- 成功生成最終行程: {final_itinerary} ---")
    #     except json.JSONDecodeError as e:
    #         print(f"--- LLM 行程優化回應格式錯誤: {e} ---")
    #         current_state.final_itinerary = {"error": "無法解析行程優化結果"}
    #
    #     return current_state


    def find_best_option(self, current_state: PlanningState) -> PlanningState:
        """
        (這是我們新增的 Python 函數)
        分析 search_results，以程式碼精確計算出成本最低的選項。
        """
        print("\n--- 正在用 Python 程式碼分析最佳選項... ---")

        results_by_date = current_state.search_results
        cost_analysis = []  # 儲存每個日期的分析結果

        cheapest_option = None
        min_total_cost = float('inf')

        # 遍歷所有被搜尋過的日期 (例如 '2025-12-01', '2025-12-06'...)
        for date_key, results in results_by_date.items():

            # 確保這是個日期，而不是 "東京" (景點搜尋的 key)
            if not re.match(r'\d{4}-\d{2}-\d{2}', date_key):
                continue

            try:
                # 1. 找到該日期的航班
                flight_result = next((r for r in results if r["tool"] == "search_flights" and "result" in r), None)
                if not flight_result or not flight_result["result"]:
                    print(f"--- 日期 {date_key}: 找不到航班資料，跳過 ---")
                    continue

                # 從航班結果中提取最低價 (假設 price 已經是 TWD)
                # 你的 search_flights.py 裡 price 可能是 None，我們要處理這個
                valid_prices = [f.get("price") for f in flight_result["result"] if f.get("price") is not None]
                if not valid_prices:
                    print(f"--- 日期 {date_key}: 航班資料中無有效價格，跳過 ---")
                    continue

                cheapest_flight_price = min(valid_prices)
                cheapest_flight_data = next(
                    f for f in flight_result["result"] if f.get("price") == cheapest_flight_price)

                # 2. 找到該日期的飯店
                hotel_result = next((r for r in results if r["tool"] == "search_hotels" and "result" in r), None)
                if not hotel_result or not hotel_result["result"]:
                    print(f"--- 日期 {date_key}: 找不到飯店資料，跳過 ---")
                    continue

                # 從飯店結果中提取最低價 (假設是 "per night" 價格)
                # 你的 search_hotel.py 裡 price 可能是 "-"，我們要處理
                valid_hotel_prices = [h.get("price") for h in hotel_result["result"] if
                                      isinstance(h.get("price"), (int, float))]
                if not valid_hotel_prices:
                    print(f"--- 日期 {date_key}: 飯店資料中無有效價格，跳過 ---")
                    continue

                cheapest_hotel_price_per_night = min(valid_hotel_prices)
                cheapest_hotel_data = next(
                    h for h in hotel_result["result"] if h.get("price") == cheapest_hotel_price_per_night)

                # 3. 計算總成本 (假設是五天四夜 = 4 晚)
                total_hotel_cost = cheapest_hotel_price_per_night * 4
                total_cost = cheapest_flight_price + total_hotel_cost

                analysis = {
                    "date_range": f"{date_key} 至 {hotel_result['params']['checkout_date']}",
                    "flight": cheapest_flight_data,
                    "hotel": cheapest_hotel_data,
                    "total_cost": total_cost,
                    "cost_breakdown": f"航班 TWD {cheapest_flight_price} + 飯店 TWD {cheapest_hotel_price_per_night} x 4晚"
                }
                cost_analysis.append(analysis)

                # 4. 更新最低成本選項
                if total_cost < min_total_cost:
                    min_total_cost = total_cost
                    cheapest_option = analysis

            except Exception as e:
                print(f"--- 分析日期 {date_key} 時發生錯誤: {e} ---")

        if cheapest_option:
            print(
                f"--- Python 分析完成：最低成本選項為 {cheapest_option['date_range']}，總價 TWD {cheapest_option['total_cost']} ---")

            # 將最佳選項和完整的成本分析儲存到狀態中
            current_state.final_itinerary = cheapest_option  # 預先填入最佳選項
            current_state.global_score = cheapest_option["total_cost"]
            # 我們也把完整的分析存起來，也許 LLM 會用到
            current_state.constraints["cost_analysis"] = cost_analysis
        else:
            print("--- Python 分析完成：找不到任何有效的行程選項 ---")
            current_state.final_itinerary = {"error": "找不到有效的航班和飯店組合"}

        return current_state

    # ... (這是你原來的 optimize_itinerary 函數) ...


# if __name__ == '__main__':
#     state = PlanningState(
#         user_query="今年2025年的十二月我想去東京，幫我找最便宜的五天四夜行程，我對動漫和美食有興趣。"
#     )
#     from dotenv import load_dotenv
#
#     print("--- 執行本地測試 (main.py) ---")
#
#     load_dotenv()  # 讀取你本地的 .env 檔案
#
#     # 從環境變數讀取 API key
#     local_api_key = os.environ.get("OPENAI_API_KEY")
#     planner = PlannerAgent(api_key=local_api_key)
#     updated_state = planner.generate_initial_plan(state)
#     updated_state = planner.execute_plan(updated_state)
#     updated_state = planner.optimize_itinerary(updated_state)
#
#     # 檢視最終狀態
#     print("\n--- 最終更新後的狀態 ---")
#     print(updated_state.model_dump_json(indent=2))
if __name__ == '__main__':
    state = PlanningState(
        user_query="今年2025年的十二月我想去東京，幫我找最便宜的五天四夜行程，我對動漫和美食有興趣。"
    )
    from dotenv import load_dotenv

    print("--- 執行本地測試 (main.py) ---")

    load_dotenv()  # 讀取你本地的 .env 檔案

    # 從環境變數讀取 API key
    local_api_key = os.environ.get("OPENAI_API_KEY")
    planner = PlannerAgent(api_key=local_api_key)

    # 步驟 1: LLM 產生工具呼叫計畫
    updated_state = planner.generate_initial_plan(state)

    # 步驟 2: Python 執行工具 (呼叫 API)
    updated_state = planner.execute_plan(updated_state)

    # *** 步驟 3: (新!) Python 執行精確計算 ***
    updated_state = planner.find_best_option(updated_state)

    # 步驟 4: LLM 發揮創意，規劃行程
    updated_state = planner.optimize_itinerary(updated_state)

    # 檢視最終狀態
    print("\n--- 最終更新後的狀態 ---")
    # 為了方便閱讀，我們只印出 final_itinerary
    # print(updated_state.model_dump_json(indent=2))
    print(json.dumps(updated_state.final_itinerary, indent=2, ensure_ascii=False))