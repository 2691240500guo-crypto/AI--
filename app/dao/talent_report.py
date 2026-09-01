"""报告 DAO（批次 2.3b）。"""
# hq新增内容 - 人才档案批次2.3b
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.talent_report import TalentReport


class TalentReportDAO(BaseDAO[TalentReport]):
    __model__ = TalentReport

    @classmethod
    def upsert(cls, db: Session, talent_id: int, fields: dict) -> TalentReport:
        """按 talent_id 覆盖式 upsert。"""
        row = db.query(TalentReport).filter_by(talent_id=talent_id).first()
        if row is None:
            row = TalentReport(talent_id=talent_id, **fields)
            db.add(row)
        else:
            for k, v in fields.items():
                setattr(row, k, v)
        db.flush()
        return row
