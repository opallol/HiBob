"""Database connection helper."""
import pymysql

from .config import DB_CONFIG


def get_connection():
    """Return a new PyMySQL connection using centralized credentials."""
    return pymysql.connect(**DB_CONFIG)
