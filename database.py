"""
database.py
──────────────────────────────────────────────────────────────
DuckDB 연결 & 스키마 초기화, 초기 데이터 삽입을 담당하는 모듈.
앱이 처음 실행될 때 이 파일의 init_db()를 호출하면
필요한 테이블을 전부 만들고 샘플 데이터도 넣어 준다.

정규화 등급: BCNF
  - Characters  : 기본 정보만 보유 (함수 종속: char_id → 나머지)
  - Character_Stats : 1:1 분리 (수치 컬럼 비대화 방지)
  - Traits      : 특성 사전 (trait_id → trait_name, trait_category)
  - Character_Traits: Characters × Traits 교차 엔티티 (N:M 해소)
  - Matchups    : 생존자↔감시자 상성 교차 엔티티 (N:M 해소)
  - Maps        : 맵 기본 정보
  - Position_Spawns: 맵 × 포지션 스폰 가이드
──────────────────────────────────────────────────────────────
"""

import duckdb
import os

# DB 파일 경로 – 같은 디렉터리에 idv_meta.db 파일로 영속 저장
DB_PATH = os.path.join(os.path.dirname(__file__), "idv_meta.db")


def get_conn():
    """DuckDB 커넥션을 새로 열어서 반환. 호출 측에서 .close() 해야 함."""
    return duckdb.connect(DB_PATH)


# ────────────────────────────────────────────────────────────
# DDL – 테이블 생성 (IF NOT EXISTS 이므로 재실행해도 안전)
# ────────────────────────────────────────────────────────────

