# models.py used by run_ml_to_db.py

from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String

Base = declarative_base()

class ProsAndCons(Base):
    __tablename__ = "prosandcons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String(255))
    pros: Mapped[str] = mapped_column(String(255), nullable=True)
    cons: Mapped[str] = mapped_column(String(255), nullable=True)
