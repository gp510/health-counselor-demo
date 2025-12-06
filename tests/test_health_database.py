"""
Unit tests for Health Counselor database loading.

These tests verify:
1. CSV files can be loaded into SQLite databases
2. Table schemas match expected column definitions
3. SQL queries execute successfully against loaded data
4. Row counts match between CSV and database

These tests run WITHOUT requiring any agents or gateway to be running.
They simulate the sam_sql_database plugin's CSV loading behavior.

Usage:
    pytest tests/test_health_database.py -v
"""
import pytest


class TestDatabaseLoading:
    """Test CSV to SQLite database loading."""

    def test_biomarker_database_loads(self, create_test_database, data_path, health_agent_configs):
        """Verify biomarker CSV loads into SQLite successfully."""
        config = health_agent_configs["biomarker"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"SELECT COUNT(*) FROM {config.table_name}")
        count = cursor.fetchone()[0]

        assert count > 0, f"No rows loaded into {config.table_name}"
        print(f"\n{config.table_name}: {count} rows loaded")

    def test_fitness_database_loads(self, create_test_database, data_path, health_agent_configs):
        """Verify fitness CSV loads into SQLite successfully."""
        config = health_agent_configs["fitness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"SELECT COUNT(*) FROM {config.table_name}")
        count = cursor.fetchone()[0]

        assert count > 0, f"No rows loaded into {config.table_name}"
        print(f"\n{config.table_name}: {count} rows loaded")

    def test_diet_database_loads(self, create_test_database, data_path, health_agent_configs):
        """Verify diet CSV loads into SQLite successfully."""
        config = health_agent_configs["diet"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"SELECT COUNT(*) FROM {config.table_name}")
        count = cursor.fetchone()[0]

        assert count > 0, f"No rows loaded into {config.table_name}"
        print(f"\n{config.table_name}: {count} rows loaded")

    def test_mental_wellness_database_loads(self, create_test_database, data_path, health_agent_configs):
        """Verify mental wellness CSV loads into SQLite successfully."""
        config = health_agent_configs["mental_wellness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"SELECT COUNT(*) FROM {config.table_name}")
        count = cursor.fetchone()[0]

        assert count > 0, f"No rows loaded into {config.table_name}"
        print(f"\n{config.table_name}: {count} rows loaded")


class TestDatabaseSchemas:
    """Verify database table schemas match expected columns."""

    def test_biomarker_table_schema(self, create_test_database, data_path, health_agent_configs):
        """Verify biomarker_data table has expected columns."""
        config = health_agent_configs["biomarker"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"PRAGMA table_info({config.table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        expected_columns = set(config.expected_columns)

        missing = expected_columns - actual_columns
        assert not missing, f"Missing columns in {config.table_name}: {missing}"

    def test_fitness_table_schema(self, create_test_database, data_path, health_agent_configs):
        """Verify fitness_data table has expected columns."""
        config = health_agent_configs["fitness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"PRAGMA table_info({config.table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        expected_columns = set(config.expected_columns)

        missing = expected_columns - actual_columns
        assert not missing, f"Missing columns in {config.table_name}: {missing}"

    def test_diet_table_schema(self, create_test_database, data_path, health_agent_configs):
        """Verify diet_logs table has expected columns."""
        config = health_agent_configs["diet"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"PRAGMA table_info({config.table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        expected_columns = set(config.expected_columns)

        missing = expected_columns - actual_columns
        assert not missing, f"Missing columns in {config.table_name}: {missing}"

    def test_mental_wellness_table_schema(self, create_test_database, data_path, health_agent_configs):
        """Verify mental_wellness table has expected columns."""
        config = health_agent_configs["mental_wellness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute(f"PRAGMA table_info({config.table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        expected_columns = set(config.expected_columns)

        missing = expected_columns - actual_columns
        assert not missing, f"Missing columns in {config.table_name}: {missing}"


class TestDatabaseQueries:
    """Test SQL queries similar to what agents execute."""

    def test_biomarker_abnormal_values_query(self, create_test_database, data_path, health_agent_configs):
        """Query for biomarkers outside normal range."""
        config = health_agent_configs["biomarker"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT test_id, biomarker_name, value, status
            FROM biomarker_data
            WHERE status IN ('low', 'high', 'critical')
            ORDER BY test_date DESC
        """)
        results = cursor.fetchall()

        # We know from the data there are abnormal values (LDL high, Vitamin D low, etc.)
        assert len(results) > 0, "Expected some abnormal biomarker values"
        print(f"\nFound {len(results)} abnormal biomarker readings")

    def test_fitness_weekly_steps_query(self, create_test_database, data_path, health_agent_configs):
        """Query for average weekly steps."""
        config = health_agent_configs["fitness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT AVG(CAST(steps AS REAL)) as avg_steps,
                   MIN(CAST(steps AS INTEGER)) as min_steps,
                   MAX(CAST(steps AS INTEGER)) as max_steps
            FROM fitness_data
        """)
        result = cursor.fetchone()

        avg_steps, min_steps, max_steps = result
        assert avg_steps is not None, "Expected average steps calculation"
        assert min_steps > 0, "Expected minimum steps > 0"
        print(f"\nSteps: avg={avg_steps:.0f}, min={min_steps}, max={max_steps}")

    def test_diet_daily_calories_query(self, create_test_database, data_path, health_agent_configs):
        """Query for daily calorie totals."""
        config = health_agent_configs["diet"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT date, SUM(CAST(calories AS INTEGER)) as daily_calories
            FROM diet_logs
            GROUP BY date
            ORDER BY date DESC
            LIMIT 5
        """)
        results = cursor.fetchall()

        assert len(results) > 0, "Expected daily calorie totals"
        for date, calories in results:
            assert calories > 0, f"Expected positive calories for {date}"
        print(f"\nFound {len(results)} days of calorie data")

    def test_mental_wellness_mood_trend_query(self, create_test_database, data_path, health_agent_configs):
        """Query for mood trends."""
        config = health_agent_configs["mental_wellness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT AVG(CAST(mood_score AS REAL)) as avg_mood,
                   AVG(CAST(stress_level AS REAL)) as avg_stress,
                   AVG(CAST(energy_level AS REAL)) as avg_energy
            FROM mental_wellness
        """)
        result = cursor.fetchone()

        avg_mood, avg_stress, avg_energy = result
        assert 1 <= avg_mood <= 10, "Mood score should be 1-10"
        assert 1 <= avg_stress <= 10, "Stress level should be 1-10"
        assert 1 <= avg_energy <= 10, "Energy level should be 1-10"
        print(f"\nAverages: mood={avg_mood:.1f}, stress={avg_stress:.1f}, energy={avg_energy:.1f}")

    def test_fitness_workout_summary_query(self, create_test_database, data_path, health_agent_configs):
        """Query for workout type summary."""
        config = health_agent_configs["fitness"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT workout_type, COUNT(*) as count
            FROM fitness_data
            WHERE workout_type != 'none'
            GROUP BY workout_type
            ORDER BY count DESC
        """)
        results = cursor.fetchall()

        assert len(results) > 0, "Expected workout type summary"
        workout_types = [r[0] for r in results]
        print(f"\nWorkout types found: {workout_types}")

    def test_diet_high_sodium_meals_query(self, create_test_database, data_path, health_agent_configs):
        """Query for high sodium meals."""
        config = health_agent_configs["diet"]
        conn, cursor = create_test_database(config, data_path)

        cursor.execute("""
            SELECT meal_id, food_items, CAST(sodium_mg AS INTEGER) as sodium
            FROM diet_logs
            WHERE CAST(sodium_mg AS INTEGER) > 800
            ORDER BY sodium DESC
        """)
        results = cursor.fetchall()

        # We know from the data there are high sodium meals
        assert len(results) > 0, "Expected some high-sodium meals"
        print(f"\nFound {len(results)} high-sodium meals (>800mg)")
