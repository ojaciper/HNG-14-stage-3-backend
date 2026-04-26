import json
import psycopg2
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import uuid
import time
import random

load_dotenv()

def generate_uuid7():
    timestamp_ms = int(time.time() * 1000)
    uuid_int = (timestamp_ms << 80) | (random.getrandbits(80) & ((1 << 80) - 1))
    return str(uuid.UUID(int=uuid_int))

def seed_database():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL not set in environment")
        return
    
    json_file = Path(__file__).parent / "seed_profiles.json"
    if not json_file.exists():
        print(f"Error: {json_file} not found!")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    profiles = data.get("profiles", [])
    print(f"Loaded {len(profiles)} profiles from JSON file")
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True  # Use autocommit to avoid transaction issues
    cursor = conn.cursor()
    
    # First, check if table exists and has correct columns
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'profiles'
    """)
    existing_columns = [row[0] for row in cursor.fetchall()]
    
    # If table doesn't have the right columns, recreate it
    if 'country_name' not in existing_columns:
        print("Recreating table with correct schema...")
        cursor.execute("DROP TABLE IF EXISTS profiles CASCADE")
        cursor.execute("""
            CREATE TABLE profiles (
                id UUID PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                gender VARCHAR(10) NOT NULL,
                gender_probability FLOAT NOT NULL,
                age INTEGER NOT NULL,
                age_group VARCHAR(10) NOT NULL,
                country_id VARCHAR(2) NOT NULL,
                country_name VARCHAR(100) NOT NULL,
                country_probability FLOAT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_profiles_name ON profiles(name)")
        cursor.execute("CREATE INDEX idx_profiles_gender ON profiles(gender)")
        cursor.execute("CREATE INDEX idx_profiles_age_group ON profiles(age_group)")
        cursor.execute("CREATE INDEX idx_profiles_country_id ON profiles(country_id)")
        print("Table created with correct schema")
    
    inserted_count = 0
    skipped_count = 0
    
    for profile in profiles:
        try:
            # Check if profile already exists
            cursor.execute('SELECT 1 FROM profiles WHERE name = %s', (profile['name'],))
            if cursor.fetchone():
                skipped_count += 1
                continue
            
            # Generate UUID v7
            profile_id = generate_uuid7()
            
            # Insert profile with all required fields
            cursor.execute('''
                INSERT INTO profiles (
                    id, name, gender, gender_probability, age, age_group,
                    country_id, country_name, country_probability, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                profile_id,
                profile['name'],
                profile['gender'],
                profile['gender_probability'],
                profile['age'],
                profile['age_group'],
                profile['country_id'],
                profile['country_name'],
                profile['country_probability'],
                datetime.now(timezone.utc)
            ))
            
            inserted_count += 1
            
            if inserted_count % 100 == 0:
                print(f"Inserted {inserted_count} profiles...")
                
        except psycopg2.IntegrityError as e:
            skipped_count += 1
            if 'duplicate key' in str(e):
                pass  # Expected duplicate
            else:
                print(f"Integrity error for {profile['name']}: {e}")
        except Exception as e:
            print(f"Error inserting {profile['name']}: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("SEEDING COMPLETE!")
    print("="*50)
    print(f"Total profiles in JSON: {len(profiles)}")
    print(f"New profiles inserted: {inserted_count}")
    print(f"Profiles skipped (duplicates): {skipped_count}")
    print(f"Total profiles in database: {inserted_count}")
    print("="*50)

def verify_database():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL not set")
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'profiles'
        )
    """)
    table_exists = cursor.fetchone()[0]
    
    if not table_exists:
        print("Table 'profiles' does not exist!")
        cursor.close()
        conn.close()
        return
    
    # Get column info
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'profiles'
        ORDER BY ordinal_position
    """)
    
    print("\nTable schema:")
    for col_name, data_type in cursor.fetchall():
        print(f"  {col_name}: {data_type}")
    
    # Get record count
    cursor.execute('SELECT COUNT(*) FROM profiles')
    count = cursor.fetchone()[0]
    print(f"\nTotal records: {count}")
    
    if count > 0:
        # Show sample
        cursor.execute('SELECT name, age, country_id, country_name FROM profiles LIMIT 3')
        print("\nSample records:")
        for row in cursor.fetchall():
            print(f"  {row[0]}, {row[1]} years, {row[2]} ({row[3]})")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        verify_database()
    else:
        seed_database()
        verify_database()