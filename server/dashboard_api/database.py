"""Read-only SQLite database connection manager for health data."""
import sqlite3
from contextlib import contextmanager
from typing import Generator
import logging

from .config import get_settings

log = logging.getLogger(__name__)


class DatabaseManager:
    """
    Read-only SQLite database manager for health data.
    Uses separate connections for each domain to avoid conflicts
    with running agents that write to these databases.
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @contextmanager
    def get_biomarker_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get read-only connection to biomarker database."""
        yield from self._connect(self.settings.biomarker_db_path)

    @contextmanager
    def get_fitness_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get read-only connection to fitness database."""
        yield from self._connect(self.settings.fitness_db_path)

    @contextmanager
    def get_diet_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get read-only connection to diet database."""
        yield from self._connect(self.settings.diet_db_path)

    @contextmanager
    def get_wellness_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get read-only connection to mental wellness database."""
        yield from self._connect(self.settings.wellness_db_path)

    def _connect(self, db_path: str) -> Generator[sqlite3.Connection, None, None]:
        """
        Create a read-only connection with proper isolation.
        Uses URI mode with mode=ro to ensure read-only access.
        """
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like row access
        try:
            yield conn
        finally:
            conn.close()


# Singleton instance
db_manager = DatabaseManager()
