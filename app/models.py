"""
Database Model Definitions
"""

from datetime import datetime

from typing import List
from pydantic import constr, RootModel

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    SmallInteger,
    REAL,
    String,
    Text,
    text,
)

from sqlmodel import (
    Field,
    SQLModel,
)


class BatCap(SQLModel, table=True):
    """
    Battery Capacity Metrics.
    """

    __tablename__ = "bat_cap"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="bat_cap_pkey"),
        Index("idx_bat_id", "bat_id"),
        Index("idx_bc_name", "bc_name"),
        Index("idx_created", "created"),
        Index("idx_soc_uid", "soc_uid"),
        Index("idx_state", "state"),
    )

    id: int | None = Field(default=None, primary_key=True)
    created: datetime = Field(
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        )
    )
    bc_name: str = Field(sa_column=Column(Text, nullable=False))
    state: str = Field(sa_column=Column(Text, nullable=False))
    bat_id: str | None = Field(default=None, sa_column=Column(String(20)))
    bat_v: int | None = Field(default=None)
    adc_v: int | None = Field(default=None)
    current: int | None = Field(default=None)
    charge: int | None = Field(default=None)
    mah: int | None = Field(default=None)
    period: int | None = Field(default=None)
    shunt: float | None = Field(default=None, sa_column=Column(REAL))
    soc_state: str | None = Field(default=None, sa_column=Column(Text))
    soc_cycle: int | None = Field(default=None, sa_column=Column(SmallInteger))
    soc_cycles: int | None = Field(default=None, sa_column=Column(SmallInteger))
    soc_cycle_period: int | None = Field(default=None)
    soc_uid: str | None = Field(default=None, sa_column=Column(Text))


# A list of Battery IDs as returned by data.getAllBatIDs
BatteryIDs = RootModel[List[constr(min_length=10, max_length=10)]]
