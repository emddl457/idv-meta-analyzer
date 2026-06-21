"""
service.py
──────────────────────────────────────────────────────────────
Repository를 감싸는 Service 계층.
Controller(UI 쪽)에서 데이터 삽입·조회 요청이 오면 여기서
트랜잭션 처리, 입력 검증, 복합 INSERT 등의 비즈니스 로직을 처리한다.

설계서 7절 시퀀스 다이어그램의 'Service' 컴포넌트에 해당.
──────────────────────────────────────────────────────────────
"""

import duckdb
import pandas as pd
from database import get_conn
from repository import (
    CharacterRepository,
    CharacterStatsRepository,
    TraitRepository,
    CharacterTraitRepository,
    MatchupRepository,
    MapRepository,
    PositionSpawnRepository,
    IdentityJoinRepository,
)


# ──────────────────────────────────────────────────────────
# 싱글턴처럼 사용할 Repository 인스턴스들
# ──────────────────────────────────────────────────────────
_char_repo        = CharacterRepository()
_stats_repo       = CharacterStatsRepository()
_trait_repo       = TraitRepository()
_char_trait_repo  = CharacterTraitRepository()
_matchup_repo     = MatchupRepository()
_map_repo         = MapRepository()
_spawn_repo       = PositionSpawnRepository()
_join_repo        = IdentityJoinRepository()


# ════════════════════════════════════════════════════════════
# 조회 서비스
# ════════════════════════════════════════════════════════════

def search_characters(name: str = "", position: str = "전체") -> pd.DataFrame:
    """
    캐릭터 이름 검색 또는 포지션 필터 결과를 반환.
    - name이 있으면 이름 검색 우선
    - 없으면 position 필터 적용 (JOIN 조회)
    """
    if name.strip():
        # 이름 검색 시에는 단순 Characters 조회 후 별도로 특성 JOIN 추가
        df = _char_repo.find_by_name(name.strip())
        return df

    # 포지션 필터 → 3개 이상 테이블 JOIN 쿼리 실행
    return _join_repo.find_characters_with_traits_by_position(position)


def get_character_detail(char_id: int) -> dict:
    """
    단일 캐릭터의 기본 정보, 세부 스탯, 특성, 감시자 상성을 묶어서 반환.
    반환값: { "basic": DataFrame, "stats": DataFrame,
              "traits": DataFrame, "matchups": DataFrame }
    """
    basic    = _char_repo.find_by_id(char_id)
    stats    = _stats_repo.find_by_char_id(char_id)
    traits   = _char_trait_repo.find_by_char_id(char_id)
    matchups = _matchup_repo.find_by_survivor_id(char_id)
    return {"basic": basic, "stats": stats, "traits": traits, "matchups": matchups}


def get_spawn_guide(map_name: str, position: str) -> pd.DataFrame:
    """맵 + 포지션 조합으로 스폰 가이드를 반환 (Maps JOIN Position_Spawns)."""
    return _join_repo.find_spawn_guide_by_map_and_position(map_name, position)


def get_all_maps() -> pd.DataFrame:
    return _map_repo.find_all()


def get_all_traits() -> pd.DataFrame:
    return _trait_repo.find_all()


def get_all_characters() -> pd.DataFrame:
    return _char_repo.find_all()


def get_characters_with_traits(position: str = "전체") -> pd.DataFrame:
    """캐릭터 도감 메인 테이블용. Characters + Stats + Traits 3개 이상 JOIN."""
    return _join_repo.find_characters_with_traits_by_position(position)


def get_matchups_for_survivor(survivor_id: int) -> pd.DataFrame:
    return _join_repo.find_matchups_for_survivor(survivor_id)


# ════════════════════════════════════════════════════════════
# 삽입 서비스 (트랜잭션 보장)
# ════════════════════════════════════════════════════════════

