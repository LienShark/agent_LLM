import os
import json
import requests
from datetime import datetime
from serpapi import GoogleSearch
from langchain.tools import tool
from pydantic import BaseModel, Field
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HotelSearchInput(BaseModel):
    destination: str = Field(description="目的地城市，例如 '東京'")
    checkin_date: str = Field(description="入住日期，格式為 YYYY-MM-DD")
    checkout_date: str = Field(description="退房日期，格式為 YYYY-MM-DD")
    sort_by: str = Field(default="price", description="排序欄位：'price'（價格）、'rating'（評分）、'reviews'（評論數）")
    sort_order: str = Field(default="asc", description="排序順序：'asc'（升序）或 'desc'（降序）")

@tool(args_schema=HotelSearchInput)
def search_hotels(destination: str, checkin_date: str, checkout_date: str, sort_by: str = "price", sort_order: str = "asc") -> str:
    """
    (真實工具) 根據目的地、入住和退房日期搜尋飯店資訊，並按指定欄位排序。
    日期格式必須是 YYYY-MM-DD。
    排序欄位：'price'（價格）、'rating'（評分）、'reviews'（評論數）。
    排序順序：'asc'（升序）或 'desc'（降序）。
    此工具會回傳一個包含前5個最相關飯店資訊的JSON字串。
    """
    logger.info(f"查詢 {destination} 的飯店（{checkin_date} 至 {checkout_date}），排序：{sort_by} ({sort_order})")

    # 檢查環境變數
    api_key = os.getenv("SERPAPI_API_KEY", "YOUR_SERPAPI_API_KEY")
    if api_key == "YOUR_SERPAPI_API_KEY":
        logger.error("⚠️ 請先設定 SERPAPI_API_KEY 在 .env 檔案")
        return json.dumps({"error": "⚠️ 請先設定 SERPAPI_API_KEY 在 .env 檔案"})

    # 驗證排序參數
    valid_sort_fields = {"price", "rating", "reviews"}
    if sort_by not in valid_sort_fields:
        logger.error(f"無效的排序欄位：{sort_by}，必須是 {valid_sort_fields}")
        return json.dumps({"error": f"無效的排序欄位：{sort_by}，必須是 {valid_sort_fields}"})
    if sort_order not in {"asc", "desc"}:
        logger.error(f"無效的排序順序：{sort_order}，必須是 'asc' 或 'desc'")
        return json.dumps({"error": f"無效的排序順序：{sort_order}，必須是 'asc' 或 'desc'"})

    # 日期驗證
    current_date = datetime.now()
    try:
        checkin_date_obj = datetime.strptime(checkin_date, "%Y-%m-%d")
        checkout_date_obj = datetime.strptime(checkout_date, "%Y-%m-%d")
        if checkin_date_obj < current_date or checkout_date_obj <= checkin_date_obj:
            logger.error("入住日期必須為未來，且退房日期必須晚於入住日期")
            return json.dumps({"error": "入住日期必須為未來，且退房日期必須晚於入住日期"})
    except ValueError:
        logger.error("日期格式必須為 YYYY-MM-DD")
        return json.dumps({"error": "日期格式必須為 YYYY-MM-DD"})

    # SerpApi 查詢參數
    params = {
        "engine": "google_hotels",
        "q": destination,
        "check_in_date": checkin_date,
        "check_out_date": checkout_date,
        "hl": "zh-tw",
        "gl": "tw",
        "adults": 1,
        "currency": "TWD",
        "api_key": api_key
    }

    try:
        # 發送 SerpApi 請求
        logger.info(f"發送 SerpApi 請求: https://serpapi.com/search with params {params}")
        search = GoogleSearch(params)
        results_data = search.get_dict()
        logger.info(f"SerpApi 回應: {json.dumps(results_data, indent=2)[:500]}...")

        # 檢查 API 回應中的錯誤
        if "error" in results_data:
            logger.error(f"API 錯誤: {results_data['error']}")
            return json.dumps({"error": f"API 錯誤: {results_data['error']}"})

        # 檢查是否有飯店資料
        if "properties" not in results_data or not results_data["properties"]:
            logger.warning(f"無飯店資料返回，params: {params}")
            return json.dumps({"error": f"在 {destination} 找不到符合日期的飯店資訊。"})

        # 處理飯店資料
        properties = results_data["properties"]

        # 動態排序
        def get_sort_key(prop):
            if sort_by == "price":
                value = prop.get("total_rate", {}).get("extracted_lowest", float("inf"))
            elif sort_by == "rating":
                value = prop.get("overall_rating", -float("inf"))
            else:  # reviews
                value = prop.get("reviews", -float("inf"))
            # 處理降序（最高到最低）或升序（最低到最高）
            return value if sort_order == "asc" else -value

        sorted_properties = sorted(properties, key=get_sort_key)[:5]

        # 格式化結果
        simplified_results = []
        for prop in sorted_properties:
            simplified_results.append({
                "name": prop.get("name", "-"),
                "price": prop.get("total_rate", {}).get("extracted_lowest", "-"),
                "rating": prop.get("overall_rating", "-"),
                "reviews": prop.get("reviews", "-"),
                "description": prop.get("description", "-"),
                "address": f"{prop.get('gps_coordinates', {}).get('latitude', '-')}, {prop.get('gps_coordinates', {}).get('longitude', '-')}"
            })

        return json.dumps(simplified_results, ensure_ascii=False)

    except requests.RequestException as e:
        logger.error(f"網路錯誤: {str(e)}")
        return json.dumps({"error": f"網路錯誤: {str(e)}"})
    except Exception as e:
        logger.error(f"未知錯誤: {str(e)}")
        return json.dumps({"error": f"未知錯誤: {str(e)}"})