DDL_STATEMENTS = [

    # 1. Characters – 캐릭터 기본 정보 (Entity 테이블 ①)
    """
    CREATE TABLE IF NOT EXISTS Characters (
        char_id          INTEGER PRIMARY KEY,
        name             VARCHAR(50)  NOT NULL UNIQUE,  -- 캐릭터 이름 (중복 불가)
        faction          VARCHAR(20)  NOT NULL,         -- '생존자' 또는 '감시자'
        position         VARCHAR(50)  NOT NULL,         -- 공식 포지션 (구원형/해독형 등)
        decode_score     INTEGER CHECK(decode_score     BETWEEN 1 AND 10),
        support_score    INTEGER CHECK(support_score    BETWEEN 1 AND 10),
        kiting_score     INTEGER CHECK(kiting_score     BETWEEN 1 AND 10),
        rescue_score     INTEGER CHECK(rescue_score     BETWEEN 1 AND 10),
        operation_guide  TEXT,                          -- 핵심 운영 가이드 메모
        image_path       VARCHAR(200)                   -- 캐릭터 이미지 파일 경로
    );
    """,

    # 1-A. Character_Stats – 세부 수치 (1:1 분리로 BCNF 유지, Entity 테이블 ②)
    # DuckDB 1.5.x는 ON DELETE CASCADE 미지원 → 삭제는 서비스 계층에서 순서 제어
    """
    CREATE TABLE IF NOT EXISTS Character_Stats (
        char_id            INTEGER PRIMARY KEY,
        run_speed_ms       DECIMAL(4,2),   -- 달리기 속도 (m/s)
        walk_speed_ms      DECIMAL(4,2),   -- 걷기 속도 (m/s)
        crawl_speed_ms     DECIMAL(4,2),   -- 기어가기 속도 (m/s)
        decode_time_s      INTEGER,        -- 해독 완료 시간 (초)
        gate_open_time_s   INTEGER,        -- 대문 오픈 시간 (초)
        pallet_drop_time_s DECIMAL(4,2),   -- 판자 내리기 시간 (초)
        vault_fast_time_s  DECIMAL(4,2),   -- 창틀 빠른 통과 (초)
        heal_other_time_s  DECIMAL(5,2),   -- 타인 치료 시간 (초)
        heal_self_time_s   INTEGER,        -- 자가 치료 시간 (초)
        chair_takeoff_time_s INTEGER,      -- 의자 이륙 시간 (초)
        FOREIGN KEY (char_id) REFERENCES Characters(char_id)
    );
    """,

    # 2. Traits – 특성 사전 (Entity 테이블 ③)
    """
    CREATE TABLE IF NOT EXISTS Traits (
        trait_id       INTEGER PRIMARY KEY,
        trait_name     VARCHAR(50) NOT NULL UNIQUE,  -- 특성 이름
        trait_category VARCHAR(20)                   -- '패시브' / '액티브' / '디버프' 등
    );
    """,

    # 3. Character_Traits – 캐릭터↔특성 N:M 교차 엔티티 (Relationship 테이블 ①)
    """
    CREATE TABLE IF NOT EXISTS Character_Traits (
        char_id        INTEGER,
        trait_id       INTEGER,
        specific_value VARCHAR(100),  -- 특성의 구체적 수치 (예: "1.5 데미지 상쇄")
        warning_memo   TEXT,          -- 실전 주의사항
        PRIMARY KEY (char_id, trait_id),
        FOREIGN KEY (char_id)  REFERENCES Characters(char_id),
        FOREIGN KEY (trait_id) REFERENCES Traits(trait_id)
    );
    """,

    # 4. Matchups – 생존자↔감시자 상성 N:M 교차 엔티티 (Relationship 테이블 ②)
    """
    CREATE TABLE IF NOT EXISTS Matchups (
        survivor_id    INTEGER,
        hunter_id      INTEGER,
        matchup_guide  TEXT NOT NULL,   -- 상성 운영 팁
        PRIMARY KEY (survivor_id, hunter_id),
        FOREIGN KEY (survivor_id) REFERENCES Characters(char_id),
        FOREIGN KEY (hunter_id)   REFERENCES Characters(char_id)
    );
    """,

    # 5. Maps – 맵 기본 정보 (Entity 테이블 ④)
    """
    CREATE TABLE IF NOT EXISTS Maps (
        map_id      INTEGER PRIMARY KEY,
        map_name    VARCHAR(50) NOT NULL UNIQUE,
        description TEXT
    );
    """,

    # 6. Position_Spawns – 맵×포지션 스폰 가이드 (Relationship 테이블 ③)
    """
    CREATE TABLE IF NOT EXISTS Position_Spawns (
        spawn_id     INTEGER PRIMARY KEY,
        map_id       INTEGER NOT NULL,
        position     VARCHAR(50) NOT NULL,   -- 포지션 (구원형/해독형 등)
        spawn_point  VARCHAR(50) NOT NULL,   -- 추천 스폰 구역
        guide_memo   TEXT,                   -- 동선 가이드 메모
        FOREIGN KEY (map_id) REFERENCES Maps(map_id)
    );
    """,
]


# ────────────────────────────────────────────────────────────
# 초기 샘플 데이터 (INSERT – 이미 있으면 건너뜀)
# ────────────────────────────────────────────────────────────