def save_advanced_character(char_data: dict, stats_data: dict,
                             trait_data: dict | None = None) -> tuple[bool, str]:
    """
    설계서 7.1 시퀀스 – 신규 캐릭터 상세 데이터 삽입.
    Characters + Character_Stats + (선택적) Character_Traits를
    하나의 트랜잭션으로 묶어 원자적으로 처리.

    반환: (성공여부, 메시지)
    """
    # ① 캐릭터명 중복 체크
    existing = _char_repo.find_by_name(char_data["name"])
    if not existing.empty:
        return False, f"'{char_data['name']}' 캐릭터가 이미 존재합니다."

    # ② 트랜잭션 시작 – DuckDB는 autocommit 모드이므로
    #    직접 BEGIN / COMMIT / ROLLBACK 제어
    con = get_conn()
    try:
        con.execute("BEGIN TRANSACTION")

        # 새 char_id 계산
        max_id = con.execute(
            "SELECT COALESCE(MAX(char_id), 0) FROM Characters"
        ).fetchone()[0]
        new_id = max_id + 1

        # Characters INSERT
        con.execute("""
            INSERT INTO Characters
              (char_id, name, faction, position,
               decode_score, support_score, kiting_score, rescue_score,
               operation_guide, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            new_id,
            char_data.get("name"),
            char_data.get("faction"),
            char_data.get("position"),
            char_data.get("decode_score"),
            char_data.get("support_score"),
            char_data.get("kiting_score"),
            char_data.get("rescue_score"),
            char_data.get("operation_guide"),
            char_data.get("image_path", ""),
        ])

        # Character_Stats INSERT (세부 스탯이 있을 때만)
        if stats_data:
            con.execute("""
                INSERT INTO Character_Stats VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, [
                new_id,
                stats_data.get("run_speed_ms"),
                stats_data.get("walk_speed_ms"),
                stats_data.get("crawl_speed_ms"),
                stats_data.get("decode_time_s"),
                stats_data.get("gate_open_time_s"),
                stats_data.get("pallet_drop_time_s"),
                stats_data.get("vault_fast_time_s"),
                stats_data.get("heal_other_time_s"),
                stats_data.get("heal_self_time_s"),
                stats_data.get("chair_takeoff_time_s"),
            ])

        # Character_Traits INSERT (특성 정보가 있을 때만)
        if trait_data and trait_data.get("trait_id"):
            con.execute("""
                INSERT INTO Character_Traits VALUES (?, ?, ?, ?)
            """, [
                new_id,
                trait_data["trait_id"],
                trait_data.get("specific_value"),
                trait_data.get("warning_memo"),
            ])

        con.execute("COMMIT")
        con.close()
        return True, f"'{char_data['name']}' 캐릭터가 성공적으로 등록되었습니다!"

    except Exception as e:
        con.execute("ROLLBACK")
        con.close()
        return False, f"등록 중 오류 발생: {e}"


def save_spawn_guide(map_name: str, position: str,
                     spawn_point: str, guide_memo: str) -> tuple[bool, str]:
    """
    맵 스폰 가이드 추가.
    Maps가 이미 있으면 재사용, 없으면 새로 삽입.
    """
    con = get_conn()
    try:
        con.execute("BEGIN TRANSACTION")

        # 맵 존재 여부 확인
        row = con.execute(
            "SELECT map_id FROM Maps WHERE map_name = ?", [map_name]
        ).fetchone()

        if row:
            map_id = row[0]
        else:
            # 새 맵 삽입
            map_id = con.execute(
                "SELECT COALESCE(MAX(map_id),0)+1 FROM Maps"
            ).fetchone()[0]
            con.execute(
                "INSERT INTO Maps VALUES (?, ?, NULL)", [map_id, map_name]
            )

        # 중복 스폰 가이드 체크
        dup = con.execute("""
            SELECT spawn_id FROM Position_Spawns
            WHERE map_id=? AND position=?
        """, [map_id, position]).fetchone()
        if dup:
            con.execute("ROLLBACK")
            con.close()
            return False, f"'{map_name}' × '{position}' 가이드가 이미 존재합니다."

        spawn_id = con.execute(
            "SELECT COALESCE(MAX(spawn_id),0)+1 FROM Position_Spawns"
        ).fetchone()[0]
        con.execute("""
            INSERT INTO Position_Spawns VALUES (?,?,?,?,?)
        """, [spawn_id, map_id, position, spawn_point, guide_memo])

        con.execute("COMMIT")
        con.close()
        return True, "스폰 가이드가 등록되었습니다!"

    except Exception as e:
        con.execute("ROLLBACK")
        con.close()
        return False, f"등록 오류: {e}"


def delete_character(char_id: int) -> tuple[bool, str]:
    """캐릭터 삭제. CASCADE 설정으로 연관 Stats, Traits도 함께 삭제됨."""
    ok = _char_repo.delete(char_id)
    if ok:
        return True, "캐릭터가 삭제되었습니다."
    return False, "삭제에 실패했습니다."
