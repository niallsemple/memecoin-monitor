import importlib.util, json, os
sp = importlib.util.spec_from_file_location('live_trader', os.path.abspath('live_trader.py'))
lt = importlib.util.module_from_spec(sp)
sp.loader.exec_module(lt)
print(json.dumps(lt.exit_watch(), default=str))
