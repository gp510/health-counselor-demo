#!/usr/bin/env python3
"""
Populate SQLite databases from CSV files for Health Counselor agents.

This script creates persistent SQLite database files from the CSV data,
matching the schema that sam_sql_database plugin expects.

Usage:
    python scripts/populate_databases.py
"""
import csv
import sqlite3
import os
from pathlib import Path


# Base directory (project root)
BASE_DIR = Path(__file__).parent.parent

# CSV to Database mappings
DATABASE_CONFIGS = [
    {
        "csv_file": "CSV_Data/biomarker_data.csv",
        "db_file": "biomarker.db",
        "table_name": "biomarker_data",
    },
    {
        "csv_file": "CSV_Data/fitness_data.csv",
        "db_file": "fitness.db",
        "table_name": "fitness_data",
    },
    {
        "csv_file": "CSV_Data/diet_logs.csv",
        "db_file": "diet.db",
        "table_name": "diet_logs",
    },
    {
        "csv_file": "CSV_Data/mental_wellness.csv",
        "db_file": "mental_wellness.db",
        "table_name": "mental_wellness",
    },
]


def sanitize_column_name(name: str) -> str:
    """Sanitize column name for SQL compatibility."""
    # Replace non-alphanumeric characters with underscores
    sanitized = "".join(c if c.isalnum() else "_" for c in name)
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized.lower()


def populate_database(config: dict) -> int:
    """
    Create and populate a SQLite database from a CSV file.

    Args:
        config: Dictionary with csv_file, db_file, and table_name

    Returns:
        Number of rows inserted
    """
    csv_path = BASE_DIR / config["csv_file"]
    db_path = BASE_DIR / config["db_file"]
    table_name = config["table_name"]

    # Check CSV exists
    if not csv_path.exists():
        print(f"  ERROR: CSV file not found: {csv_path}")
        return 0

    # Remove existing database file
    if db_path.exists():
        os.remove(db_path)
        print(f"  Removed existing: {db_path.name}")

    # Read CSV headers and data
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        sanitized_headers = [sanitize_column_name(h) for h in headers]
        rows = list(reader)

    # Create database and table
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build column definitions (all TEXT, matching sam_sql_database)
    columns = []

    # Add auto-increment id if not present
    if "id" not in sanitized_headers:
        columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")

    # Add CSV columns as TEXT
    for header in sanitized_headers:
        columns.append(f"{header} TEXT")

    # Create table
    create_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
    cursor.execute(create_sql)

    # Insert data
    placeholders = ", ".join(["?"] * len(sanitized_headers))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(sanitized_headers)}) VALUES ({placeholders})"

    cursor.executemany(insert_sql, rows)
    conn.commit()

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]

    conn.close()

    return count


def main():
    """Populate all health agent databases."""
    print("=" * 60)
    print("Health Counselor Database Population Script")
    print("=" * 60)
    print(f"\nBase directory: {BASE_DIR}\n")

    total_rows = 0

    for config in DATABASE_CONFIGS:
        print(f"Processing: {config['csv_file']} -> {config['db_file']}")

        row_count = populate_database(config)
        total_rows += row_count

        print(f"  Created table: {config['table_name']}")
        print(f"  Rows inserted: {row_count}")
        print()

    print("=" * 60)
    print(f"Complete! Total rows across all databases: {total_rows}")
    print("=" * 60)

    # Print database file locations
    print("\nDatabase files created:")
    for config in DATABASE_CONFIGS:
        db_path = BASE_DIR / config["db_file"]
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            print(f"  {db_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
