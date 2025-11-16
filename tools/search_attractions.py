import os
import json
import logging
from serpapi import GoogleSearch
from langchain.tools import tool
from pydantic import BaseModel, Field
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AttractionSearchInput(BaseModel):
    destination: str = Field(description="目的地城市，例如 '東京'")
    interest: str = Field(description="興趣類型，例如 '動漫' 或 '美食'")

@tool(args_schema=AttractionSearchInput)
def search_attractions(destination: str, interest: str) -> str:
    """
    搜尋指定目的地的興趣相關景點（例如動漫、美食）。
    回傳包含前5個景點資訊的JSON字串。
    """
    logger.info(f"搜尋 {destination} 的 {interest} 相關景點")

    # 檢查環境變數
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        logger.error("請先設定 SERPAPI_API_KEY 在 .env 檔案")
        return json.dumps({"error": "請先設定 SERPAPI_API_KEY 在 .env 檔案"})

    # SerpApi 查詢參數
    params = {
        "engine": "google",
        "q": f"{destination} {interest} 景點",
        "hl": "zh-tw",
        "gl": "tw",
        "api_key": api_key
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        logger.debug(f"API 回傳結果: {json.dumps(results, ensure_ascii=False, indent=2)[:500]}...")

        if "error" in results:
            logger.error(f"API 錯誤: {results['error']}")
            return json.dumps({"error": f"API 錯誤: {results['error']}"})

        # 提取景點資料
        organic_results = results.get("organic_results", [])[:5]
        if not organic_results:
            logger.warning(f"無 {interest} 相關景點資料返回，params: {params}")
            return json.dumps({"error": f"在 {destination} 找不到 {interest} 相關景點"})

        simplified_results = []
        for result in organic_results:
            simplified_results.append({
                "title": result.get("title", "-"),
                "link": result.get("link", "-"),
                "snippet": result.get("snippet", "-")
            })

        return json.dumps(simplified_results, ensure_ascii=False)

    except Exception as e:
        logger.error(f"搜尋景點失敗: {str(e)}")
        return json.dumps({"error": f"搜尋景點失敗: {str(e)}"})