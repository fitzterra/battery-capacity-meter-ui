"""
Database connection and setup functions.
"""

from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import URL

DB_URL = URL.create(
    "postgresql+psycopg",
    username="iot",
    password="shitFlies",
    host="nodered",
    database="iot",
)


engine = create_engine(DB_URL, echo=True)


def createDBAndTables():
    """
    Creates DB and all tables.
    """
    # SQLModel.metadata.create_all(engine)
