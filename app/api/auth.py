from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError
from app.models.user import UserCreate, UserResponse, UserDB
from app.core.security import get_password_hash, verify_password, create_access_token
from app.services.repositories.user import create_user, get_user_by_username
from app.models.token import Token
from typing import Annotated
from app.core.security import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    hashed = get_password_hash(user.password)
    user_db = UserDB(username=user.username, email=user.email, 
                    hashed_password=hashed)

    try:
        await create_user(user_db)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username has already been taken")
    return user_db

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user is not authorized")
    token = create_access_token({ "sub": user["username"] })
    return Token(access_token=token, token_type="bearer")

@router.get("/account", response_model=UserResponse)
async def read_current_user(current_user: Annotated[dict, Depends(get_current_user)]):
    return current_user
