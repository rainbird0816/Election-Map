"""schema + seed 적용해 빈 DB 생성.
실행: python backend/db/init_db.py
"""
import sqlite3
import pathlib

HERE = pathlib.Path(__file__).parent
DB = HERE / "election.sqlite"


def main():
    con = sqlite3.connect(DB)
    for fname in ("schema.sql", "seed_parties.sql", "seed_regions.sql"):
        sql = (HERE / fname).read_text(encoding="utf-8")
        con.executescript(sql)
    con.commit()

    # 검증 출력
    n_parties = con.execute("SELECT COUNT(*) FROM parties").fetchone()[0]
    n_regions = con.execute("SELECT COUNT(*) FROM regions WHERE level='시도'").fetchone()[0]
    print(f"DB created at {DB}")
    print(f"  parties: {n_parties}")
    print(f"  시도 regions: {n_regions}")
    con.close()


if __name__ == "__main__":
    main()