def test_hotel_search():
    load_dotenv()  # 載入 .env 檔案中的 API Key

    # 測試不同排序情況
    test_cases = [
        {"destination": "東京", "checkin_date": "2025-10-20", "checkout_date": "2025-10-22", "sort_by": "price", "sort_order": "asc"},
        {"destination": "東京", "checkin_date": "2025-10-20", "checkout_date": "2025-10-22", "sort_by": "rating", "sort_order": "desc"},
        {"destination": "東京", "checkin_date": "2025-10-20", "checkout_date": "2025-10-22", "sort_by": "reviews", "sort_order": "desc"}
    ]

    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"=== 測試案例 {i}：東京飯店搜尋 ({test_case['checkin_date']} 至 {test_case['checkout_date']})，排序：{test_case['sort_by']} ({test_case['sort_order']}) ===")
        result = search_hotels.invoke(test_case)
        hotels = json.loads(result) if isinstance(result, str) else result
        if "error" in hotels:
            print(hotels["error"])
        else:
            for j, hotel in enumerate(hotels, 1):
                print(f"飯店 {j}: 名稱={hotel['name']}, 價格={hotel['price']}元, 評分={hotel['rating']}, 評論數={hotel['reviews']}, 描述={hotel['description']}, 地址={hotel['address']}")
        print()

def hotel_search(des="東京" , start_date="2025-10-08" , end_date="2025-10-12" , sort_by="price"):
    load_dotenv()
    case = {"destination": des, "checkin_date": start_date, "checkout_date": end_date, "sort_by": sort_by,"sort_order": "asc"}
    result = search_hotels.invoke(case)
    hotels = json.loads(result) if isinstance(result, str) else result
    if "error" in hotels:
        print(hotels["error"])
    else:
        for j, hotel in enumerate(hotels, 1):
            print(
                f"飯店 {j}: 名稱={hotel['name']}, 價格={hotel['price']}元, 評分={hotel['rating']}, 評論數={hotel['reviews']}, 描述={hotel['description']}, 地址={hotel['address']}")
    print()

if __name__ == "__main__":
    # test_hotel_search()
    hotel_search()