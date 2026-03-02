import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_USER = os.getenv('CRON_DB_USER', 'guidda')
DB_PASS = os.getenv('CRON_DB_PASS', '!q1w2e3r4t5')
DB_HOST = os.getenv('CRON_DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('CRON_DB_PORT', '3306')
DB_NAME = os.getenv('CRON_DB_NAME', 'internal_db')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
