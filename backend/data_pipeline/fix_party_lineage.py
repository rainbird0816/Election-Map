"""정당 계열(lineage) 보정 + 초기 대선 정당 추가.

개관(개관 페이지)에서 '이름을 바꾸거나 통합한 정당을 같은 계열로' 묶기 위해,
parties.lineage_id 가 기타(7)로 잘못 분류된 주요 정당들을 본래 계열로 옮긴다.
계열 분류는 정당 계보(명칭변경·합당·후신)를 기준으로 한다.

party_lineage(label):
 1 민주당계 / 2 보수계(국민의힘) / 3 진보정당계(정의당)
 4 충청계(자민련/선진당) / 5 국민의당/제3지대 / 6 무소속 / 7 기타·군소

실행: python backend/data_pipeline/fix_party_lineage.py
"""
import sqlite3
import pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "db" / "election.sqlite"

# name -> lineage_id (계보 기준). 동명(민주당 등 lineage 이미 1)은 그대로.
FIX = {
    # 민주당계: 평민당→국민회의→…→더민주, YS 이전 통일민주당, 새로운미래(2024 분당)
    "평화민주당": 1, "새정치국민회의": 1, "통일민주당": 1, "새로운미래": 1,
    # 보수계: 민정당→민자당→신한국당→한나라→…→국민의힘
    "민주정의당": 2, "민주자유당": 2, "신한국당": 2,
    # 진보정당계: 민노당→통진당→정의당/진보당, 진보신당
    "진보당": 3, "진보신당": 3,
    # 충청계: 신민주공화당→(민자합당)→자민련→선진당, 국민중심당
    "신민주공화당": 4, "자민련": 4, "국민중심당": 4, "국민중심연합": 4,
    # 제3지대: 정몽준 국민통합21·통일국민당, 박찬종, 문국현, 이준석 개혁신당
    "국민통합21": 5, "통일국민당": 5, "신정치개혁당": 5, "창조한국당": 5, "개혁신당": 5,
}

# 초기 대선 신규 정당(현 parties에 없음): name -> (lineage_id, color)
ADD = {
    "국민신당": (5, "#1CA4DE"),     # 1997 이인제, 제3지대
    "국민승리21": (3, "#E5007F"),   # 1997 권영길, 민노당 전신(진보)
}


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    have = {r[0] for r in cur.execute("SELECT name FROM parties")}
    moved = 0
    for name, lid in FIX.items():
        if name in have:
            cur.execute("UPDATE parties SET lineage_id=? WHERE name=?", (lid, name))
            moved += cur.rowcount
    added = 0
    for name, (lid, color) in ADD.items():
        if name not in have:
            cur.execute("INSERT INTO parties(name, lineage_id, color_hex) VALUES(?,?,?)",
                        (name, lid, color))
            added += 1
    con.commit()
    print(f"계열 보정 {moved}건, 신규 정당 {added}건")
    # 결과 확인
    print("--- 계열별 정당 수 ---")
    for r in cur.execute("SELECT l.label, COUNT(*) n FROM parties p "
                         "JOIN party_lineage l ON l.id=p.lineage_id GROUP BY l.id ORDER BY l.id"):
        print(f"  {r[0]}: {r[1]}")
    con.close()


if __name__ == "__main__":
    main()
