from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models.excel_file import ExcelFile
from app.models.permission import FilePermission
from app.models.user import User
from app.services.auth_service import decode_token
from app.services.collab import collab_manager

router = APIRouter()


@router.websocket("/ws/files/{file_id}")
async def collab_ws(
    websocket: WebSocket,
    file_id: int,
    token: str = Query(...),
):
    db = SessionLocal()
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=4001)
            return
        user = db.query(User).filter(
            User.id == int(payload["sub"]), User.is_active == True
        ).first()
        if not user:
            await websocket.close(code=4001)
            return
        if not db.query(ExcelFile).filter(ExcelFile.id == file_id).first():
            await websocket.close(code=4004)
            return
        if not user.is_admin:
            perm = db.query(FilePermission).filter(
                FilePermission.user_id == user.id,
                FilePermission.file_id == file_id,
            ).first()
            if not perm:
                await websocket.close(code=4003)
                return
        full_name = user.full_name
    finally:
        db.close()

    await collab_manager.connect(file_id, websocket, user.id, full_name)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "cell":
                await collab_manager.broadcast(file_id, websocket, {
                    "type": "cell",
                    "sheet": data.get("sheet"),
                    "row": data.get("row"),
                    "col": data.get("col"),
                    "value": data.get("value"),
                    "user": full_name,
                })
    except WebSocketDisconnect:
        await collab_manager.disconnect(file_id, websocket)
