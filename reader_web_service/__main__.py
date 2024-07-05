import asyncio
import logging
import os
from json import dumps
from pathlib import Path

import pyroscope
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from loguru import logger as _log
from notifiers.logging import NotificationHandler

from reader_web_service.read_by_firefox import read_by_firefox

NOTIFY_OPTIONS = {
    'from': os.environ["EMAIL_FROM"],
    'to': os.environ["EMAIL_FROM"],
    'username': Path('/run/secrets/EMAIL_USERNAME').read_text().strip(),
    'password': Path('/run/secrets/EMAIL_PASSWORD').read_text().strip(),
    'subject': 'FirefoxReaderWebService error',
    'host': 'smtp.office365.com',
    'port': 587,
    'ssl': False,
    'tls': True,
}

email_handler = NotificationHandler('email', defaults=NOTIFY_OPTIONS)
logging.basicConfig(handlers=[email_handler])
_log.add(email_handler, level='ERROR')

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
async def root(url, ):
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
