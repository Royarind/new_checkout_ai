"""
Database connection and helper functions for SQLite
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

DATABASE_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "checkout_ai.db"

class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT query and return last row ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute UPDATE/DELETE query and return affected rows"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        results = self.execute_query(query, params)
        return results[0] if results else None

# Global database instance
db = Database()
