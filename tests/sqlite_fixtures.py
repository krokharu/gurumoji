"""SQLite contexts in fixtures commit/rollback and close on Windows as well."""
import sqlite3


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *arguments):
        try:
            return super().__exit__(*arguments)
        finally:
            self.close()
