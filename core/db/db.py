from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config.settings import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()