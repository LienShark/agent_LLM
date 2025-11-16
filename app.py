import streamlit as st
import json
from main import PlanningState, PlannerAgent  # 假設你的類別在這裡
import pandas as pd

# --- 網頁標題 ---
st.title("🤖 AI 旅遊行程規劃師")
st.caption("輸入您的需求，AI 將為您規劃行程")

# --- 步驟 1: 獲取使用者輸入 ---
default_query = "今年2025年的十月我想去東京，幫我找最便宜的五天四夜行程，我對動漫和美食有興趣。"
user_input = st.text_area("您的旅遊需求：", value=default_query, height=100)

# --- 步驟 2: 建立執行按鈕 ---
if st.button("開始規劃行程 🚀"):

    if not user_input:
        st.error("請輸入您的旅遊需求！")
    else:
        # --- 步驟 3: 執行你的 Python 邏輯 ---
        try:
            if "OPENAI_API_KEY" not in st.secrets:
                st.error("請在 Streamlit Cloud 的 secrets 中設定 OPENAI_API_KEY")
                st.stop()  # 停止執行

                # 從 secrets 獲取 API key
            api_key = st.secrets["OPENAI_API_KEY"]
            # 顯示載入動畫
            with st.spinner("AI 正在為您規劃中，請稍候..."):
                # 1. 初始化狀態
                state = PlanningState(user_query=user_input)

                # 2. 建立 Agent
                planner = PlannerAgent(api_key=api_key)

                # 3. 執行你的規劃流程
                updated_state = planner.generate_initial_plan(state)
                updated_state = planner.execute_plan(updated_state)
                updated_state = planner.optimize_itinerary(updated_state)

            # --- 步驟 4: 顯示結果 ---
            st.success("🎉 您的行程規劃完成！")

            # st.json() 會自動格式化 JSON
            st.subheader("規劃結果 (JSON):")
            st.json(updated_state.model_dump_json(indent=2))

            st.subheader("📅 您的專屬行程總覽")

            # 1. 獲取 Pydantic 模型中的 final_itinerary 字典
            final_data = updated_state.model_dump().get("final_itinerary", {})

            # 2. 檢查是否有錯誤
            if "error" in final_data:
                st.warning(f"行程規劃失敗: {final_data['error']}")

            # 3. 如果成功，才顯示表格
            elif "selected_date_range" in final_data:

                # 顯示基本資訊
                start = final_data['selected_date_range'].get('start_date', 'N/A')
                end = final_data['selected_date_range'].get('end_date', 'N/A')
                cost = final_data.get('total_cost', 'N/A')

                st.markdown(f"**🗓️ 日期:** {start} 至 {end}")
                st.markdown(f"**💸 預估最低總花費:** {cost}")

                # 顯示航班和飯店 (JSON 格式就很清楚了)
                st.markdown("---")
                st.markdown("#### ✈️ 航班資訊")
                st.json(final_data.get("flights", {}))

                st.markdown("#### 🏨 飯店資訊")
                st.json(final_data.get("hotel", {}))

                # 顯示行程 (表格)
                st.markdown("---")
                st.markdown("#### 🗺️ 每日行程規劃")

                itinerary_list = final_data.get("itinerary", [])

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

                    # 6. 重新命名欄位
                    df = df.rename(columns={"day": "天數", "activities": "活動內容"})

                    # 7. 顯示表格！
                    st.dataframe(df.set_index('天數'), use_container_width=True)

                else:
                    st.info("未產生每日行程。")

        except Exception as e:
            st.error(f"規劃過程中發生錯誤：{e}")

else:
    st.info("請在上方輸入框中描述您的需求，然後點擊按鈕。")