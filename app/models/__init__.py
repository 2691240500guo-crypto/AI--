from app.models.user import User, UserRole
from app.models.role import Role, RoleMenu
from app.models.menu import Menu
from app.models.dept import Dept, Position
from app.models.dict_item import DictType, DictItem
from app.models.operation_log import OperationLog, LoginLog
from app.models.message import Message
from app.models.matching import PosPosition, MatchRule, MatchResult, MatchPushLog
from app.models.assessment import (
    QuestionBank, Question, Paper, PaperQuestion, Result, ResultDetail,
)
# ---- hy 分支合并：人才档案域 + 在线学习 ----
from app.models.talent import (
    Talent, TalentEducation, TalentWorkExperience, TalentProject, TalentCertificate,
    TalentTag, TalentTalentTag, TalentResumeParseLog,
)
from app.models.talent_dict import TalentDict
from app.models.talent_report import TalentReport
from app.models.talent_merge import TalentMerge
from app.models.course import Course
from app.models.course_progress import CourseProgress
from app.models.course_video import CourseVideo

__all__ = [
    "User", "UserRole", "Role", "RoleMenu", "Menu",
    "Dept", "Position", "DictType", "DictItem",
    "OperationLog", "LoginLog", "Message",
    "PosPosition", "MatchRule", "MatchResult", "MatchPushLog",
    "QuestionBank", "Question", "Paper", "PaperQuestion", "Result", "ResultDetail",
    "Talent", "TalentEducation", "TalentWorkExperience", "TalentProject",
    "TalentCertificate", "TalentTag", "TalentTalentTag", "TalentResumeParseLog",
    "TalentDict", "TalentReport", "TalentMerge",
    "Course", "CourseProgress", "CourseVideo",
]