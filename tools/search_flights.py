import os
import json
import requests
from dateutil.parser import parse
from serpapi.google_search import GoogleSearch
from langchain.tools import tool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CITY_TO_AIRPORT_CODE = {
    "東京": "NRT",
    "大阪": "KIX",
    "台北": "TPE"
}

class FlightSearchInput(BaseModel):
    departure_city: str = Field(description="出發城市，例如 '台北'")
    destination_city: str = Field(description="目的地城市，例如 '東京'")
    departure_date: str = Field(description="出發日期，格式為 YYYY-MM-DD 或其他可解析格式")
    return_date: str = Field(description="回程日期，格式為 YYYY-MM-DD 或其他可解析格式，選填", default=None)

@tool(args_schema=FlightSearchInput)
def search_flights(departure_city: str, destination_city: str, departure_date: str, return_date: str = None) -> str:
    """
    根據出發城市、目的地城市、出發日期和回程日期（可選）搜尋航班資訊。
    日期格式應為 YYYY-MM-DD 或其他可解析格式。
    回傳包含前5個最相關航班資訊的JSON字串。
    """
    load_dotenv()
    logger.info(f"正在執行搜尋航班工具：從 {departure_city} 到 {destination_city}, 出發日期 {departure_date}, 回程日期 {return_date}")

    try:
        departure_date = parse(departure_date).strftime("%Y-%m-%d")
        if return_date:
            return_date = parse(return_date).strftime("%Y-%m-%d")
    except ValueError:
        return json.dumps({"error": "無法解析日期格式，請使用 YYYY-MM-DD 或其他有效格式"})

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return json.dumps({"error": "找不到 SERPAPI_API_KEY"})

    departure_id = CITY_TO_AIRPORT_CODE.get(departure_city, departure_city)
    arrival_id = CITY_TO_AIRPORT_CODE.get(destination_city, destination_city)

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": departure_date,
        #"outbound_time": departure_time,
        "return_date": return_date,
        #"return_time": retur_time,
        "api_key": api_key,
        "hl": "zh-tw",
        "type": "1" if return_date else "2" ,
        "bags":"1",
        #"carrier":carrier
    }
    if return_date:
        params["return_date"] = return_date

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        logger.debug(f"API 回傳結果: {json.dumps(results, ensure_ascii=False, indent=2)}")

        if "error" in results:
            return json.dumps({"error": f"API 錯誤: {results['error']}"})
        if "best_flights" not in results and "other_flights" not in results:
            return json.dumps({"error": f"找不到從 {departure_id} 到 {arrival_id} 在 {departure_date} 的航班資訊"})

        flights_to_process = (results.get("best_flights", []) + results.get("other_flights", []))[:5]

        simplified_results = []
        for flight in flights_to_process:
            flights = flight.get("flights") or []
            if not flights:
                flight_number = departure_time = arrival_time = airline = None
            else:
                seg0 = flights[0] or {}
                dep_airport = (seg0.get("departure_airport") or {})
                arr_airport = (seg0.get("arrival_airport") or {})

                flight_number = seg0.get("flight_number")
                airline = seg0.get("airline")  # 航空公司名稱
                departure_time = dep_airport.get("time")
                arrival_time = arr_airport.get("time")
            simplified_results.append({
                "airline": airline,
                "flight_number": flight_number,
                "price": flight.get("price")*30,
                "duration": flight.get("total_duration"),
                "stops": len(flight.get("layovers", [])),
                "departure_time": departure_time,
                "arrival_time": arrival_time
            })

        return json.dumps(simplified_results, ensure_ascii=False)

    except requests.RequestException as e:
        return json.dumps({"error": f"網路錯誤: {str(e)}"})
    except json.JSONDecodeError:
        return json.dumps({"error": "無法解析 API 回傳的 JSON 資料"})

from dotenv import load_dotenv
import json
from pprint import pprint

def test_flight_search():
    load_dotenv()

    print("=== 測試案例 1：單程航班（台北 -> 東京） ===")
    result = search_flights.run({"departure_city": "台北", "destination_city": "東京", "departure_date": "2025-10-20"})
    flights = json.loads(result) if isinstance(result, str) else result
    if "error" in flights:
        print(flights["error"])
    else:
        for i, flight in enumerate(flights, 1):
            print(f"航班 {i}: 航空公司={flight['airline']}, 航班號={flight['flight_number']}, 價格={flight['price']}元, 時間={flight['duration']}分鐘, 中轉={flight['stops']}, 出發={flight['departure_time']}, 抵達={flight['arrival_time']}")

    print("\n=== 測試案例 2：來回航班（台北 <-> 大阪） ===")
    result = search_flights.run({
        "departure_city": "台北",
        "destination_city": "大阪",
        "departure_date": "2025-10-20",
        "return_date": "2025-10-27"
    })
    flights = json.loads(result) if isinstance(result, str) else result
    if "error" in flights:
        print(flights["error"])
    else:
        for i, flight in enumerate(flights, 1):
            print(f"航班 {i}: 航空公司={flight['airline']}, 航班號={flight['flight_number']}, 價格={flight['price']}元, 時間={flight['duration']}分鐘, 中轉={flight['stops']}, 出發={flight['departure_time']}, 抵達={flight['arrival_time']}")

def flight_search(de_city="台北" , arr_city="東京" , de_date="2025-10-08" , re_date="2025-10-12"):
    load_dotenv()
    tool_input = {
        "departure_city": de_city,
        "destination_city": arr_city,
        "departure_date": de_date,
        "return_date": re_date
    }
    result = search_flights.invoke(tool_input)
    flights = json.loads(result) if isinstance(result, str) else result
    if "error" in flights:
        print(flights["error"])
    else:
        for i, flight in enumerate(flights, 1):
            print(f"航班 {i}: 航空公司={flight['airline']}, 航班號={flight['flight_number']}, 價格={flight['price']}元, 時間={flight['duration']}分鐘, 中轉={flight['stops']}, 出發={flight['departure_time']}, 抵達={flight['arrival_time']}")


if __name__ == "__main__":
    flight_search()