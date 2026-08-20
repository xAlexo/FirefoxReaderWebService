import asyncio
import os
from json import dumps

import sentry_sdk
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger as _log

from reader_web_service.read_by_firefox import read_by_firefox

sentry_sdk.init(os.environ["SENTRY_DSN"])

try:
    import pyroscope
    pyroscope.configure(
      application_name = "FirefoxReaderWebService",
      server_address   = "http://my-pyroscope-server:4040",
    )
except ImportError:
    pass

app = FastAPI()


@app.get("/ping")
async def ping():
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, read_by_firefox, 'https://example.com', False)
    if not data:
        return JSONResponse(content=jsonable_encoder({"status": "error"}), status_code=500)
    return {"status": "ok"}


@app.get("/")
async def root(url, ):
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, read_by_firefox, url)
    if not data:
        return JSONResponse(content=jsonable_encoder({
            "error": "reader not found",
        }), status_code=400)

    data_debug = dumps(
        data, indent=4, ensure_ascii=False, sort_keys=True, default=str)
    _log.debug(f'data: {data_debug}')
    return JSONResponse(content=jsonable_encoder({
        "title": data['title'],
        "html": data['content'],
    }))


@app.get("/ip")
async def ip():
    """Return the exit IP address Firefox uses (through Tor/proxy)."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, read_by_firefox, 'http://ifconfig.me/', False)
    if not data:
        return JSONResponse(content=jsonable_encoder({"error": "failed to get IP"}), status_code=500)
    # ifconfig.me returns the IP as the page body text
    ip = data['content'].strip()
    return {"ip": ip}


@app.get("/html")
async def html(url, ):
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, read_by_firefox, url, False)
    if not data:
        return JSONResponse(content=jsonable_encoder({
            "error": "reader not found",
        }), status_code=400)

    return JSONResponse(content=jsonable_encoder({
        "title": data['title'],
        "html": data['content'],
    }))
