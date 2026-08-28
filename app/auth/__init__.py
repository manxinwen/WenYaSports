"""认证与角色权限模块。

提供简单的基于 Token 的角色认证系统，区分管理员和普通用户。
管理员可管理知识库，普通用户只能使用运动分析和 AI 问答功能。
"""

from app.auth.auth import (
    UserRole,
    AuthUser,
    create_token,
    verify_token,
    get_current_user,
    require_admin,
    require_user,
    authenticate,
    register,
    list_registered_users,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)

__all__ = [
    "UserRole",
    "AuthUser",
    "create_token",
    "verify_token",
    "get_current_user",
    "require_admin",
    "require_user",
    "authenticate",
    "register",
    "list_registered_users",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
]
