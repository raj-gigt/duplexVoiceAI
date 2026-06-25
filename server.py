from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config import AppConfig
from session import SessionFactory

config = AppConfig.from_env()
factory = SessionFactory(config)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/voice")
async def voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = factory.create_session(websocket)
    await session.run()
