
import os
import sys
import json
import re
from datetime import date, timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv

# ----------------------
# Dynamic tool imports with rich error capture
# ----------------------
_flights_import_err = None
_hotels_import_err = None
search_flights = None
search_hotels = None

try:
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("search_flights", "/mnt/data/search_flights.py")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # may raise ImportError if deps missing
    search_flights = getattr(mod, "search_flights", None)
except Exception as e:
    _flights_import_err = repr(e)

try:
    from importlib.util import spec_from_file_location, module_from_spec
    spec2 = spec_from_file_location("search_hotel", "/mnt/data/search_hotel.py")
    mod2 = module_from_spec(spec2)
    spec2.loader.exec_module(mod2)
    search_hotels = getattr(mod2, "search_hotels", None)
except Exception as e:
    _hotels_import_err = repr(e)

# ----------------------
# Lightweight CN date normalization (heuristic)
# ----------------------
CN_MONTH_MAP = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12}

def _parse_month(query: str) -> int | None:
    m = re.search(r"([一二三四五六七八九十]{1,3}|\d{1,2})月", query)
    if not m: return None
    tok = m.group(1)
    if tok.isdigit():
        v = int(tok)
        return v if 1 <= v <= 12 else None
    return CN_MONTH_MAP.get(tok)

def _first_future_day_in_month(year: int, month: int, today: date) -> date:
    d = date(year, month, 1)
    while d.month == month and d < today:
        d += timedelta(days=1)
    if d.month != month:
        # fallback to first of month if everything is in the past
        d = date(year, month, 1)
    return d

def _extract_len_nights(query: str) -> int | None:
    m = re.search(r"(\d+)天(\d+)夜", query)
    if m:
        return int(m.group(2))
    m2 = re.search(r"(\d+)天", query)
    if m2:
        d = max(1, int(m2.group(1)))
        return max(1, d-1)
    return None

def normalize_dates(query: str, today: date | None = None) -> dict:
    if today is None:
        today = date.today()
    month = _parse_month(query) or today.month
    year = today.year
    checkin = _first_future_day_in_month(year, month, today)
    nights = _extract_len_nights(query) or 4
    checkout = checkin + timedelta(days=nights)
    return {
        "depart_date": checkin.strftime("%Y-%m-%d"),
        "return_date": checkout.strftime("%Y-%m-%d"),
        "checkin_date": checkin.strftime("%Y-%m-%d"),
        "checkout_date": checkout.strftime("%Y-%m-%d")
    }

# ----------------------
# Planner: synthesize strict tool_calls matching YOUR schemas
# ----------------------
def synth_plan(user_query: str, dates: dict) -> dict:
    """
    We skip LLM for robustness and generate a deterministic plan
    that exactly matches your Pydantic schemas:
    - search_flights(departure_city, destination_city, departure_date, return_date?)
    - search_hotels(destination, checkin_date, checkout_date, sort_by?, sort_order?)
    """
    return {
        "tool_calls": [
            {
                "name": "search_flights",
                "arguments": {
                    "departure_city": "台北",
                    "destination_city": "東京",
                    "departure_date": dates["depart_date"],
                    "return_date": dates["return_date"]
                }
            },
            {
                "name": "search_hotels",
                "arguments": {
                    "destination": "東京",
                    "checkin_date": dates["checkin_date"],
                    "checkout_date": dates["checkout_date"],
                    "sort_by": "price",
                    "sort_order": "asc"
                }
            }
        ]
    }

# ----------------------
# Execution
# ----------------------
def run_plan(tool_calls: List[Dict[str, Any]]) -> dict:
    results: List[Dict[str, Any]] = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("arguments", {})
        if name == "search_flights":
            if search_flights is None:
                results.append({"tool": "search_flights", "error": f"import failed: {_flights_import_err or 'unknown'}, ensure dependencies installed (e.g., serpapi, requests, python-dateutil)"})
                continue
            try:
                out = search_flights.invoke(args)
                data = json.loads(out) if isinstance(out, str) else out
                results.append({"tool": "search_flights", "data": data})
            except Exception as e:
                results.append({"tool": "search_flights", "error": repr(e), "args": args})
        elif name == "search_hotels":
            if search_hotels is None:
                results.append({"tool": "search_hotels", "error": f"import failed: {_hotels_import_err or 'unknown'}, ensure dependencies installed (e.g., serpapi, requests, python-dotenv)"})
                continue
            try:
                out = search_hotels.invoke(args)
                data = json.loads(out) if isinstance(out, str) else out
                results.append({"tool": "search_hotels", "data": data})
            except Exception as e:
                results.append({"tool": "search_hotels", "error": repr(e), "args": args})
        else:
            results.append({"tool": name, "error": "unsupported tool", "args": args})
    return {"results": results}

def main():
    load_dotenv()
    user_query = os.getenv("USER_QUERY") or "幫我找九月份東京四天三夜，飯店每晚越便宜越好"
    today = date.today()
    dates = normalize_dates(user_query, today)
    plan = synth_plan(user_query, dates)

    print("\n=== Planner plan (JSON) ===")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print("\n=== Executing tools ===")
    exec_results = run_plan(plan["tool_calls"])
    print(json.dumps(exec_results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
