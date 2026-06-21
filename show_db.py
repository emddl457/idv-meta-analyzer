import duckdb

# 진짜 데이터가 들어있는 파일의 절대 경로 지정
db_path = r"c:\Users\염정화\Downloads\files\idv_meta.db"

# 정확한 경로의 DB 연결
conn = duckdb.connect(db_path)

print("\n[ 1. 생성된 테이블 목록 조회 (SHOW TABLES) ]")
print(conn.execute("SHOW TABLES").df())
print("\n" + "="*60 + "\n")

print("[ 2. Characters 테이블 데이터 삽입 결과 확인 (SELECT) ]")
# 어떤 컬럼이든 상관없이 모든 데이터를 가져오되, 화면에 예쁘게 나오도록 5줄만 출력
print(conn.execute("SELECT * FROM Characters LIMIT 5").df())
print("\n" + "="*60 + "\n")

print("[ 3. Traits 테이블 데이터 삽입 결과 확인 (SELECT) ]")
print(conn.execute("SELECT * FROM Traits LIMIT 5").df())