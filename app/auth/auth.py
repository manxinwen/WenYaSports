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


# ---------------------------------------------------------------------------
# 用户存储（Demo 级别：内存存储，重启后丢失）
# ---------------------------------------------------------------------------
# 注册用户存储: {username: {"user_id": str, "username": str, "password": str, "role": UserRole, "created_at": float}}
_registered_users: dict = {}


def _hash_password(password: str) -> str:
    """简单的密码哈希（Demo 级别）。"""
    return hashlib.sha256(password.encode()).hexdigest()


def register(username: str, password: str) -> AuthUser:
    """注册新用户。

    Args:
        username: 用户名（3-32 字符）
        password: 密码（至少 6 字符）

    Returns:
        注册成功的 AuthUser

    Raises:
        ValueError: 参数无效或用户名已存在
    """
    username = (username or "").strip()
    if not username:
        raise ValueError("用户名不能为空")
    if len(username) < 3:
        raise ValueError("用户名至少为 3 个字符")
    if len(username) > 32:
        raise ValueError("用户名不能超过 32 个字符")
    if not password or len(password) < 6:
        raise ValueError("密码至少为 6 个字符")

    # 保留管理员账号名
    if username == ADMIN_USERNAME:
        raise ValueError(f"用户名 '{ADMIN_USERNAME}' 已被保留")

    # 检查重复
    if username in _registered_users:
        raise ValueError("该用户名已被注册")

    user_id = f"user_{username}"
    _registered_users[username] = {
        "user_id": user_id,
        "username": username,
        "password": _hash_password(password),
        "role": UserRole.USER,
        "created_at": time.time(),
    }

    logger.info("新用户注册: username=%s, user_id=%s", username, user_id)

    return AuthUser(
        user_id=user_id,
        role=UserRole.USER,
        username=username,
    )


def list_registered_users() -> list:
    """获取已注册用户列表（不含密码）。"""
    return [
        {
            "user_id": u["user_id"],
            "username": u["username"],
            "role": u["role"].value,
            "created_at": u["created_at"],
        }
        for u in _registered_users.values()
    ]


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
    # 已注册用户：验证密码哈希
    stored = _registered_users.get(username)
    if stored:
        if stored["password"] == _hash_password(password):
            return AuthUser(
                user_id=stored["user_id"],
                role=stored["role"],
                username=stored["username"],
            )
        return None
    # 其他情况：接受任意非空用户名密码（Demo 级别，向后兼容）
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
