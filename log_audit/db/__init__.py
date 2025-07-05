# db/__init__.py
import pymysql
from DBUtils.PooledDB import PooledDB
from config import DB_CONFIG

pool = PooledDB(
    creator=pymysql,
    maxconnections=5,
    mincached=2,
    blocking=True,
    **DB_CONFIG
)

def get_conn():
    return pool.connection()