from __future__ import annotations


class XError(Exception):
    """Base error for X2Notion sync."""

    def __init__(self, message: str, code: str = "unknown_error") -> None:
        super().__init__(message)
        self.code = code


class XAuthError(XError):
    """Authentication or cookie failure."""

    def __init__(self, message: str = "X 登录状态失效，请更新凭据。") -> None:
        super().__init__(message, code="x_auth_required")


class XRateLimitError(XError):
    """Rate limit encountered."""

    def __init__(self, message: str = "X 访问频率受限，请稍后重试。") -> None:
        super().__init__(message, code="x_rate_limited")


class XSchemaError(XError):
    """Notion schema mismatch."""

    def __init__(self, message: str = "Notion 模板缺少必要属性。") -> None:
        super().__init__(message, code="notion_schema_mismatch")
