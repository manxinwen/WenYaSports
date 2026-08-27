"""认证与角色权限。

使用 HMAC-SHA256 实现简易 Token 认证，区分 admin / user 角色。
生产环境应替换为 JWT + 密码哈希，这里保持 Demo 级别的简洁实现。
"""

import hashlib
import hmac
import logging
import time
from enum import Enum
from typing import Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "wenyasports2024"

# Token 有效期（秒）
TOKEN_TTL = 3600  # 1 小时

# HMAC 密钥（生产环境应使用环境变量）
_SECRET_KEY = "wenyasports-secret-key-change-in-production"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class AuthUser:
    """认证后的用户信息。"""

    def __init__(self, user_id: str, role: UserRole, username: str = ""):
        self.user_id = user_id
        self.role = role
        self.username = username

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "role": self.role.value,
            "username": self.username,
            "is_admin": self.is_admin,
        }


def _sign(payload: str) -> str:
    """HMAC-SHA256 签名。"""
    return hmac.new(
        _SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_token(user: AuthUser) -> str:
    """为用户签发 Token。

    格式: {user_id}:{role}:{timestamp}:{signature}
    """
    timestamp = int(time.time())
    payload = f"{user.user_id}:{user.role.value}:{timestamp}"
    sig = _sign(payload)
    return f"{payload}:{sig}"


def verify_token(token: str) -> Optional[AuthUser]:
    """验证 Token 并返回用户信息。

    Returns:
        AuthUser or None（无效/过期）
    """
    if not token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None
        user_id, role_str, ts_str, sig = parts
        payload = f"{user_id}:{role_str}:{ts_str}"

        # 验证签名
        expected_sig = _sign(payload)
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # 验证有效期
        ts = int(ts_str)
        if time.time() - ts > TOKEN_TTL:
            return None

        role = UserRole(role_str)
        return AuthUser(user_id=user_id, role=role)
    except (ValueError, KeyError):
        return None


def authenticate(username: str, password: str) -> Optional[AuthUser]:
    """验证用户名密码，返回 AuthUser 或 None。"""
    if not username or not password:
        return None
    if username == ADMIN_USERNAME:
        if password == ADMIN_PASSWORD:
            return AuthUser(
                user_id="admin_001",
                role=UserRole.ADMIN,
                username=username,
            )
        # Admin 用户名但密码错误 → 直接拒绝
        return None
    # 普通用户：接受任意非空用户名密码（Demo 级别）
    return AuthUser(
        user_id=f"user_{username}",
        role=UserRole.USER,
        username=username,
    )


# ---------------------------------------------------------------------------
# FastAPI 依赖
# ---------------------------------------------------------------------------

def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthUser:
    """从 Authorization header 解析当前用户。"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
        )
    # 支持 "Bearer <token>" 和直接 token
    token = authorization.removeprefix("Bearer ").strip()
    user = verify_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )
    return user


def require_admin(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthUser:
    """要求当前用户为管理员。"""
    user = get_current_user(authorization=authorization)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


def require_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthUser:
    """要求已登录（管理员或普通用户均可）。"""
    user = get_current_user(authorization=authorization)
    return user
