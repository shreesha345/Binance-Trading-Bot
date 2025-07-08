from fastapi import FastAPI
from api.routes import router
import multiprocessing
import time
from utils.websocket_handler import websocket_runner
import uvicorn

app = FastAPI()
app.include_router(router)

ws_process = None
ws_stop_event = None

def start_bot():
    global ws_process, ws_stop_event
    if ws_process is None or not ws_process.is_alive():
        ws_stop_event = multiprocessing.Event()
        ws_process = multiprocessing.Process(target=websocket_runner, args=(ws_stop_event,))
        ws_process.start()
        return True
    return False

def stop_bot():
    global ws_process, ws_stop_event
    if ws_process is not None and ws_process.is_alive():
        if ws_stop_event is not None:
            ws_stop_event.set()
        ws_process.terminate()
        ws_process.join()
        ws_process = None
        ws_stop_event = None
        return True
    return False

def is_bot_running():
    global ws_process
    return ws_process is not None and ws_process.is_alive()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1, log_level="info")
