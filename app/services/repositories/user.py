from app.services.connections.mongodb import db
from app.models.user import UserDB

async def create_user(user: UserDB) -> None:
    await db.users.insert_one(user.model_dump())

async def get_user_by_username(username: str) -> dict | None:
    return await db.users.find_one({ "username": username }, {"_id": 0})