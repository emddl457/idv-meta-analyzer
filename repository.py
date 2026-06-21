"""
repository.py
──────────────────────────────────────────────────────────────
각 테이블의 CRUD + Join 조회를 담당하는 Repository 클래스 모음.
설계서 8절(Repository Interface 설계)과 1:1 대응됨.

구조:
  ICharacterRepository       → Characters 테이블
  ICharacterStatsRepository  → Character_Stats 테이블
  ITraitRepository           → Traits 테이블
  ICharacterTraitRepository  → Character_Traits 교차 테이블
  IMatchupRepository         → Matchups 교차 테이블
  IMapRepository             → Maps 테이블
  IPositionSpawnRepository   → Position_Spawns 테이블
  IIdentityJoinRepository    → 3개 이상 테이블 JOIN 전용
──────────────────────────────────────────────────────────────
"""

from abc import ABC, abstractmethod
import pandas as pd
import duckdb
from database import get_conn


# ════════════════════════════════════════════════════════════
# 8.1  Characters 테이블 인터페이스
# ════════════════════════════════════════════════════════════

class ICharacterRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_all(self) -> pd.DataFrame: ...
    @abstractmethod
    def find_by_id(self, char_id: int) -> pd.DataFrame: ...
    @abstractmethod
    def find_by_name(self, name: str) -> pd.DataFrame: ...
    @abstractmethod
    def find_by_faction(self, faction: str) -> pd.DataFrame: ...
    @abstractmethod
    def find_by_position(self, position: str) -> pd.DataFrame: ...
    @abstractmethod
    def update(self, char_id: int, data: dict) -> bool: ...
    @abstractmethod
    def delete(self, char_id: int) -> bool: ...


