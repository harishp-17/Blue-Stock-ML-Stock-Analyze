from sqlalchemy import create_engine

HOST = "127.0.0.1"
PORT = 3306
USER = "root"
PASSWORD = ""  
DB_NAME = "ml"

def get_engine():
    url = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}"
    engine = create_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
    )
    return engine
