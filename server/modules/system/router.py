from fastapi import APIRouter
from fastapi.responses import JSONResponse
from modules.system.service import systemService
from config.logger import logger

router = APIRouter(tags=["system"])


@router.get("/health")
async def getHealthEndpoint():
    try:
        payload = await systemService.getHealth()
        statusCode = 200 if payload["status"] == "ok" else 503
        return JSONResponse(status_code=statusCode, content=payload)
    except Exception as e:
        logger.error(f"getHealthEndpoint failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )
