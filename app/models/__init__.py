from app.models.user import User, UserRole
from app.models.role import Role, RoleMenu
from app.models.menu import Menu
from app.models.dept import Dept, Position
from app.models.dict_item import DictType, DictItem
from app.models.operation_log import OperationLog, LoginLog
from app.models.message import Message
from app.models.matching import PosPosition, MatchRule, MatchResult, MatchPushLog
from app.models.training import Course, Lesson, TrainingPlan, LearningRecord, Exam, ExamResult

__all__ = [
    "User", "UserRole", "Role", "RoleMenu", "Menu",
    "Dept", "Position", "DictType", "DictItem",
    "OperationLog", "LoginLog", "Message",
    "PosPosition", "MatchRule", "MatchResult", "MatchPushLog",
    "Course", "Lesson", "TrainingPlan", "LearningRecord", "Exam", "ExamResult",
]