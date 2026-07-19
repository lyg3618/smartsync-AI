from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings
from app.database import get_pool
from app.security import hash_password, verify_and_upgrade_password, verify_password


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        return None
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    pool = await get_pool()
    user_record = None

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, username, name, role, hashed_password, COALESCE(email, '') FROM contacts WHERE username = %s LIMIT 1",
                (form.username,),
            )
            row = await cur.fetchone()
            if row:
                user_record = {
                    "id": row[0],
                    "username": row[1],
                    "name": row[2],
                    "role": row[3],
                    "hashed_password": row[4],
                    "email": row[5],
                }
                verified, upgraded_hash = verify_and_upgrade_password(form.password, user_record["hashed_password"])
                if not verified:
                    user_record = None
                elif upgraded_hash:
                    await cur.execute(
                        "UPDATE contacts SET hashed_password = %s WHERE id = %s",
                        (upgraded_hash, user_record["id"]),
                    )
                    await conn.commit()

    if not user_record:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(
        {"sub": user_record["username"], "name": user_record["name"], "role": user_record["role"]}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_record["id"],
            "username": user_record["username"],
            "name": user_record["name"],
            "role": user_record["role"],
            "email": user_record["email"],
        },
    }


@router.put("/password")
async def change_password(data: PasswordChange, current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="未授权")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT hashed_password FROM contacts WHERE username = %s LIMIT 1", (current_user["sub"],))
            row = await cur.fetchone()
            if not row or not verify_password(data.old_password, row[0]):
                raise HTTPException(status_code=400, detail="旧密码不正确")

            new_hash = hash_password(data.new_password)
            await cur.execute("UPDATE contacts SET hashed_password = %s WHERE username = %s", (new_hash, current_user["sub"]))
            await conn.commit()

    return {"message": "密码修改成功"}
