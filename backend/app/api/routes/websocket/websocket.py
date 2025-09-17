from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Cookie,
    WebSocketException,
    status,
)
from typing import Any, Annotated
from app.api.deps import get_db, SessionDep
from fastapi.responses import HTMLResponse
from datetime import timezone
import jwt
from jwt.exceptions import InvalidTokenError
from app.core import security
from app.core.config import settings
from pydantic import ValidationError
from app.models import TokenPayload, User

router = APIRouter(
    prefix="/ws", tags=["ws"]  # type:ignore
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if not user_id in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        # print()
        # print("connect")
        # print(self.active_connections)
        # print()
        # print()

    def disconnect(self, websocket: WebSocket, user_id: int):
        # print()
        # print("disconnect BEFORE")
        # print(self.active_connections)
        # print()
        # print()

        self.active_connections[user_id].remove(websocket)
        if len(self.active_connections[user_id]) == 0:
            del self.active_connections[user_id]
        # print()
        # print("disconnect AFTER")
        # print(self.active_connections)
        # print()
        # print()

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_json(self, json: dict[str, Any], websocket: WebSocket):
        await websocket.send_json(json)

    async def broadcast(self, message: str):
        for user_id, list_of_connections in self.active_connections.items():
            for user_connection in list_of_connections:
                await user_connection.send_text(message)

    async def send_text_by_user_ids(self, message: str, user_ids: list[int]):
        for user_id in user_ids:
            if user_id in self.active_connections:
                for user_connection in self.active_connections[user_id]:
                    await user_connection.send_text(message)

    async def send_json_by_user_ids(self, json: dict[str, Any], user_ids: list[int]):
        sent_result = {}
        for user_id in user_ids:
            is_sent = False
            number_sent = 0
            if user_id in self.active_connections:
                for user_connection in self.active_connections[user_id]:
                    await user_connection.send_json(json)
                    is_sent = True
                    number_sent += 1
            sent_result[user_id] = {"is_sent": is_sent, "number_sent": number_sent}
        return sent_result

    async def send_json_to_one_user(self, json: dict[str, Any], user_id: int):
        is_sent = False
        number_sent = 0
        if user_id in self.active_connections:
            for user_connection in self.active_connections[user_id]:
                await user_connection.send_json(json)
                is_sent = True
                number_sent += 1
        return is_sent, number_sent


manager = ConnectionManager()


# @router.websocket("/ws")
# async def websocket_endpoint1(websocket: WebSocket):

#     await websocket.accept()
#     while True:
#         data = await websocket.receive_text()
#         await websocket.send_text(f"Message text was: {data}")


# @router.post("/test-delete-me-later")
# def test(phone: TestBody):
#     return phone


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session: SessionDep,
):
    
    print()
    print()
    print()
    print("HERE!!!!")
    print()
    print()
    
    if not websocket.cookies:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Отсутствуют куки"
        )
    token = websocket.cookies.get("access_token")
    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Отсутствует access_token в куки",
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Пользователь не найден"
        )
    # if user.status_id != "active":
    #     raise WebSocketException(
    #         code=status.WS_1008_POLICY_VIOLATION, reason="Неактивный пользователь"
    #     )

    await manager.connect(websocket, user.id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.send_json({"user_id": str(user.id)}, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id=user.id)


@router.post("/test-broadcast-to-many-users")
async def test_broadcast_to_many_users(user_ids: list[int]):
    # await manager.broadcast("Hello!")
    sent_result = await manager.send_json_by_user_ids(
        {"name": "Fyo", "age": 22}, user_ids
    )
    return sent_result


@router.post("/test-broadcast-to-one-user")
async def test_broadcast_to_one_user(user_id: int):
    # await manager.broadcast("Hello!")
    is_sent, number_sent = await manager.send_json_to_one_user(
        {"name": "Fyo", "age": 22}, user_id
    )
    return {"is_sent": is_sent, "number_sent": number_sent}