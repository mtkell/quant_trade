"""SQLite encryption helpers using sqlcipher (optional).

If sqlcipher is not installed, falls back to unencrypted SQLite.
"""
import sqlite3
from pathlib import Path
from typing import Optional


def has_sqlcipher() -> bool:
    """Check if sqlcipher is available."""
    try:
        import sqlcipher3  # type: ignore
        return True
    except ImportError:
        return False


def get_encrypted_connection(
    db_path: str,
    password: str,
    timeout: int = 30,
) -> sqlite3.Connection:
    """Get an encrypted SQLite connection using sqlcipher.
    
    Args:
        db_path: Path to database file
        password: Encryption password
        timeout: Connection timeout in seconds
    
    Returns:
        sqlite3.Connection with encryption enabled
    
    Raises:
        RuntimeError: If sqlcipher is not installed
    """
    try:
        import sqlcipher3 as sqlite3_enc  # type: ignore
    except ImportError:
        raise RuntimeError(
            "sqlcipher3 is not installed. Install with: pip install sqlcipher3\n"
            "Or use get_connection() for unencrypted database."
        )
    
    conn = sqlite3_enc.connect(db_path, timeout=timeout)
    conn.execute(f"PRAGMA key = '{password}'")
    conn.execute("PRAGMA cipher_page_size = 4096")
    conn.execute("PRAGMA cipher_compatibility = 3")
    # Test the connection by querying sqlite_master
    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
    except Exception as e:
        raise RuntimeError(f"Failed to open encrypted database (wrong password?): {e}")
    
    return conn


def get_connection(
    db_path: str,
    password: Optional[str] = None,
    timeout: int = 30,
) -> sqlite3.Connection:
    """Get a SQLite connection, optionally encrypted.
    
    Args:
        db_path: Path to database file
        password: Optional encryption password. If provided, uses sqlcipher.
        timeout: Connection timeout in seconds
    
    Returns:
        sqlite3.Connection
    """
    if password:
        return get_encrypted_connection(db_path, password, timeout)
    else:
        return sqlite3.connect(db_path, timeout=timeout)


def encrypt_existing_db(unencrypted_path: str, encrypted_path: str, password: str) -> None:
    """Migrate an unencrypted SQLite database to encrypted using sqlcipher.
    
    Args:
        unencrypted_path: Path to original unencrypted database
        encrypted_path: Path to new encrypted database
        password: Encryption password for new database
    """
    try:
        import sqlcipher3  # type: ignore
    except ImportError:
        raise RuntimeError(
            "sqlcipher3 is required for encryption. Install with: pip install sqlcipher3"
        )
    
    # Open unencrypted source
    src = sqlite3.connect(unencrypted_path)
    
    # Create encrypted destination
    dst = sqlcipher3.connect(encrypted_path)
    dst.execute(f"PRAGMA key = '{password}'")
    dst.execute("PRAGMA cipher_page_size = 4096")
    
    # Dump and restore
    with src:
        sql = '\n'.join(src.iterdump())
    
    with dst:
        dst.executescript(sql)
    
    src.close()
    dst.close()
