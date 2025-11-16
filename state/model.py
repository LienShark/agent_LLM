# from typing import List, Dict, Any, Optional
# from pydantic import BaseModel, Field, ValidationError
#
# class PlanningState(BaseModel):
#     user_query: str
#     constraints: Dict[str, Any] = Field(
#         default_factory=dict,
#         description="Key-value pairs of constraints extracted from the user query."
#     )
#     current_plan: List[str] = Field(
#         default_factory=list,
#         description="The sequence of actions the agent plans to take."
#     )
#     execution_history: List[Dict[str, Any]] = Field(
#         default_factory=list,
#         description="A log of executed actions and their outcomes."
#     )
#     global_score: Optional[float] = Field(
#         default=None,
#         description="The overall score of the current solution, used for optimization."
#     )
#
# if __name__ == "__main__":
#     try:
#         print("--- 1. 創建一個初始狀態 ---")
#         initial_state = PlanningState(
#             user_query="我想以最少的金錢在9月安排一個五天四夜的日本東京旅遊"
#         )
#         print(initial_state.model_dump_json(indent=2))
#
#         print("\n--- 2. Agent 開始工作，更新狀態 ---")
#         initial_state.constraints = {"max_budget": 40000, "duration_nights": 4, "month": 9}
#         initial_state.current_plan = ["extract_constraints", "search_flights"]
#         initial_state.execution_history.append(
#             {
#                 "step": "extract_constraints",
#                 "tool_used": "llm_parser",
#                 "result": {"max_budget": 40000, "duration_nights": 4, "month": 9}
#             }
#         )
#         initial_state.global_score = 50.0
#
#         print(initial_state.model_dump_json(indent=2))
#         print("\n--- 3. 嘗試賦予 global_score 一個錯誤的型別 ---")
#         try:
#             initial_state.global_score = "good"
#         except ValidationError as e:
#             print("Pydantic 成功攔截到錯誤！")
#             print(e)
#
#         print("\n--- 4. 賦予正確的型別 ---")
#         initial_state.global_score = 95.5
#         print(f"成功將分數更新為: {initial_state.global_score}")
#
#
#     except ValidationError as e:
#         print("創建初始狀態時發生錯誤：")
#         print(e)
from pydantic import BaseModel
from typing import List, Dict, Optional

class PlanningState(BaseModel):
    user_query: str
    constraints: Dict = {}
    current_plan: List[str] = []
    execution_history: List[Dict] = []
    global_score: Optional[float] = None
    search_results: Dict = {}  # 儲存多日期搜尋結果
    final_itinerary: Dict = {}  # 儲存最終選擇的行程