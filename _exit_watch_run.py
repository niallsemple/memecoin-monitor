import importlib.util
import json
import sys

sp = importlib.util.spec_from_file_location('live_trader', 'live_trader.py')
lt = importlib.util.module_from_spec(sp)
sp.loader.exec_module(lt)
result = lt.exit_watch()
print(json.dumps(result, default=str))
