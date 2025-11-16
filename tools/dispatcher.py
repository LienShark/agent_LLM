# dispatcher.py
import json
from importlib.util import spec_from_file_location, module_from_spec

# 動態載入你的檔案（不改檔名）
def _load_module(path, mod_name):
    spec = spec_from_file_location(mod_name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_flights_mod = _load_module("tools/search_flights.py", "search_flights_mod")
_hotels_mod  = _load_module("tools/search_hotel.py", "search_hotel_mod")

# def call_tool(tool_name: str, args: dict):
#     if tool_name == "search_flights":
#         tool = getattr(_flights_mod, "search_flights")
#         # 你的工具若是 LangChain 的 @tool，通常有 .invoke(...)；若是一般函式就直接呼叫
#         fn = getattr(tool, "invoke", tool)
#         result = fn(args)
#         return json.loads(result) if isinstance(result, str) else result
#
#     if tool_name == "search_hotels":
#         tool = getattr(_hotels_mod, "search_hotels")
#         fn = getattr(tool, "invoke", tool)
#         result = fn(args)
#         return json.loads(result) if isinstance(result, str) else result
#
#     raise ValueError(f"Unknown tool {tool_name}")
# 在 dispatcher.py 中
def call_tool(tool_name: str, args: dict):
    print(f"調用工具: {tool_name}，參數: {args}")
    if tool_name == "search_flights":
        tool = getattr(_flights_mod, "search_flights")
        fn = getattr(tool, "invoke", tool)
        result = fn(args)
        print(f"search_flights 回傳: {result}")
        return json.loads(result) if isinstance(result, str) else result

    if tool_name == "search_hotels":
        tool = getattr(_hotels_mod, "search_hotels")
        fn = getattr(tool, "invoke", tool)
        result = fn(args)
        print(f"search_hotels 回傳: {result}")
        return json.loads(result) if isinstance(result, str) else result

    raise ValueError(f"Unknown tool {tool_name}")