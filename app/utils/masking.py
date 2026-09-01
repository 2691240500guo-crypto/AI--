"""脱敏工具（I03）：对手机号/邮箱/证件号打码后再输出，避免敏感信息明文暴露。"""


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：保留前 3 位和后 4 位，中间打码。"""
    if not phone:  # 空值直接返回
        return phone
    return phone[:3] + "****" + phone[-4:]  # 中间四位打码


def mask_email(email: str | None) -> str | None:
    """邮箱脱敏：保留用户名首字母和域名，用户名其余部分打码。"""
    if not email or "@" not in email:  # 空值或格式异常
        return email
    name, domain = email.split("@", 1)  # 拆出用户名和域名
    masked_name = name[0] + "***"  # 用户名首字母保留，其余打码
    return masked_name + "@" + domain  # 拼回脱敏邮箱


def mask_id_card(id_card: str | None) -> str | None:
    """证件号脱敏：保留前 4 位和后 4 位，中间按长度打码。"""
    if not id_card:  # 空值直接返回
        return id_card
    if len(id_card) <= 8:  # 太短时整体打码
        return "****"
    stars = "*" * (len(id_card) - 8)  # 中间星号数量按剩余长度生成
    return id_card[:4] + stars + id_card[-4:]  # 拼接脱敏结果
