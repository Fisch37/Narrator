"""
SQL Object Reference Models.
Classes defined herein should **never** be imported outside of database
code! **Outsourcing database interactions is required!**
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import declarative_base, mapped_column, Mapped

Base = declarative_base()

class SQLMasks(Base):
    """
    SQL Data table for the masks.
    Includes every data content except the fields list, which is stored
    in a seperate table.
    """
    __tablename__ = "masks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    avatar_url: Mapped[str|None] = mapped_column()
    owner: Mapped[str] = mapped_column()
    guild: Mapped[str] = mapped_column()

class SQLMaskFields(Base):
    """
    Table storing all fields. Each stored field has an id added to it
    to allow the ORM to read it. Otherwise, fields are tagged with their
    index and mask id
    """
    __tablename__ = "mask_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    mask_id: Mapped[int] = mapped_column()
    index: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    value: Mapped[str] = mapped_column()
    inline: Mapped[bool] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "mask_id",
            "index",
            name="list_position_uniqueness"
        ),
    )
