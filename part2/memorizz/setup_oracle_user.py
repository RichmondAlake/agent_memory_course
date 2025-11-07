"""
Oracle Database Complete Setup for Memorizz

This script performs a complete setup:
1. Creates the memorizz_user with all required privileges
2. Grants JSON Duality View privileges
3. Creates the relational schema (tables, indexes)
4. Creates JSON Duality Views
5. Verifies the setup

Run this after starting your Oracle database (via Docker or otherwise).

Usage:
    python setup_oracle_user.py

Prerequisites:
- Oracle Database 23ai running (for AI Vector Search and Duality Views)
- oracledb Python package installed: pip install oracledb
- Admin credentials (system user)
"""

import sys
from pathlib import Path

import oracledb


def parse_sql_file(filepath):
    """Parse SQL file into individual executable statements."""
    with open(filepath, "r") as f:
        content = f.read()

    # Remove single-line comments
    lines = []
    for line in content.split("\n"):
        if "--" in line:
            line = line[: line.index("--")]
        lines.append(line)
    content = "\n".join(lines)

    # Remove multi-line comments
    while "/*" in content:
        start = content.index("/*")
        end = content.index("*/", start) + 2
        content = content[:start] + content[end:]

    # Split by semicolons
    statements = [s.strip() for s in content.split(";") if s.strip()]

    # Filter out COMMENT statements
    statements = [s for s in statements if not s.upper().startswith("COMMENT")]

    return statements


