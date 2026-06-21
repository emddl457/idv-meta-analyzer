# IDV Meta-Analyzer

제5인격(Identity V) 실전 메타 백과사전 – 데이터베이스 Term Project

---

## 프로젝트 구조

```
idv_meta/
├── main.py          ← Flet GUI 앱 진입점 (여기서 실행)
├── database.py      ← DuckDB 스키마 + 초기 데이터
├── repository.py    ← 테이블별 CRUD 인터페이스 구현
├── service.py       ← 비즈니스 로직 + 트랜잭션 처리
├── assets/
│   └── images/      ← 캐릭터 이미지 (.png)
└── idv_meta.db      ← DuckDB 영속 파일 (자동 생성)
```

## 설치 및 실행

```bash
pip install flet duckdb pandas pillow

python main.py
```

## DB 스키마 (BCNF 정규화)

| 테이블 | 종류 | 설명 |
|--------|------|------|
| Characters | Entity | 캐릭터 기본 정보 |
| Character_Stats | Entity (1:1) | 세부 수치 분리 |
| Traits | Entity | 특성 사전 |
| Maps | Entity | 맵 정보 |
| Character_Traits | Relationship (N:M) | 캐릭터↔특성 교차 |
| Matchups | Relationship (N:M) | 생존자↔감시자 상성 |
| Position_Spawns | Relationship | 맵×포지션 스폰 가이드 |

## 주요 기능

- **캐릭터 도감**: 포지션 필터 / 이름 검색 + 4개 테이블 LEFT JOIN 조회
- **데이터 삽입**: Characters + Stats + Traits 트랜잭션 단위 삽입
- **맵 가이드**: Maps × Position_Spawns JOIN 결과 표출 + 신규 등록
- **경고 팝업**: 주의사항 클릭 시 붉은 다이얼로그 표시 (Use Case 3.6)
