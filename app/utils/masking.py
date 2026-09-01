"""通用数据脱敏工具（I03 / 需求：证件号/电话/邮箱默认脱敏返回）。

二期业务域（B 人才档案、F 报表导出、Agent 日志）统一调用本模块，避免各自发明：
    - 手机号 138****5678（保留前3后4）
    - 邮箱   a***e@qq.com（保留首尾字符 + 域名）
    - 身份证 1101**********1234（保留前4后4）
    - 姓名   张**（保留首字）

约定：传入 None 原样返回；长度过短无法保留有效位的整体打码。
"""


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：保留前 3 后 4，中间打星。短号按位打码。"""
    if not phone:
        return phone
    phone = phone.strip()
    if len(phone) < 7:
        return "*" * len(phone)
    return f"{phone[:3]}{'*' * (len(phone) - 7)}{phone[-4:]}"


def mask_email(email: str | None) -> str | None:
    """邮箱脱敏：@ 前保留首尾字符，域名明文。非邮箱按字符串打码。"""
    if not email:
        return email
    email = email.strip()
    if "@" not in email:
        return mask_name(email)
    local, _, domain = email.partition("@")
    if not local:
        return email
    if len(local) == 1:
        return f"*@{domain}"
    return f"{local[0]}{'*' * max(1, len(local) - 2)}{local[-1]}@{domain}"


def mask_id_card(id_card: str | None) -> str | None:
    """证件号脱敏：保留前 4 后 4，中间打星。过短整体打码。"""
    if not id_card:
        return id_card
    id_card = id_card.strip()
    if len(id_card) <= 8:
        return "*" * len(id_card)
    return f"{id_card[:4]}{'*' * (len(id_card) - 8)}{id_card[-4:]}"


def mask_name(name: str | None) -> str | None:
    """姓名脱敏：保留首字，其余打星。"""
    if not name:
        return name
    name = name.strip()
    if len(name) <= 1:
        return "*"
    return f"{name[0]}{'*' * (len(name) - 1)}"
