# tools_spec.py
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "搜尋航班",
            "parameters": {
                "type": "object",
                "properties": {
                    "departure_city": {"type": "string", "description": "出發城市（繁中，例如：台北）"},
                    "destination_city": {"type": "string", "description": "目的地城市（例如：東京）"},
                    "departure_date": {"type": "string", "description": "出發日期，YYYY-MM-DD"},
                    "return_date": {"type": "string", "description": "回程日期，YYYY-MM-DD"}
                },
                "required": ["departure_city","destination_city","departure_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "搜尋飯店",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "目的地城市（例如：東京）"},
                    "checkin_date": {"type": "string", "description": "入住日期，YYYY-MM-DD"},
                    "checkout_date": {"type": "string", "description": "退房日期，YYYY-MM-DD"},
                    "sort_by": {"type": "string", "enum": ["price","rating","distance"], "default": "price"},
                    "sort_order": {"type": "string", "enum": ["asc","desc"], "default": "asc"}
                },
                "required": ["destination","checkin_date","checkout_date"]
            }
        }
    }
]