def setup_oracle_user():
    """Create and configure memorizz user in Oracle database."""

    # Configuration - modify these as needed
    ADMIN_USER = "system"
    # ⚠️ IMPORTANT: For Docker containers, ADMIN_PASSWORD must match ORACLE_PWD from docker run command
    # Example: docker run -e ORACLE_PWD=SecurePass123 ... → ADMIN_PASSWORD = "SecurePass123"
    ADMIN_PASSWORD = "SecurePass123"  # Change to your admin password
    DSN = "localhost:1521/FREEPDB1"  # Change if using different host/port/service

    # User to create
    MEMORIZZ_USER = "memorizz_user"
    MEMORIZZ_PASSWORD = "SecurePass123!"  # Change to your desired password

    # SQL files - resolve paths relative to script location
    # The script is at: part2/memorizz/setup_oracle_user.py
    # SQL files are at: part2/memorizz/oracle/
    # Use .resolve() to get absolute path regardless of where script is called from
    SCRIPT_DIR = Path(__file__).resolve().parent  # part2/memorizz/ (absolute)
    SQL_DIR = SCRIPT_DIR / "oracle"  # part2/memorizz/oracle/ (absolute)
    SCHEMA_FILE = SQL_DIR / "schema_relational.sql"
    VIEWS_FILE = SQL_DIR / "duality_views.sql"

    print("=" * 70)
    print("Oracle Database Complete Setup for Memorizz")
    print("=" * 70)
    print()

    # Show resolved paths
    print(f"Script location: {Path(__file__).resolve()}")
    print(f"Script directory: {SCRIPT_DIR.resolve()}")
    print(f"SQL directory: {SQL_DIR.resolve()}")
    print()

    # Verify SQL files exist
    if not SCHEMA_FILE.exists():
        print(f"✗ Schema file not found: {SCHEMA_FILE.resolve()}")
        print(f"  Expected at: {SCHEMA_FILE}")
        print("  Please verify the project structure is correct")
        return False

    if not VIEWS_FILE.exists():
        print(f"✗ Views file not found: {VIEWS_FILE.resolve()}")
        print(f"  Expected at: {VIEWS_FILE}")
        print("  Please verify the project structure is correct")
        return False

    print(f"✓ Found schema file: {SCHEMA_FILE.name}")
    print(f"✓ Found views file: {VIEWS_FILE.name}")
    print()

    # ========== STEP 1: Create User ==========
    print("STEP 1: Connecting and Creating User")
    print("-" * 70)

    print(f"Connecting to Oracle as {ADMIN_USER}...")
    try:
        admin_conn = oracledb.connect(user=ADMIN_USER, password=ADMIN_PASSWORD, dsn=DSN)
        admin_cursor = admin_conn.cursor()
        print("✓ Connected successfully!")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nPlease check:")
        print("  1. Oracle database is running")
        print("  2. Connection details are correct")
        print("  3. Admin password is correct")
        # Common issue: ORA-01017 means ADMIN_PASSWORD doesn't match Docker's ORACLE_PWD
        if "ORA-01017" in str(e):
            print(f"\n⚠️  Password mismatch detected! Verify ADMIN_PASSWORD matches ORACLE_PWD from docker run")
        return False

    # Drop existing user if exists
    print(f"\nDropping existing {MEMORIZZ_USER} user (if exists)...")
    try:
        # First, kill any active sessions for this user
        print("  Checking for active sessions...")
        admin_cursor.execute(
            f"""
            SELECT sid, serial# FROM v$session WHERE username = UPPER('{MEMORIZZ_USER}')
        """
        )
        sessions = admin_cursor.fetchall()

        if sessions:
            print(f"  Found {len(sessions)} active session(s), terminating...")
            for sid, serial in sessions:
                try:
                    admin_cursor.execute(
                        f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE"
                    )
                    print(f"    ✓ Killed session {sid},{serial}")
                except Exception as e:
                    error_msg = str(e)
                    if "ORA-00031" in error_msg:
                        print(f"    ✓ Session {sid},{serial} marked for kill")
                    else:
                        print(f"    ⚠ Failed to kill session {sid},{serial}: {e}")

            # Reconnect if our connection was lost
            try:
                admin_cursor.execute("SELECT 1 FROM DUAL")
            except Exception:
                print("  Reconnecting to database...")
                admin_cursor.close()
                admin_conn.close()
                admin_conn = oracledb.connect(
                    user=ADMIN_USER, password=ADMIN_PASSWORD, dsn=DSN
                )
                admin_cursor = admin_conn.cursor()
                print("  ✓ Reconnected successfully")
        else:
            print("  No active sessions found")

        # Now drop the user
        admin_cursor.execute(f"DROP USER {MEMORIZZ_USER} CASCADE")
        print(f"  ✓ Dropped existing {MEMORIZZ_USER} user")
    except Exception as e:
        if "ORA-01918" in str(e):
            print("  ℹ User doesn't exist yet (this is fine)")
        else:
            print(f"  ⚠ {e}")

    # Create user
    print(f"\nCreating {MEMORIZZ_USER} user...")
    try:
        admin_cursor.execute(
            f'CREATE USER {MEMORIZZ_USER} IDENTIFIED BY "{MEMORIZZ_PASSWORD}"'
        )
        print(f"  ✓ User {MEMORIZZ_USER} created")
    except Exception as e:
        print(f"  ✗ Failed to create user: {e}")
        admin_conn.close()
        return False

    # Grant basic privileges
    print("\nGranting basic privileges...")
    try:
        admin_cursor.execute(f"GRANT CREATE SESSION TO {MEMORIZZ_USER}")
        print("  ✓ CREATE SESSION")

        admin_cursor.execute(f"GRANT CREATE TABLE TO {MEMORIZZ_USER}")
        print("  ✓ CREATE TABLE")

        admin_cursor.execute(f"GRANT UNLIMITED TABLESPACE TO {MEMORIZZ_USER}")
        print("  ✓ UNLIMITED TABLESPACE")
    except Exception as e:
        print(f"  ✗ Failed to grant basic privileges: {e}")
        admin_conn.close()
        return False

    # Grant AI Vector Search privileges
    print("\nGranting AI Vector Search privileges...")
    try:
        admin_cursor.execute(f"GRANT EXECUTE ON DBMS_VECTOR TO {MEMORIZZ_USER}")
        print("  ✓ EXECUTE ON DBMS_VECTOR")

        admin_cursor.execute(f"GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO {MEMORIZZ_USER}")
        print("  ✓ EXECUTE ON DBMS_VECTOR_CHAIN")
    except Exception as e:
        print(f"  ⚠ Vector privileges not available: {e}")
        print("    This is OK if not using Oracle 23ai+")

    # Grant JSON Duality View privileges
    print("\nGranting JSON Duality View privileges...")
    try:
        admin_cursor.execute(f"GRANT SODA_APP TO {MEMORIZZ_USER}")
        print("  ✓ SODA_APP")

        admin_cursor.execute(f"GRANT CREATE VIEW TO {MEMORIZZ_USER}")
        print("  ✓ CREATE VIEW")

        admin_cursor.execute(f"GRANT SELECT ANY TABLE TO {MEMORIZZ_USER}")
        print("  ✓ SELECT ANY TABLE")
    except Exception as e:
        print(f"  ✗ Failed to grant Duality View privileges: {e}")
        admin_conn.close()
        return False

    admin_conn.commit()
    admin_cursor.close()
    admin_conn.close()

    print("\n✓ User creation and privilege grants complete!")
    print()

    # ========== STEP 2: Create Schema ==========
    print("STEP 2: Creating Relational Schema")
    print("-" * 70)

    print(f"Connecting as {MEMORIZZ_USER}...")
    try:
        user_conn = oracledb.connect(
            user=MEMORIZZ_USER, password=MEMORIZZ_PASSWORD, dsn=DSN
        )
        user_cursor = user_conn.cursor()
        print("✓ Connected!")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

    print(f"\nExecuting {SCHEMA_FILE.name}...")
    statements = parse_sql_file(SCHEMA_FILE)
    print(f"Found {len(statements)} SQL statements")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, stmt in enumerate(statements, 1):
        try:
            user_cursor.execute(stmt)
            success_count += 1
            if i % 10 == 0 or i == len(statements):
                print(f"  ✓ Executed {i}/{len(statements)} statements...")
        except Exception as e:
            error_str = str(e)
            if "ORA-00955" in error_str or "ORA-01408" in error_str:
                skip_count += 1
            else:
                fail_count += 1
                if fail_count <= 3:  # Only show first 3 errors
                    print(f"  ✗ Statement {i}: {e}")

    user_conn.commit()
    print(
        f"\n📊 Schema Summary: ✓ {success_count} success, ⚠ {skip_count} skipped, ✗ {fail_count} failed"
    )
    print()

    # ========== STEP 3: Create Duality Views ==========
    print("STEP 3: Creating JSON Duality Views")
    print("-" * 70)

    print(f"Executing {VIEWS_FILE.name}...")
    statements = parse_sql_file(VIEWS_FILE)
    print(f"Found {len(statements)} view statements")

    success_count = 0
    fail_count = 0

    for i, stmt in enumerate(statements, 1):
        try:
            user_cursor.execute(stmt)
            success_count += 1
            print(f"  ✓ Created view {i}/{len(statements)}")
        except Exception as e:
            fail_count += 1
            print(f"  ✗ View {i} failed: {e}")

    user_conn.commit()
    print(f"\n📊 Views Summary: ✓ {success_count} success, ✗ {fail_count} failed")
    print()

    # ========== STEP 4: Verify Setup ==========
    print("STEP 4: Verifying Setup")
    print("-" * 70)

    # Check tables
    print("\n📊 Relational Tables:")
    user_cursor.execute(
        """
        SELECT table_name FROM user_tables
        WHERE table_name IN ('AGENTS', 'AGENT_LLM_CONFIGS', 'AGENT_MEMORIES', 'PERSONAS',
                             'TOOLBOX', 'CONVERSATION_MEMORY', 'LONG_TERM_MEMORY',
                             'SHORT_TERM_MEMORY', 'WORKFLOW_MEMORY', 'SHARED_MEMORY',
                             'SUMMARIES', 'SEMANTIC_CACHE')
        ORDER BY table_name
    """
    )
    tables = [row[0] for row in user_cursor.fetchall()]
    for table in tables:
        print(f"  ✓ {table}")
    print(f"  Total: {len(tables)} tables")

    # Check views
    print("\n📄 JSON Duality Views:")
    user_cursor.execute(
        "SELECT view_name FROM user_views WHERE view_name LIKE '%_DV' ORDER BY view_name"
    )
    views = [row[0] for row in user_cursor.fetchall()]
    for view in views:
        print(f"  ✓ {view}")
    print(f"  Total: {len(views)} views")

    # Check vector indexes
    print("\n🔍 Vector Indexes:")
    user_cursor.execute(
        "SELECT index_name FROM user_indexes WHERE index_name LIKE 'IDX_%_VEC' ORDER BY index_name"
    )
    indexes = [row[0] for row in user_cursor.fetchall()]
    print(f"  Total: {len(indexes)} vector indexes")

    user_cursor.close()
    user_conn.close()

    print()
    print("=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)
    print()
    print("Connection details for your Memorizz application:")
    print(f"  User:     {MEMORIZZ_USER}")
    print(f"  Password: {MEMORIZZ_PASSWORD}")
    print(f"  DSN:      {DSN}")
    print()
    print("Example usage in Python:")
    print()
    print("  from memorizz.memory_provider.oracle import OracleProvider, OracleConfig")
    print("  from memorizz.memagent.builders import MemAgentBuilder")
    print("  ")
    print("  # Create Oracle provider")
    print("  oracle_config = OracleConfig(")
    print(f'      user="{MEMORIZZ_USER}",')
    print(f'      password="{MEMORIZZ_PASSWORD}",')
    print(f'      dsn="{DSN}",')
    print('      embedding_provider="openai",')
    print(
        '      embedding_config={"model": "text-embedding-3-small", "api_key": "your-key"}'
    )
    print("  )")
    print("  oracle_provider = OracleProvider(oracle_config)")
    print("  ")
    print("  # Build your agent")
    print("  agent = (MemAgentBuilder()")
    print('      .with_instruction("You are a helpful assistant.")')
    print("      .with_memory_provider(oracle_provider)")
    print("      .with_llm_config({")
    print('          "provider": "openai",')
    print('          "model": "gpt-4o-mini",')
    print('          "api_key": "your-openai-key"')
    print("      })")
    print("      .build()")
    print("  )")
    print()
    print("Summary counts:")
    print(f"  - Tables: {len(tables)}/12 expected")
    print(f"  - Duality Views: {len(views)}/10 expected")
    print(f"  - Vector Indexes: {len(indexes)}/10 expected")

    if len(tables) >= 12 and len(views) >= 10:
        print("\n✅ All components created successfully!")
    else:
        print("\n⚠️  Some components may be missing. Check the logs above.")

    print()

    return True


if __name__ == "__main__":
    try:
        success = setup_oracle_user()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
