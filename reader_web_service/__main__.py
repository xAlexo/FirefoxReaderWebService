import asyncio

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from reader_web_service.read_by_firefox import read_by_firefox

app = FastAPI()


@app.get("/")
async def root(url, ):
    loop = asyncio.get_running_loop()
    html = await loop.run_in_executor(None, read_by_firefox, url)
    return JSONResponse(content=jsonable_encoder({"html": html}))
