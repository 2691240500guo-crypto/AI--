# -*- coding: utf-8 -*-
"""统一日志系统（全局唯一出口）。

配置 root logger：让所有模块的 logging.getLogger("任意名") 都继承统一
handler（写文件 + 控制台），避免各模块各自输出、业务日志不进日志文件的问题。

用法：
    from app.utils.logger import logger
    logger.info("...") / logger.error("...")
"""
import logging
import sys
from pathlib import Path

# 日志固定写到项目根目录（基于本文件位置推算，与启动目录无关）
# 本文件位于 <root>/app/utils/logger.py，向上 3 层即项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_FILE = str(PROJECT_ROOT / "ai_talent.log")


def setup_logger(name: str = "ai_talent", log_file: str = DEFAULT_LOG_FILE):
    """
    配置日志系统（全局统一）

    Args:
        name: 兼容旧引用：返回该名字的 logger（自动继承 root 配置）
        log_file: 日志文件路径

    Returns:
        logging.Logger: 配置好的 logger 实例
    """
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # ===== 配置 root logger（全局统一出口） =====
    root = logging.getLogger()
    if not root.handlers:  # 避免重复添加
        root.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')  # 文件 handler
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler(sys.stdout)  # 控制台 handler
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    # ===== 压掉第三方库的 INFO 噪音（httpx/urllib3 的请求日志不进业务文件） =====
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ===== 兼容旧引用：返回 ai_talent logger（自动继承 root 的 handler） =====
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger


# 创建全局 logger 实例
logger = setup_logger()
