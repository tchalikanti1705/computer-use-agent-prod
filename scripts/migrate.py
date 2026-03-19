from pathlib import Path
from sqlalchemy import create_engine, text
from shared.config import get_settings

def run_migrations():
    engine = create_engine(get_settings().database_url)
    for f in sorted((Path(__file__).parent.parent / "migrations").glob("*.sql")):
        print(f"Running: {f.name}")
        with engine.connect() as c:
            c.execute(text(f.read_text()))
            c.commit()
    print("Done.")

if __name__ == "__main__":
    run_migrations()
