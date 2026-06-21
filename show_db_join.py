import duckdb

# DB 파일 경로
db_path = r"c:\Users\염정화\Downloads\files\idv_meta.db"
conn = duckdb.connect(db_path)

print("\n[ 3개 테이블 JOIN 출력 결과 (Characters + Character_Traits + Traits) ]")

# 무조건 존재하는 안전한 컬럼만 선택해서 JOIN
join_sql = """
    SELECT 
        c.name AS '캐릭터명', 
        c.faction AS '진영', 
        t.trait_name AS '특성명'
    FROM Characters c
    JOIN Character_Traits ct ON c.char_id = ct.char_id
    JOIN Traits t ON ct.trait_id = t.trait_id
    LIMIT 10
"""

print(conn.execute(join_sql).df())
print("\n" + "="*65 + "\n")