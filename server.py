import os

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agents.coordinator import run_pipeline

app = FastAPI()


@app.post("/run")
async def run(body: dict):
    topic = body.get("topic")
    if not topic:
        return JSONResponse(status_code=400, content={"error": "topic is required"})

    try:
        result = await run_pipeline(topic)
        return result
    except Exception as err:
        print(err)
        return JSONResponse(
            status_code=500, content={"error": "pipeline failed", "detail": str(err)}
        )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"pipeline API running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
