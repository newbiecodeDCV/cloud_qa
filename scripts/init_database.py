"""
Script để khởi tạo hoặc reset database
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.qa_communicate.database.database import init_db, drop_db, DATABASE_PATH


def main():
    print("="*60)
    print("DATABASE INITIALIZATION SCRIPT")
    print("="*60)
    print(f"\nDatabase location: {DATABASE_PATH}")
    
    if DATABASE_PATH.exists():
        print("\n⚠️  Database file already exists!")
        choice = input("Do you want to DROP all tables and recreate? (yes/no): ")
        if choice.lower() == 'yes':
            drop_db()
            init_db()
            print("\n✅ Database reset successfully!")
        else:
            print("\n❌ Operation cancelled.")
    else:
        init_db()
        print("\n✅ Database created successfully!")
    
    print(f"\nYou can now start the API server.")
    print("="*60)


if __name__ == "__main__":
    main()