def _seed_data(con):
    """앱 첫 실행 시 샘플 데이터를 넣어 두는 함수. 이미 데이터가 있으면 무시."""
    
    # Characters가 비어 있을 때만 삽입
    count = con.execute("SELECT COUNT(*) FROM Characters").fetchone()[0]
    if count > 0:
        return  # 이미 데이터 있음 → 스킵

    base_dir = os.path.dirname(__file__)

    # ── 생존자 캐릭터 ──
    survivors = [
        # (char_id, name, faction, position, dec, sup, kit, resc, guide, image)
        (1, "화가",       "생존자", "견제형",
         5, 4, 9, 6,
         "그림 기믹으로 감시자를 고착시키는 것이 핵심. 팀 어그로 분산에 집중하자.",
         os.path.join(base_dir, "assets/images/painter.png")),

        (2, "인형사",     "생존자", "견제형",
         5, 6, 8, 8,
         "루이 매커니즘 숙지가 1순위. 8초간 1.5 데미지를 상쇄하므로 타이밍 관리가 중요하다.",
         os.path.join(base_dir, "assets/images/puppeteer.png")),

        (3, "기계기술자", "생존자", "해독형",
         9, 3, 4, 4,
         "로봇 해독이 핵심 강점. 로봇 위치 선정을 잘못하면 오히려 어그로를 끌 수 있으니 주의.",
         os.path.join(base_dir, "assets/images/mechanic.png")),

        (4, "의사",       "생존자", "보조형",
         6, 9, 5, 7,
         "부상 치료 속도가 가장 빠른 캐릭터 중 하나. 자가 치료 가능 여부가 생존율을 크게 좌우.",
         os.path.join(base_dir, "assets/images/doctor.png")),

        (5, "포워드",       "생존자", "구원형",
         5, 5, 8, 9,
         "돌진 스킬로 감시자의 공격을 끊어낼 수 있다. 구출 타이밍을 정확히 계산해야 함.",
         os.path.join(base_dir, "assets/images/forward.png")),

        (6, "납관사",     "생존자", "해독형",
         8, 5, 6, 6,
         "관 시스템으로 팀원을 임시 보호 가능. 관 위치 선정이 승패를 가른다.",
         os.path.join(base_dir, "assets/images/embalmer.png")),

        (7, "선지자",     "생존자", "보조형",
         6, 8, 5, 6,
         "까마귀로 감시자 위치를 실시간 공유. 정보 공유 타이밍이 핵심 역할.",
         os.path.join(base_dir, "assets/images/seer.png")),

        (8, "공군",     "생존자", "보조형",
         5, 9, 5, 7,
         "일회성 총 아이템으로 감시자에게 긴 스턴효과를 줌.",
         os.path.join(base_dir, "assets/images/coordinator.png")),
    ]

    # ── 감시자 캐릭터 ──
    hunters = [
        (9,  "리퍼",  "감시자", "-",
         None, None, None, None,
         "안개 상태에서 순간이동. 생존자의 위치 파악을 최우선으로 해야 한다.",
         os.path.join(base_dir, "assets/images/jack.png")),

        (10, "사냥터지기",    "감시자", "-",
         None, None, None, None,
         "창틀 근처에 트랩을 배치하는 것이 기본 운영. 구출 시도를 철저히 차단.",
         os.path.join(base_dir, "assets/images/hell_ember.png")),
    ]

    for row in survivors + hunters:
        con.execute("""
            INSERT INTO Characters
              (char_id, name, faction, position,
               decode_score, support_score, kiting_score, rescue_score,
               operation_guide, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)

    # ── Character_Stats (세부 수치) ──
    stats = [
        # (char_id, run, walk, crawl, decode_t, gate_t, pallet_t, vault_t, heal_o, heal_s, chair_t)
        (1,  3.60, 2.00, 0.44, 81, 18, 0.73, 0.87, 21.43, 30, 60),
        (2,  3.80, 2.11, 0.44, 81, 18, 0.73, 0.87, 21.43, 30, 60),
        (3,  3.20, 1.80, 0.44, 70, 16, 0.73, 0.87, 21.43, 30, 60),
        (4,  3.60, 2.00, 0.44, 75, 18, 0.73, 0.87, 16.00, 22, 60),
        (5,  3.80, 2.11, 0.44, 81, 18, 0.73, 0.87, 21.43, 30, 55),
        (6,  3.60, 2.00, 0.44, 72, 18, 0.73, 0.87, 21.43, 30, 60),
        (7,  3.60, 2.00, 0.44, 81, 18, 0.73, 0.87, 21.43, 30, 60),
        (8,  3.60, 2.00, 0.44, 81, 18, 0.73, 0.87, 21.43, 30, 60),
    ]
    for s in stats:
        con.execute("""
            INSERT INTO Character_Stats VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, s)

    # ── Traits (특성 사전) ──
    traits = [
        (1, "루이",           "패시브"),   # 인형사 전용
        (2, "쓸모없는 피와 살", "디버프"),  # 인형사 전용
        (3, "그림 그리기",    "액티브"),   # 화가 전용
        (4, "로봇 해독",      "액티브"),   # 기계기술자 전용
        (5, "치료 전문가",    "패시브"),   # 의사 전용
        (6, "돌진",           "액티브"),   # 전위 전용
        (7, "임시 안치",      "액티브"),   # 방부사 전용
        (8, "까마귀 정찰",    "액티브"),   # 예언자 전용
        (9, "닻 포탈",        "액티브"),   # 조율사 전용
    ]
    for t in traits:
        con.execute("INSERT INTO Traits VALUES (?,?,?)", t)

    # ── Character_Traits (캐릭터↔특성 연결) ──
    char_traits = [
        # (char_id, trait_id, specific_value, warning_memo)
        (2, 1, "8초간 1.5 데미지 상쇄",
         "루이가 활성화 중에는 타인에게 치료를 받을 수 없음. "
         "연합 사냥 모드에서도 동일하게 적용되며, 진정제 사용 불가."),
        (2, 2, "타인 치료 속도 -30%",
         "다른 생존자를 치료할 때마다 서로의 공포치가 1/4 감소. "
         "치료한 생존자의 다음 치료 시간이 10% 증가하는 추가 패널티 존재."),
        (1, 3, "감시자 고착 최대 4초",
         "그림 완성 전에 감시자가 그림을 부수면 효과 발동 안 됨. "
         "감시자 동선을 미리 파악하고 그려야 효율이 극대화."),
        (3, 4, "해독 시간 -15%",
         "로봇이 폭발하면 주변 생존자에게 어그로가 집중되므로 "
         "로봇 위치를 팀원에게 알리는 소통이 필수."),
        (4, 5, "자가 치료 가능, 치료 속도 +20%",
         "치료 중 감시자에게 피격당하면 치료 게이지가 리셋됨. "
         "항상 탈출로를 확보한 상태에서 치료 시작."),
        (5, 6, "순간 돌진으로 감시자 공격 차단",
         "돌진 쿨타임 중에는 일반 생존자와 동일한 취약 상태. "
         "쿨타임을 파악한 감시자의 페이크 공격에 당하지 않도록 주의."),
        (6, 7, "사망 시 관에 15초 수납",
         "관 위치를 감시자가 알면 바로 지킬 수 있으므로 "
         "은밀한 위치에 설치하는 것이 중요."),
        (7, 8, "까마귀로 감시자 위치 30초 추적",
         "까마귀가 감시자에게 발각되면 즉시 파괴됨. "
         "까마귀를 너무 가까이 보내지 말 것."),
        (8, 9, "닻 포탈로 팀원 순간이동 지원",
         "닻이 배치된 상태에서 조율사가 의자에 묶이면 닻의 효과가 사라짐. "
         "자신의 생존을 최우선으로 해야 팀을 지원할 수 있음."),
    ]
    for ct in char_traits:
        con.execute("INSERT INTO Character_Traits VALUES (?,?,?,?)", ct)

    # ── Matchups (감시자 상성) ──
    matchups = [
        # (survivor_id, hunter_id, matchup_guide)
        (2, 9,
         "요셉(사진사) 상대 시 루이가 1.5 데미지를 막으므로 반피 생존자를 노리는 요셉에게 "
         "강력한 카운터가 됨. 단, 판이 어떻게 기울어지냐에 따라 유불리가 달라질 수 있음."),
        (2, 10,
         "지옥불의 화염 지대를 루이로 한 번 버틸 수 있어 유리. "
         "단, 루이 쿨타임 중에 화염 지대로 유도당하지 않도록 주의."),
        (1, 10,
         "그림을 이용해 지옥불의 이동 경로를 차단할 수 있음. "
         "의자 근처 트랩 위치를 미리 파악해 두는 것이 중요."),
        (5, 9,
         "돌진으로 요셉의 특수 공격을 차단 가능. "
         "단, 사진이 찍힌 상태에서의 순간이동에는 대응 불가."),
        (3, 10,
         "로봇이 트랩을 대신 밟아줄 수 있어 유리. "
         "로봇 폭발 범위에 팀원이 있으면 오히려 불리해질 수 있으니 위치 소통 필수."),
    ]
    for m in matchups:
        con.execute("INSERT INTO Matchups VALUES (?,?,?)", m)

    # ── Maps ──
    maps = [
        (1, "레오의 기억",  "지하실 생성 빈도가 높은 위험 맵. 중앙 해독기 견제가 핵심."),
        (2, "화이트샌드 정신병원", "넓은 복도 구조. 판자가 일직선으로 배치되어 판자 루프 활용이 중요."),
        (3, "레드 처치",    "폐쇄적인 실내 구조. 감시자의 시야가 제한되는 만큼 어그로 분산이 어려움."),
        (4, "달의 강",      "물 구역으로 인해 이동 경로가 제한적. 구출형은 스폰 선정이 매우 중요."),
        (5, "던전",         "복잡한 미로 구조. 해독기 위치를 빨리 파악하는 팀이 유리."),
    ]
    for mp in maps:
        con.execute("INSERT INTO Maps VALUES (?,?,?)", mp)

    # ── Position_Spawns (맵×포지션 스폰 가이드) ──
    spawns = [
        # (spawn_id, map_id, position, spawn_point, guide_memo)
        (1,  1, "구원형",  "6번 젠",
         "지하실이 자주 생성되는 위험 구역. 중앙 해독기를 1순위로 견제하며 "
         "아군의 첫 어그로 동선을 커버하세요."),
        (2,  1, "해독형",  "2번 젠",
         "초반 해독을 최대한 빠르게 진행. 감시자가 중앙으로 오면 즉시 이탈."),
        (3,  1, "견제형",  "중앙",
         "감시자를 초반에 어그로해서 해독 시간을 벌어주는 역할."),
        (4,  2, "구원형",  "복도 교차점",
         "복도를 활용해 구출 경로를 미리 파악해 두세요."),
        (5,  2, "해독형",  "1번 젠",
         "일직선 판자를 활용해 감시자를 최대한 오래 묶어두세요."),
        (6,  3, "구원형",  "입구 근처",
         "실내 구조 특성상 구출 후 탈출 경로가 매우 짧음. "
         "탈출 게이트 방향을 반드시 미리 파악."),
        (7,  4, "구원형",  "다리 근처",
         "물 구역을 통과하면 이동 속도가 감소하므로 육지 경로를 우선 활용."),
        (8,  4, "해독형",  "언덕 위 젠",
         "높은 지형 덕분에 감시자 접근을 미리 확인 가능. 안전하게 해독."),
        (9,  5, "구원형",  "미로 입구",
         "미로 구조라 구출 후 탈출이 어려울 수 있음. 탈출 경로를 사전에 외워두는 것 권장."),
        (10, 5, "해독형",  "중앙 방",
         "해독기 밀도가 높은 중앙을 빠르게 점령하면 승기를 잡을 수 있음."),
    ]
    for sp in spawns:
        con.execute("INSERT INTO Position_Spawns VALUES (?,?,?,?,?)", sp)

    print("[DB] 초기 샘플 데이터 삽입 완료.")


# ────────────────────────────────────────────────────────────
# 진입점
# ────────────────────────────────────────────────────────────

def init_db():
    """DB를 초기화하고 커넥션을 반환한다. 앱 시작 시 한 번만 호출."""
    con = get_conn()
    for ddl in DDL_STATEMENTS:
        con.execute(ddl)
    _seed_data(con)
    con.commit()
    print(f"[DB] 초기화 완료 → {DB_PATH}")
    return con
