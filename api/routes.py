from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from utils.logger import log_api
import logging

router = APIRouter()

class UvicornInterceptHandler(logging.Handler):
    def emit(self, record):
        from utils.logger import log_api
        try:
            msg = self.format(record)
            log_api(f"[uvicorn] {msg}")
        except Exception:
            pass

# Intercept uvicorn logs and store in api.log
logging.getLogger("uvicorn").addHandler(UvicornInterceptHandler())
logging.getLogger("uvicorn.error").addHandler(UvicornInterceptHandler())
logging.getLogger("uvicorn.access").addHandler(UvicornInterceptHandler())

class BotControlRequest(BaseModel):
    action: int  # 1 for start, 0 for stop

@router.post("/bot/control")
def control_bot(req: BotControlRequest):
    """
    Control the trading bot: 1=start, 0=stop
    """
    from main import start_bot, stop_bot
    if req.action == 1:
        started = start_bot()
        log_api("Bot start requested via API. Status: {}".format("started" if started else "already running"))
        return {"status": "started" if started else "already running"}
    elif req.action == 0:
        stopped = stop_bot()
        log_api("Bot stop requested via API. Status: {}".format("stopped" if stopped else "already stopped"))
        return {"status": "stopped" if stopped else "already stopped"}
    else:
        log_api("Invalid action requested via API: {}".format(req.action))
        return {"status": "invalid action"}

@router.get("/bot/status")
def bot_status():
    """
    Check if the trading bot is running
    """
    from main import is_bot_running
    running = is_bot_running()
    log_api("Bot status checked via API. Running: {}".format(running))
    return {"running": running}