class CharacterRepository(ICharacterRepository):
    """실제 DuckDB Characters 테이블을 조작하는 구현체."""

    def save(self, data: dict) -> bool:
        """새 캐릭터를 Characters 테이블에 삽입."""
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Characters
                  (char_id, name, faction, position,
                   decode_score, support_score, kiting_score, rescue_score,
                   operation_guide, image_path)
                VALUES (
                  (SELECT COALESCE(MAX(char_id),0)+1 FROM Characters),
                  ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                data.get("name"),
                data.get("faction"),
                data.get("position"),
                data.get("decode_score"),
                data.get("support_score"),
                data.get("kiting_score"),
                data.get("rescue_score"),
                data.get("operation_guide"),
                data.get("image_path", ""),
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterRepository.save] Error: {e}")
            return False

    def find_all(self) -> pd.DataFrame:
        """전체 캐릭터 목록 반환."""
        con = get_conn()
        df = con.execute("SELECT * FROM Characters ORDER BY faction, position").df()
        con.close()
        return df

    def find_by_id(self, char_id: int) -> pd.DataFrame:
        con = get_conn()
        df = con.execute("SELECT * FROM Characters WHERE char_id = ?", [char_id]).df()
        con.close()
        return df

    def find_by_name(self, name: str) -> pd.DataFrame:
        """이름 부분 일치 검색 (LIKE 사용)."""
        con = get_conn()
        df = con.execute(
            "SELECT * FROM Characters WHERE name LIKE ?", [f"%{name}%"]
        ).df()
        con.close()
        return df

    def find_by_faction(self, faction: str) -> pd.DataFrame:
        con = get_conn()
        df = con.execute(
            "SELECT * FROM Characters WHERE faction = ?", [faction]
        ).df()
        con.close()
        return df

    def find_by_position(self, position: str) -> pd.DataFrame:
        con = get_conn()
        if position == "전체":
            df = con.execute(
                "SELECT * FROM Characters WHERE faction = '생존자' ORDER BY position"
            ).df()
        else:
            df = con.execute(
                "SELECT * FROM Characters WHERE position = ? ORDER BY name",
                [position]
            ).df()
        con.close()
        return df

    def update(self, char_id: int, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                UPDATE Characters SET
                  name = ?, faction = ?, position = ?,
                  decode_score = ?, support_score = ?,
                  kiting_score = ?, rescue_score = ?,
                  operation_guide = ?, image_path = ?
                WHERE char_id = ?
            """, [
                data["name"], data["faction"], data["position"],
                data["decode_score"], data["support_score"],
                data["kiting_score"], data["rescue_score"],
                data["operation_guide"], data.get("image_path", ""),
                char_id,
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterRepository.update] Error: {e}")
            return False

    def delete(self, char_id: int) -> bool:
        try:
            con = get_conn()
            con.execute("DELETE FROM Characters WHERE char_id = ?", [char_id])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterRepository.delete] Error: {e}")
            return False

    def get_max_id(self) -> int:
        con = get_conn()
        result = con.execute("SELECT COALESCE(MAX(char_id), 0) FROM Characters").fetchone()[0]
        con.close()
        return result


# ════════════════════════════════════════════════════════════
# 8.2  Character_Stats 테이블 인터페이스
# ════════════════════════════════════════════════════════════

class ICharacterStatsRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_by_char_id(self, char_id: int) -> pd.DataFrame: ...
    @abstractmethod
    def update(self, char_id: int, data: dict) -> bool: ...
    @abstractmethod
    def delete(self, char_id: int) -> bool: ...


class CharacterStatsRepository(ICharacterStatsRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Character_Stats VALUES
                  (?,?,?,?,?,?,?,?,?,?,?)
            """, [
                data["char_id"],
                data.get("run_speed_ms"),
                data.get("walk_speed_ms"),
                data.get("crawl_speed_ms"),
                data.get("decode_time_s"),
                data.get("gate_open_time_s"),
                data.get("pallet_drop_time_s"),
                data.get("vault_fast_time_s"),
                data.get("heal_other_time_s"),
                data.get("heal_self_time_s"),
                data.get("chair_takeoff_time_s"),
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterStatsRepository.save] Error: {e}")
            return False

    def find_by_char_id(self, char_id: int) -> pd.DataFrame:
        con = get_conn()
        df = con.execute(
            "SELECT * FROM Character_Stats WHERE char_id = ?", [char_id]
        ).df()
        con.close()
        return df

    def update(self, char_id: int, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                UPDATE Character_Stats SET
                  run_speed_ms=?, walk_speed_ms=?, crawl_speed_ms=?,
                  decode_time_s=?, gate_open_time_s=?,
                  pallet_drop_time_s=?, vault_fast_time_s=?,
                  heal_other_time_s=?, heal_self_time_s=?, chair_takeoff_time_s=?
                WHERE char_id=?
            """, [
                data.get("run_speed_ms"), data.get("walk_speed_ms"),
                data.get("crawl_speed_ms"), data.get("decode_time_s"),
                data.get("gate_open_time_s"), data.get("pallet_drop_time_s"),
                data.get("vault_fast_time_s"), data.get("heal_other_time_s"),
                data.get("heal_self_time_s"), data.get("chair_takeoff_time_s"),
                char_id,
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterStatsRepository.update] Error: {e}")
            return False

    def delete(self, char_id: int) -> bool:
        try:
            con = get_conn()
            con.execute("DELETE FROM Character_Stats WHERE char_id=?", [char_id])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterStatsRepository.delete] Error: {e}")
            return False


# ════════════════════════════════════════════════════════════
# 8.3  Traits & Character_Traits 인터페이스
# ════════════════════════════════════════════════════════════

class ITraitRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_all(self) -> pd.DataFrame: ...
    @abstractmethod
    def update(self, trait_id: int, data: dict) -> bool: ...
    @abstractmethod
    def delete(self, trait_id: int) -> bool: ...


class TraitRepository(ITraitRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Traits VALUES
                  ((SELECT COALESCE(MAX(trait_id),0)+1 FROM Traits), ?, ?)
            """, [data["trait_name"], data.get("trait_category")])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[TraitRepository.save] Error: {e}")
            return False

    def find_all(self) -> pd.DataFrame:
        con = get_conn()
        df = con.execute("SELECT * FROM Traits ORDER BY trait_category, trait_name").df()
        con.close()
        return df

    def update(self, trait_id: int, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute(
                "UPDATE Traits SET trait_name=?, trait_category=? WHERE trait_id=?",
                [data["trait_name"], data.get("trait_category"), trait_id]
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[TraitRepository.update] Error: {e}")
            return False

    def delete(self, trait_id: int) -> bool:
        try:
            con = get_conn()
            con.execute("DELETE FROM Traits WHERE trait_id=?", [trait_id])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[TraitRepository.delete] Error: {e}")
            return False


class ICharacterTraitRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_by_char_id(self, char_id: int) -> pd.DataFrame: ...
    @abstractmethod
    def delete(self, char_id: int, trait_id: int) -> bool: ...


class CharacterTraitRepository(ICharacterTraitRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Character_Traits VALUES (?,?,?,?)
            """, [
                data["char_id"], data["trait_id"],
                data.get("specific_value"), data.get("warning_memo"),
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterTraitRepository.save] Error: {e}")
            return False

    def find_by_char_id(self, char_id: int) -> pd.DataFrame:
        con = get_conn()
        df = con.execute("""
            SELECT t.trait_name, t.trait_category,
                   ct.specific_value, ct.warning_memo
            FROM   Character_Traits ct
            JOIN   Traits t ON ct.trait_id = t.trait_id
            WHERE  ct.char_id = ?
        """, [char_id]).df()
        con.close()
        return df

    def delete(self, char_id: int, trait_id: int) -> bool:
        try:
            con = get_conn()
            con.execute(
                "DELETE FROM Character_Traits WHERE char_id=? AND trait_id=?",
                [char_id, trait_id]
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[CharacterTraitRepository.delete] Error: {e}")
            return False


# ════════════════════════════════════════════════════════════
# 8.4  Matchups 인터페이스
# ════════════════════════════════════════════════════════════

class IMatchupRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_by_survivor_id(self, survivor_id: int) -> pd.DataFrame: ...
    @abstractmethod
    def delete(self, survivor_id: int, hunter_id: int) -> bool: ...


class MatchupRepository(IMatchupRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute(
                "INSERT INTO Matchups VALUES (?,?,?)",
                [data["survivor_id"], data["hunter_id"], data["matchup_guide"]]
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[MatchupRepository.save] Error: {e}")
            return False

    def find_by_survivor_id(self, survivor_id: int) -> pd.DataFrame:
        con = get_conn()
        df = con.execute("""
            SELECT h.name AS 감시자, m.matchup_guide AS 상성_가이드
            FROM   Matchups m
            JOIN   Characters h ON m.hunter_id = h.char_id
            WHERE  m.survivor_id = ?
        """, [survivor_id]).df()
        con.close()
        return df

    def delete(self, survivor_id: int, hunter_id: int) -> bool:
        try:
            con = get_conn()
            con.execute(
                "DELETE FROM Matchups WHERE survivor_id=? AND hunter_id=?",
                [survivor_id, hunter_id]
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[MatchupRepository.delete] Error: {e}")
            return False


# ════════════════════════════════════════════════════════════
# 8.5  Maps & Position_Spawns 인터페이스
# ════════════════════════════════════════════════════════════

class IMapRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_all(self) -> pd.DataFrame: ...
    @abstractmethod
    def delete(self, map_id: int) -> bool: ...


class MapRepository(IMapRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Maps VALUES
                  ((SELECT COALESCE(MAX(map_id),0)+1 FROM Maps), ?, ?)
            """, [data["map_name"], data.get("description")])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[MapRepository.save] Error: {e}")
            return False

    def find_all(self) -> pd.DataFrame:
        con = get_conn()
        df = con.execute("SELECT * FROM Maps ORDER BY map_name").df()
        con.close()
        return df

    def delete(self, map_id: int) -> bool:
        try:
            con = get_conn()
            con.execute("DELETE FROM Maps WHERE map_id=?", [map_id])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[MapRepository.delete] Error: {e}")
            return False


class IPositionSpawnRepository(ABC):
    @abstractmethod
    def save(self, data: dict) -> bool: ...
    @abstractmethod
    def find_by_map_id(self, map_id: int) -> pd.DataFrame: ...
    @abstractmethod
    def update(self, spawn_id: int, data: dict) -> bool: ...
    @abstractmethod
    def delete(self, spawn_id: int) -> bool: ...


class PositionSpawnRepository(IPositionSpawnRepository):

    def save(self, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                INSERT INTO Position_Spawns VALUES
                  ((SELECT COALESCE(MAX(spawn_id),0)+1 FROM Position_Spawns),
                   ?, ?, ?, ?)
            """, [
                data["map_id"], data["position"],
                data["spawn_point"], data.get("guide_memo"),
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[PositionSpawnRepository.save] Error: {e}")
            return False

    def find_by_map_id(self, map_id: int) -> pd.DataFrame:
        con = get_conn()
        df = con.execute(
            "SELECT * FROM Position_Spawns WHERE map_id=? ORDER BY position",
            [map_id]
        ).df()
        con.close()
        return df

    def update(self, spawn_id: int, data: dict) -> bool:
        try:
            con = get_conn()
            con.execute("""
                UPDATE Position_Spawns SET
                  map_id=?, position=?, spawn_point=?, guide_memo=?
                WHERE spawn_id=?
            """, [
                data["map_id"], data["position"],
                data["spawn_point"], data.get("guide_memo"), spawn_id,
            ])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[PositionSpawnRepository.update] Error: {e}")
            return False

    def delete(self, spawn_id: int) -> bool:
        try:
            con = get_conn()
            con.execute("DELETE FROM Position_Spawns WHERE spawn_id=?", [spawn_id])
            con.commit()
            con.close()
            return True
        except Exception as e:
            print(f"[PositionSpawnRepository.delete] Error: {e}")
            return False


# ════════════════════════════════════════════════════════════
# 8.6  통합 JOIN 조회 전용 인터페이스
# ════════════════════════════════════════════════════════════

class IIdentityJoinRepository(ABC):
    @abstractmethod
    def find_characters_with_traits_by_position(self, position: str) -> pd.DataFrame: ...
    @abstractmethod
    def find_spawn_guide_by_map_and_position(
        self, map_name: str, position: str
    ) -> pd.DataFrame: ...
    @abstractmethod
    def find_full_character_detail(self, char_id: int) -> pd.DataFrame: ...


class IdentityJoinRepository(IIdentityJoinRepository):
    """
    설계서 3.4 / 3.5 Use Case의 핵심 쿼리를 담당.
    Characters, Character_Stats, Traits, Character_Traits,
    Maps, Position_Spawns 등 3개 이상 테이블을 JOIN해서 반환.
    """

    def find_characters_with_traits_by_position(self, position: str) -> pd.DataFrame:
        """
        포지션별 캐릭터 + 특성 + 주의사항 통합 조회.
        Characters LEFT JOIN Character_Stats
                   LEFT JOIN Character_Traits
                   LEFT JOIN Traits
        → 특성이 없는 캐릭터도 기본 스탯과 함께 출력 (LEFT JOIN)
        """
        con = get_conn()
        if position == "전체":
            where_clause = "WHERE c.faction = '생존자'"
            params = []
        else:
            where_clause = "WHERE c.position = ?"
            params = [position]

        df = con.execute(f"""
            SELECT
                c.name         AS 캐릭터명,
                c.position     AS 포지션,
                c.decode_score AS 해독,
                c.support_score AS 보조,
                c.kiting_score  AS 견제,
                c.rescue_score  AS 구원,
                cs.run_speed_ms     AS 달리기속도,
                cs.decode_time_s    AS 해독시간,
                cs.heal_other_time_s AS 타인치료,
                t.trait_name        AS 특성명,
                ct.specific_value   AS 특성수치,
                ct.warning_memo     AS 주의사항,
                c.image_path        AS 이미지경로,
                c.char_id           AS char_id
            FROM Characters c
            LEFT JOIN Character_Stats   cs ON c.char_id = cs.char_id
            LEFT JOIN Character_Traits  ct ON c.char_id = ct.char_id
            LEFT JOIN Traits             t ON ct.trait_id = t.trait_id
            {where_clause}
            ORDER BY c.position, c.name, t.trait_name
        """, params).df()
        con.close()
        return df

    def find_spawn_guide_by_map_and_position(
        self, map_name: str, position: str
    ) -> pd.DataFrame:
        """
        맵 × 포지션별 스폰 가이드 조회.
        Maps JOIN Position_Spawns (2개 테이블)
        """
        con = get_conn()
        df = con.execute("""
            SELECT
                m.map_name   AS 맵이름,
                m.description AS 맵설명,
                ps.position   AS 포지션,
                ps.spawn_point AS 추천스폰,
                ps.guide_memo  AS 가이드메모
            FROM Position_Spawns ps
            JOIN Maps m ON ps.map_id = m.map_id
            WHERE m.map_name = ? AND ps.position = ?
        """, [map_name, position]).df()
        con.close()
        return df

    def find_full_character_detail(self, char_id: int) -> pd.DataFrame:
        """
        단일 캐릭터의 전체 상세 정보.
        Characters, Character_Stats, Character_Traits, Traits,
        Matchups 5개 테이블을 조합.
        """
        con = get_conn()
        df = con.execute("""
            SELECT
                c.name, c.faction, c.position,
                c.decode_score, c.support_score,
                c.kiting_score, c.rescue_score,
                c.operation_guide, c.image_path,
                cs.run_speed_ms, cs.walk_speed_ms,
                cs.decode_time_s, cs.gate_open_time_s,
                cs.pallet_drop_time_s, cs.vault_fast_time_s,
                cs.heal_other_time_s, cs.heal_self_time_s,
                cs.chair_takeoff_time_s,
                t.trait_name, t.trait_category,
                ct.specific_value, ct.warning_memo
            FROM Characters c
            LEFT JOIN Character_Stats  cs ON c.char_id = cs.char_id
            LEFT JOIN Character_Traits ct ON c.char_id = ct.char_id
            LEFT JOIN Traits            t ON ct.trait_id = t.trait_id
            WHERE c.char_id = ?
        """, [char_id]).df()
        con.close()
        return df

    def find_matchups_for_survivor(self, survivor_id: int) -> pd.DataFrame:
        """감시자 상성 정보 조회. Matchups JOIN Characters."""
        con = get_conn()
        df = con.execute("""
            SELECT
                h.name          AS 감시자,
                m.matchup_guide AS 상성가이드
            FROM Matchups m
            JOIN Characters h ON m.hunter_id = h.char_id
            WHERE m.survivor_id = ?
        """, [survivor_id]).df()
        con.close()
        return df
