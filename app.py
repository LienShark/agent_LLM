import streamlit as st
import json
from main import PlanningState, PlannerAgent  # 假設你的類別在這裡

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
                planner = PlannerAgent()

                # 3. 執行你的規劃流程
                updated_state = planner.generate_initial_plan(state)
                updated_state = planner.execute_plan(updated_state)
                updated_state = planner.optimize_itinerary(updated_state)

            # --- 步驟 4: 顯示結果 ---
            st.success("🎉 您的行程規劃完成！")

            # st.json() 會自動格式化 JSON
            st.subheader("規劃結果 (JSON):")
            st.json(updated_state.model_dump_json(indent=2))

            # 你也可以解析 JSON 並用 Markdown 顯示，使其更美觀
            # data = updated_state.model_dump()
            # st.subheader("行程概覽:")
            # st.markdown(f"**目的地:** {data.get('destination')}")
            # st.markdown(f"**天數:** {data.get('days')}")
            # ... 等等

        except Exception as e:
            st.error(f"規劃過程中發生錯誤：{e}")

else:
    st.info("請在上方輸入框中描述您的需求，然後點擊按鈕。")