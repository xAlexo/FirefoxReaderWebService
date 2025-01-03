import asyncio
import os
from json import dumps

import pyroscope
import sentry_sdk
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger as _log

from reader_web_service.read_by_firefox import read_by_firefox

sentry_sdk.init(os.environ["SENTRY_DSN"])

pyroscope.configure(
  application_name = "FirefoxReaderWebService",
  server_address   = "http://my-pyroscope-server:4040",
)

app = FastAPI()


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
