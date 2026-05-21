from sqlalchemy import (
    Column,
    Integer,
    Text,
    Float,
    DateTime
)

from datetime import datetime

from database import Base


class ScanHistory(Base):

    __tablename__ = "scan_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    submitted_text = Column(
        Text,
        nullable=False
    )

    overall_similarity = Column(
        Float,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
