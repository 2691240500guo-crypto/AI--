"""部门 DAO（A07）。"""
from app.dao.base import BaseDAO
from app.models.dept import Dept


class DeptDAO(BaseDAO[Dept]):
    __model__ = Dept
