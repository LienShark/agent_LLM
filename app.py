import streamlit as st
import json
from main import PlanningState, PlannerAgent  # 假設你的類別在這裡
import pandas as pd

# --- 網頁標題 ---
st.set_page_config(page_title="🤖 AI 旅遊行程規劃師", layout="wide")
st.title("🤖 AI 旅遊行程規劃師")
st.caption("輸入您的需求，AI 將為您規劃出 CP 值最高的創意行程")

# --- 步驟 1: 獲取使用者輸入 ---
default_query = "今年2025年的十二月我想去東京，幫我找最便宜的五天四夜行程，我對動漫和美食有興趣。"
user_input = st.text_area("您的旅遊需求：", value=default_query, height=100)

# --- 步驟 2: 建立執行按鈕 ---
if st.button("開始規劃行程 🚀"):

    if not user_input:
        st.error("請輸入您的旅遊需求！")
    else:
        # --- 步驟 3: 執行你的 Python 邏輯 ---
        try:
            # (修正) 檢查 secrets 的方式
            if "OPENAI_API_KEY" not in st.secrets or not st.secrets["OPENAI_API_KEY"]:
                st.error("請在 Streamlit Cloud 的 secrets 中設定 OPENAI_API_KEY")
                st.stop()  # 停止執行

            # 從 secrets 獲取 API key
            api_key = st.secrets["OPENAI_API_KEY"]

            # 顯示載入動畫
            with st.spinner("AI 正在為您規劃中... (正在執行多日 API 查詢，請稍候 1-2 分鐘)"):
                # 1. 初始化狀態
                state = PlanningState(user_query=user_input)

                # 2. 建立 Agent
                planner = PlannerAgent(api_key=api_key)

                # 3. 執行你的規劃流程
                updated_state = planner.generate_initial_plan(state)
                updated_state = planner.execute_plan(updated_state)
                updated_state = planner.find_best_option(updated_state)
                updated_state = planner.optimize_itinerary(updated_state)

            # --- 步驟 4: 顯示結果 ---
            st.success("🎉 您的行程規劃完成！")

            st.subheader("📅 您的專屬行程總覽")

            # 1. 獲取 Pydantic 模型中的 final_itinerary 字典
            final_data = updated_state.model_dump().get("final_itinerary", {})

            # 2. 檢查是否有錯誤
            if "error" in final_data:
                st.warning(f"行程規劃失敗: {final_data['error']}")

            # 3. (修正) 檢查 'total_cost' (Python 算的) 和 'creative_plan' (LLM 算的)
            elif "total_cost" in final_data and "creative_plan" in final_data:

                # (修正) 從 creative_plan 中獲取 LLM 的總結
                creative_plan = final_data.get("creative_plan", {})
                st.header(creative_plan.get("title", "您的東京之旅"))
                st.markdown(f"### {creative_plan.get('summary', 'AI 規劃完成！')}")

                # 顯示基本資訊 (來自 Python 的精確計算)
                date_range = final_data.get('date_range', 'N/A')
                cost = final_data.get('total_cost', 'N/A')
                cost_breakdown = final_data.get('cost_breakdown', '')

                st.markdown(f"**🗓️ 最佳日期:** {date_range}")
                st.markdown(f"**💸 預估最低總花費:** `TWD {cost}`")
                st.caption(f"成本分析: {cost_breakdown}")

                col1, col2 = st.columns(2)

                with col1:
                    # 顯示航班和飯店 (來自 Python 的精確計算)
                    st.markdown("---")
                    st.markdown("#### ✈️ 航班資訊 (CP值最佳)")
                    # (修正) 應為 'flight' (單數)
                    st.json(final_data.get("flight", {}))

                with col2:
                    st.markdown("---")
                    st.markdown("#### 🏨 飯店資訊 (CP值最佳)")
                    st.json(final_data.get("hotel", {}))  # 'hotel' (單數) 是正確的

                # 顯示行程 (表格)
                st.markdown("---")
                st.markdown("#### 🗺️ 每日行程規劃")

                # *** --- 【關鍵修正】--- ***
                # (修正) 從 'creative_plan' 中提取 'itinerary'
                itinerary_list = creative_plan.get("itinerary", [])
                # *** --- 【修正完畢】--- ***

                if itinerary_list:
                    # 4. (關鍵) 將字典列表轉換為 Pandas DataFrame
                    df = pd.DataFrame(itinerary_list)


                    # 5. (可選) 格式化 'activities' 欄位，將列表變成多行文字
                    def format_activities(activities_list):
                        if isinstance(activities_list, list):
                            # 將 ["活動1", "活動2"] 變成 "• 活動1\n• 活動2"
                            return "\n".join([f"• {act}" for act in activities_list])
                        return str(activities_list)


                    df['activities'] = df['activities'].apply(format_activities)

                    # 6. (修正) 重新命名欄位，並包含 'theme'
                    if 'theme' in df.columns:
                        df = df.rename(columns={"day": "天數", "theme": "本日主題", "activities": "活動內容"})
                        # (修正) 設定索引，讓表格更乾淨
                        st.dataframe(df.set_index('天數'), use_container_width=True)
                    else:
                        # Fallback if theme is missing
                        df = df.rename(columns={"day": "天數", "activities": "活動內容"})
                        st.dataframe(df.set_index('天數'), use_container_width=True)

                else:
                    st.info("AI 未能產生每日行程。")

                # (新增) 顯示 LLM 的 Tips
                st.markdown("---")
                st.info(f"💡 AI 貼心提醒：\n{creative_plan.get('tips', '玩得開心！')}")

            else:
                st.error("規劃結果異常：缺少 'total_cost' 或 'creative_plan' 欄位。")
                st.json(final_data)  # 顯示原始資料以供除錯

        except Exception as e:
            st.error(f"規劃過程中發生嚴重錯誤：{e}")
            import traceback

            st.code(traceback.format_exc())  # 顯示詳細的錯誤堆疊

else:
    st.info("請在上方輸入框中描述您的需求，然後點擊按鈕。")