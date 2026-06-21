"""
main.py
──────────────────────────────────────────────────────────────
IDV Meta-Analyzer – 제5인격 실전 메타 백과사전
Flet 기반 데스크톱 GUI 메인 엔트리포인트.

화면 구성:
  ① 캐릭터 도감  – 포지션 필터 + 이름 검색 + JOIN 결과 테이블
  ② 데이터 삽입  – 신규 캐릭터 폼 (Characters + Stats + Traits 트랜잭션)
  ③ 맵 가이드   – 맵×포지션 선택 → 스폰 가이드 + 추가 폼
──────────────────────────────────────────────────────────────
"""
import os
import flet as ft
import pandas as pd 
from database import init_db
import service

# ── 앱 공통 색상 팔레트 ──────────────────────────────────────
DARK_BG      = "#1A1A2E"   # 전체 배경
SIDEBAR_BG   = "#16213E"   # 사이드바 배경
CARD_BG      = "#0F3460"   # 카드 배경
ACCENT       = "#E94560"   # 강조색 (경고/선택)
ACCENT_SOFT  = "#533483"   # 부드러운 포인트
TEXT_MAIN    = "#EAEAEA"   # 기본 텍스트
TEXT_SUB     = "#A8B2C1"   # 서브 텍스트
SUCCESS      = "#4CAF50"
WARNING      = "#FF9800"

POSITIONS = ["전체", "구원형", "해독형", "견제형", "보조형"]
MAP_NAMES  = ["레오의 기억", "화이트샌드 정신병원", "붉은성당", "달빛강공원", "군수공장"]


# ════════════════════════════════════════════════════════════
#  헬퍼 – 재사용 컴포넌트
# ════════════════════════════════════════════════════════════

def nav_button(label: str, icon, selected: bool, on_click) -> ft.Container:
    """사이드바 네비게이션 버튼."""
    return ft.Container(
        content=ft.Row([
            ft.Icon(icon, color=ACCENT if selected else TEXT_SUB, size=18),
            ft.Text(label, color=ACCENT if selected else TEXT_SUB,
                    size=13, weight=ft.FontWeight.BOLD if selected else None),
        ], spacing=10),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border_radius=8,
        bgcolor=ACCENT_SOFT + "55" if selected else "transparent",
        on_click=on_click,
        ink=True,
        animate=ft.animation.Animation(200),
    )


def score_bar(score: int, max_val: int = 10) -> ft.Row:
    """능력치 점수를 시각적 바 형태로 표시."""
    filled = int(score or 0)
    bars = []
    for i in range(max_val):
        bars.append(ft.Container(
            width=10, height=8, border_radius=2,
            bgcolor=ACCENT if i < filled else TEXT_SUB + "33",
        ))
    return ft.Row(bars + [ft.Text(f" {filled}/{max_val}",
                                   color=TEXT_SUB, size=11)],
                  spacing=2)


def section_title(text: str) -> ft.Text:
    return ft.Text(text, size=13, color=TEXT_SUB,
                   weight=ft.FontWeight.BOLD)


def stat_chip(label: str, value: str) -> ft.Container:
    """스탯 하나를 작은 칩 형태로 표시."""
    return ft.Container(
        content=ft.Column([
            ft.Text(label, size=10, color=TEXT_SUB),
            ft.Text(str(value) if value is not None else "-",
                    size=12, color=TEXT_MAIN, weight=ft.FontWeight.BOLD),
        ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=SIDEBAR_BG,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
    )


def warning_dialog(page: ft.Page, title: str, content: str):
    """경고 팝업 – 설계서 3.6 Use Case 대응."""
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ACCENT, size=22),
            ft.Text(f"  ⚠ 주의사항 – {title}",
                    color=ACCENT, weight=ft.FontWeight.BOLD, size=14),
        ]),
        content=ft.Container(
            content=ft.Text(content, color=TEXT_MAIN, size=13, selectable=True),
            bgcolor=DARK_BG, border_radius=8,
            padding=16, width=480,
        ),
        actions=[
            ft.TextButton("닫기", on_click=lambda _: close_dlg(page, dlg),
                          style=ft.ButtonStyle(color=ACCENT)),
        ],
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    page.dialog = dlg
    dlg.open = True
    page.update()


def close_dlg(page: ft.Page, dlg: ft.AlertDialog):
    dlg.open = False
    page.update()


def snack(page: ft.Page, msg: str, success: bool = True):
    """간단한 토스트 메시지."""
    page.snack_bar = ft.SnackBar(
        content=ft.Text(msg, color="white"),
        bgcolor=SUCCESS if success else ACCENT,
        duration=2500,
    )
    page.snack_bar.open = True
    page.update()


# ════════════════════════════════════════════════════════════
#  ① 캐릭터 도감 화면
# ════════════════════════════════════════════════════════════

def build_encyclopedia_view(page: ft.Page) -> ft.Column:
    """
    설계서 4.① 메인 화면 – 포지션 필터 + 이름 검색 + 결과 테이블.
    3개 이상 테이블 JOIN 결과를 DataTable로 표출.
    """
    search_field = ft.TextField(
        hint_text="캐릭터 이름 검색...",
        border_color=ACCENT_SOFT, color=TEXT_MAIN,
        hint_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_radius=8,
        height=38, text_size=13,
        expand=True,
    )

    # 결과를 담을 ListView (스크롤 가능)
    result_area = ft.ListView(expand=True, spacing=8, padding=4)

    current_pos = ["전체"]

    def render_rows(df):
        """DataFrame을 카드 형태 행으로 변환."""
        result_area.controls.clear()

        if df.empty:
            result_area.controls.append(
                ft.Container(
                    content=ft.Text("해당 캐릭터 정보를 찾을 수 없습니다.",
                                    color=TEXT_SUB, size=13),
                    alignment=ft.Alignment.CENTER, padding=40,
                )
            )
            page.update()
            return

        # 이름 검색 결과는 컬럼이 다름 → 기본 카드만 표시
        is_basic = "name" in df.columns and "특성명" not in df.columns

        # 같은 캐릭터 데이터가 특성별로 여러 행일 수 있어서 이름 기준으로 그룹핑
        seen_chars: dict = {}  # char_id or name → 카드 인덱스
        cards: list = []

        for _, row in df.iterrows():
            char_name = row.get("캐릭터명") or row.get("name", "?")
            char_id   = row.get("char_id") or row.get("char_id")
            img_path  = row.get("이미지경로") or row.get("image_path", "")
            pos_val   = row.get("포지션") or row.get("position", "-")

            key = char_name
            if key not in seen_chars:
                # 캐릭터 기본 정보 카드 생성
                img_ctrl = (
                    ft.Image(src=img_path, width=56, height=56,
                             fit="cover", border_radius=28)
                    if img_path and os.path.exists(img_path)
                    else ft.Container(
                        width=56, height=56, border_radius=28,
                        bgcolor=ACCENT_SOFT,
                        content=ft.Text(char_name[0], color="white",
                                        size=22, weight=ft.FontWeight.BOLD),
                        alignment=ft.Alignment.CENTER,
                    )
                )

                # 능력치 점수 (기본 조회 vs JOIN 조회 컬럼명 다름)
                dec = row.get("해독") or row.get("decode_score")
                sup = row.get("보조") or row.get("support_score")
                kit = row.get("견제") or row.get("kiting_score")
                rsc = row.get("구원") or row.get("rescue_score")

                score_section = ft.Column([
                    ft.Row([
                        ft.Text("해독", color=TEXT_SUB, size=11, width=28),
                        score_bar(int(dec) if dec else 0),
                    ]),
                    ft.Row([
                        ft.Text("보조", color=TEXT_SUB, size=11, width=28),
                        score_bar(int(sup) if sup else 0),
                    ]),
                    ft.Row([
                        ft.Text("견제", color=TEXT_SUB, size=11, width=28),
                        score_bar(int(kit) if kit else 0),
                    ]),
                    ft.Row([
                        ft.Text("구원", color=TEXT_SUB, size=11, width=28),
                        score_bar(int(rsc) if rsc else 0),
                    ]),
                ], spacing=3) if (dec or sup or kit or rsc) else ft.Container()

                # 세부 스탯 칩 (JOIN 결과에만 있음)
                stats_row = None
                if not is_basic and "달리기속도" in df.columns:
                    run  = row.get("달리기속도")
                    dec_t = row.get("해독시간")
                    heal = row.get("타인치료")
                    if run or dec_t or heal:
                        stats_row = ft.Row([
                            stat_chip("달리기", f"{run}m/s" if run else "-"),
                            stat_chip("해독",   f"{dec_t}s" if dec_t else "-"),
                            stat_chip("타인치료", f"{heal}s" if heal else "-"),
                        ], spacing=6, wrap=True)

                traits_col = ft.Column([], spacing=4)  # 특성 태그 추가될 자리

                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            img_ctrl,
                            ft.Column([
                                ft.Row([
                                    ft.Text(char_name, color=TEXT_MAIN, size=15,
                                            weight=ft.FontWeight.BOLD),
                                    ft.Container(
                                        content=ft.Text(pos_val, color="white", size=10),
                                        bgcolor=ACCENT_SOFT, border_radius=4,
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    ),
                                ], spacing=8),
                                score_section,
                                stats_row or ft.Container(height=0),
                            ], expand=True, spacing=4),
                        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                        traits_col,
                    ], spacing=8),
                    bgcolor=CARD_BG, border_radius=10,
                    padding=14,
                )
                seen_chars[key] = {
                    "card": card,
                    "traits_col": traits_col,
                    "char_id": char_id,
                }
                cards.append(card)

            # 특성 태그 추가 (같은 캐릭터의 여러 특성 행 처리)
            trait_name = row.get("특성명")
            warning    = row.get("주의사항")
            if trait_name and str(trait_name) != "nan":
                target_col = seen_chars[key]["traits_col"]
                tid = seen_chars[key]["char_id"]

                def make_warn_btn(tn=trait_name, wm=warning):
                    """클로저로 각 특성의 경고창 버튼 생성."""
                    if not wm or str(wm) == "nan":
                        return ft.Text(f"• {tn}", color=TEXT_SUB, size=12)
                    return ft.TextButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ERROR_OUTLINE, color=ACCENT, size=14),
                            ft.Text(tn, color=ACCENT, size=12),
                        ], spacing=4),
                        on_click=lambda _, n=tn, w=wm: warning_dialog(page, n, w),
                        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
                    )

                target_col.controls.append(make_warn_btn())

        for c in cards:
            result_area.controls.append(c)
        page.update()

    def do_search(e=None):
        name = search_field.value or ""
        pos  = current_pos[0]
        df = service.search_characters(name=name, position=pos)
        render_rows(df)
        df = service.search_characters(name=name, position=pos)
        render_rows(df)

    search_field.on_submit = do_search

    # 포지션 필터 버튼 행
    pos_buttons = []
    filter_row_ref = ft.Ref[ft.Row]()

    def make_pos_btn(p):
        def on_click(_):
            current_pos[0] = p
            search_field.value = ""
            do_search()
            search_field.value = ""
            do_search()
            # 버튼 선택 상태 갱신
            for btn in pos_buttons:
                btn.bgcolor = "transparent"
                btn.border = ft.Border.all(1, TEXT_SUB + "55")
            pos_buttons[POSITIONS.index(p)].bgcolor = ACCENT + "33"
            pos_buttons[POSITIONS.index(p)].border = ft.Border.all(1, ACCENT)
            page.update()

        btn = ft.Container(
            content=ft.Text(p, color=TEXT_MAIN, size=12),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=16,
            bgcolor=ACCENT + "33" if p == "전체" else "transparent",
            border=ft.Border.all(1, ACCENT if p == "전체" else TEXT_SUB + "55"),
            on_click=on_click,
            ink=True,
        )
        pos_buttons.append(btn)
        return btn

    filter_row = ft.Row(
        [make_pos_btn(p) for p in POSITIONS],
        spacing=8, wrap=True,
    )

    # 검색 버튼
    search_btn = ft.IconButton(
        icon=ft.Icons.SEARCH, icon_color=ACCENT,
        tooltip="검색", on_click=do_search,
    )

    # 최초 로드
    do_search()

    import pandas as pd

    return ft.Column([
        ft.Text("캐릭터 도감", size=20, color=TEXT_MAIN, weight=ft.FontWeight.BOLD),
        ft.Text("포지션 필터 또는 이름으로 검색 · 주의사항 버튼 클릭 시 경고창 표시",
                color=TEXT_SUB, size=12),
        ft.Divider(color=ACCENT_SOFT + "44"),
        ft.Row([search_field, search_btn], spacing=8),
        filter_row,
        ft.Container(height=4),
        ft.Container(content=result_area, expand=True),
    ], spacing=10, expand=True)


# ════════════════════════════════════════════════════════════
#  ② 데이터 삽입 화면
# ════════════════════════════════════════════════════════════

def build_insert_view(page: ft.Page) -> ft.Column:
    """
    설계서 4.② 데이터 삽입 화면 – Characters + Stats + Traits 동시 삽입.
    ScrollMode.AUTO로 긴 폼을 스크롤 가능하게 처리.
    """

    def tf(label, hint="", width=None, kb_type=ft.KeyboardType.TEXT):
        """공통 텍스트 필드 생성 헬퍼."""
        return ft.TextField(
            label=label, hint_text=hint,
            color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
            border_color=ACCENT_SOFT, focused_border_color=ACCENT,
            bgcolor=SIDEBAR_BG, border_radius=8,
            text_size=13, height=46,
            width=width, keyboard_type=kb_type,
            input_filter=ft.NumbersOnlyInputFilter()
            if kb_type == ft.KeyboardType.NUMBER else None,
        )

    # ── 기본 정보 필드 ──
    f_name      = tf("캐릭터명 *")
    f_faction   = ft.Dropdown(
        label="진영 *", options=[
            ft.dropdown.Option("생존자"), ft.dropdown.Option("감시자"),
        ],
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )
    f_position  = ft.Dropdown(
        label="포지션 *",
        options=[ft.dropdown.Option(p) for p in ["구원형","해독형","견제형","보조형","-"]],
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )

    # ── 능력치 슬라이더 ──
    def make_slider(label, ref_val):
        slider = ft.Slider(
            min=1, max=10, divisions=9, value=5,
            active_color=ACCENT, inactive_color=TEXT_SUB + "33",
            label="{value}",
        )
        val_text = ft.Text("5", color=ACCENT, size=13,
                            weight=ft.FontWeight.BOLD, width=24)

        def on_change(e):
            val_text.value = str(int(slider.value))
            page.update()

        slider.on_change = on_change
        return slider, val_text

    slider_dec, val_dec = make_slider("해독", None)
    slider_sup, val_sup = make_slider("보조", None)
    slider_kit, val_kit = make_slider("견제", None)
    slider_rsc, val_rsc = make_slider("구원", None)

    # ── 세부 스탯 필드 ──
    NUM = ft.KeyboardType.NUMBER
    f_run   = tf("달리기(m/s)", "3.6",  kb_type=NUM)
    f_walk  = tf("걷기(m/s)",   "2.0",  kb_type=NUM)
    f_crawl = tf("기어가기",    "0.44", kb_type=NUM)
    f_dec_t = tf("해독시간(s)", "81",   kb_type=NUM)
    f_gate  = tf("대문(s)",     "18",   kb_type=NUM)
    f_pal   = tf("판자(s)",     "0.73", kb_type=NUM)
    f_vlt   = tf("창틀빠름(s)", "0.87", kb_type=NUM)
    f_ho    = tf("타인치료(s)", "21.43",kb_type=NUM)
    f_hs    = tf("자가치료(s)", "30",   kb_type=NUM)
    f_chair = tf("의자이륙(s)", "60",   kb_type=NUM)

    # ── 특성 연결 ──
    traits_df = service.get_all_traits()
    trait_opts = [ft.dropdown.Option("없음")]
    for _, r in traits_df.iterrows():
        trait_opts.append(ft.dropdown.Option(
            key=str(r["trait_id"]),
            text=f"{r['trait_name']} ({r['trait_category']})",
        ))

    f_trait = ft.Dropdown(
        label="연결할 특성",
        options=trait_opts,
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
        value="없음",
    )
    f_trait_val  = tf("특성 수치 (예: 8초간 1.5 데미지 상쇄)")
    f_warning    = ft.TextField(
        label="주의사항 메모",
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        border_color=ACCENT_SOFT, focused_border_color=ACCENT,
        bgcolor=SIDEBAR_BG, border_radius=8,
        text_size=13, multiline=True, min_lines=2, max_lines=4,
    )

    # ── 운영 가이드 ──
    f_guide = ft.TextField(
        label="운영 및 매커니즘 가이드",
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        border_color=ACCENT_SOFT, focused_border_color=ACCENT,
        bgcolor=SIDEBAR_BG, border_radius=8,
        text_size=13, multiline=True, min_lines=3, max_lines=6,
    )

    # 이미지 경로 입력 (선택)
    f_img = tf("이미지 파일 경로 (선택)")

    result_text = ft.Text("", color=TEXT_SUB, size=12)

    def on_submit(_):
        """삽입 버튼 클릭 – 트랜잭션 처리."""
        if not f_name.value or not f_faction.value or not f_position.value:
            result_text.value = "⚠ 캐릭터명, 진영, 포지션은 필수 항목입니다."
            result_text.color = ACCENT
            page.update()
            return

        def safe_float(v):
            try: return float(v) if v else None
            except: return None

        def safe_int(v):
            try: return int(v) if v else None
            except: return None

        char_data = {
            "name":            f_name.value.strip(),
            "faction":         f_faction.value,
            "position":        f_position.value,
            "decode_score":    int(slider_dec.value),
            "support_score":   int(slider_sup.value),
            "kiting_score":    int(slider_kit.value),
            "rescue_score":    int(slider_rsc.value),
            "operation_guide": f_guide.value,
            "image_path":      f_img.value or "",
        }
        stats_data = {
            "run_speed_ms":        safe_float(f_run.value),
            "walk_speed_ms":       safe_float(f_walk.value),
            "crawl_speed_ms":      safe_float(f_crawl.value),
            "decode_time_s":       safe_int(f_dec_t.value),
            "gate_open_time_s":    safe_int(f_gate.value),
            "pallet_drop_time_s":  safe_float(f_pal.value),
            "vault_fast_time_s":   safe_float(f_vlt.value),
            "heal_other_time_s":   safe_float(f_ho.value),
            "heal_self_time_s":    safe_int(f_hs.value),
            "chair_takeoff_time_s":safe_int(f_chair.value),
        }
        trait_data = None
        if f_trait.value and f_trait.value != "없음":
            trait_data = {
                "trait_id":      int(f_trait.value),
                "specific_value": f_trait_val.value,
                "warning_memo":  f_warning.value,
            }

        ok, msg = service.save_advanced_character(char_data, stats_data, trait_data)
        result_text.value = ("✅ " if ok else "❌ ") + msg
        result_text.color = SUCCESS if ok else ACCENT

        if ok:
            # 폼 초기화
            for field in [f_name, f_guide, f_img, f_run, f_walk, f_crawl,
                          f_dec_t, f_gate, f_pal, f_vlt, f_ho, f_hs, f_chair,
                          f_trait_val, f_warning]:
                field.value = ""
            f_faction.value  = None
            f_position.value = None
            f_trait.value    = "없음"
            for sl, vt in [(slider_dec, val_dec), (slider_sup, val_sup),
                           (slider_kit, val_kit), (slider_rsc, val_rsc)]:
                sl.value = 5
                vt.value = "5"

        page.update()

    def on_reset(_):
        for field in [f_name, f_guide, f_img, f_run, f_walk, f_crawl,
                      f_dec_t, f_gate, f_pal, f_vlt, f_ho, f_hs, f_chair,
                      f_trait_val, f_warning]:
            field.value = ""
        f_faction.value  = None
        f_position.value = None
        f_trait.value    = "없음"
        result_text.value = ""
        page.update()

    # ── 폼 레이아웃 조립 ──
    def row2(*fields):
        return ft.Row(list(fields), spacing=10, expand=True)

    form_content = ft.Column([
        section_title("■ 기본 정보"),
        f_name,
        row2(f_faction, f_position),

        ft.Container(height=4),
        section_title("■ 능력치 평가 (1~10)"),
        ft.Row([ft.Text("해독", color=TEXT_SUB, size=12, width=36),
                slider_dec, val_dec], spacing=8),
        ft.Row([ft.Text("보조", color=TEXT_SUB, size=12, width=36),
                slider_sup, val_sup], spacing=8),
        ft.Row([ft.Text("견제", color=TEXT_SUB, size=12, width=36),
                slider_kit, val_kit], spacing=8),
        ft.Row([ft.Text("구원", color=TEXT_SUB, size=12, width=36),
                slider_rsc, val_rsc], spacing=8),

        ft.Container(height=4),
        section_title("■ 특성 상세 수치 입력 (세부 스탯)"),
        row2(f_run, f_walk, f_crawl),
        row2(f_dec_t, f_gate),
        row2(f_pal, f_vlt),
        row2(f_ho, f_hs, f_chair),

        ft.Container(height=4),
        section_title("■ 운영 및 매커니즘 가이드"),
        f_guide,

        ft.Container(height=4),
        section_title("■ 특성 연결"),
        f_trait,
        f_trait_val,
        f_warning,

        ft.Container(height=4),
        section_title("■ 이미지 경로 (선택)"),
        f_img,

        ft.Container(height=8),
        ft.Row([
            ft.OutlinedButton("폼 입력 초기화", on_click=on_reset,
                              style=ft.ButtonStyle(color=TEXT_SUB)),
            ft.ElevatedButton(
                "DB 상세 데이터 삽입", on_click=on_submit,
                style=ft.ButtonStyle(
                    bgcolor=ACCENT, color="white",
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            ),
        ], spacing=12),
        result_text,
        ft.Container(height=20),
    ], spacing=10, scroll=ft.ScrollMode.AUTO)

    return ft.Column([
        ft.Text("데이터 삽입", size=20, color=TEXT_MAIN,
                weight=ft.FontWeight.BOLD),
        ft.Text("신규 캐릭터의 기본 정보 + 세부 스탯 + 특성을 한 번에 등록합니다",
                color=TEXT_SUB, size=12),
        ft.Divider(color=ACCENT_SOFT + "44"),
        ft.Container(content=form_content, expand=True),
    ], spacing=10, expand=True)


# ════════════════════════════════════════════════════════════
#  ③ 맵 가이드 화면
# ════════════════════════════════════════════════════════════

def build_map_guide_view(page: ft.Page) -> ft.Column:
    """
    설계서 4.④ 맵 가이드 화면 – Maps × Position_Spawns JOIN 결과 표출.
    추가로 신규 스폰 가이드 등록 폼 포함.
    """
    sel_map = ft.Dropdown(
        label="맵 선택",
        options=[ft.dropdown.Option(m) for m in MAP_NAMES],
        value=MAP_NAMES[0],
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )
    sel_pos = ft.Dropdown(
        label="포지션",
        options=[ft.dropdown.Option(p) for p in POSITIONS[1:]],  # 전체 제외
        value="구원형",
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )

    guide_card = ft.Container(
        bgcolor=CARD_BG, border_radius=10, padding=16,
        content=ft.Text("맵과 포지션을 선택하고 조회하세요.",
                         color=TEXT_SUB, size=13),
    )

    def do_query(_=None):
        df = service.get_spawn_guide(sel_map.value, sel_pos.value)
        if df.empty:
            guide_card.content = ft.Column([
                ft.Icon(ft.Icons.MAP_OUTLINED, color=TEXT_SUB, size=36),
                ft.Text(f"'{sel_map.value}' × '{sel_pos.value}' 가이드가 없습니다.",
                        color=TEXT_SUB, size=13),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
        else:
            row = df.iloc[0]
            guide_card.content = ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.PLACE, color=ACCENT, size=20),
                    ft.Text(f"{row['맵이름']}  ·  {row['포지션']}",
                            color=TEXT_MAIN, size=15, weight=ft.FontWeight.BOLD),
                ]),
                ft.Divider(color=ACCENT_SOFT + "44"),
                ft.Row([
                    ft.Text("추천 스폰 구역 :", color=TEXT_SUB, size=13),
                    ft.Text(str(row["추천스폰"]), color=ACCENT, size=15,
                            weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Container(height=4),
                ft.Container(
                    content=ft.Text(str(row["가이드메모"]) if row["가이드메모"] else "-",
                                    color=TEXT_MAIN, size=13, selectable=True),
                    bgcolor=SIDEBAR_BG, border_radius=8, padding=12,
                ),
                ft.Container(height=4),
                ft.Text(f"맵 설명: {row['맵설명']}", color=TEXT_SUB, size=11),
            ], spacing=8)
        page.update()

    # ── 신규 스폰 가이드 추가 폼 ──
    def tf(label, hint=""):
        return ft.TextField(
            label=label, hint_text=hint,
            color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
            border_color=ACCENT_SOFT, focused_border_color=ACCENT,
            bgcolor=SIDEBAR_BG, border_radius=8, text_size=13, height=46,
        )

    add_map  = ft.Dropdown(
        label="맵", options=[ft.dropdown.Option(m) for m in MAP_NAMES],
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )
    add_pos  = ft.Dropdown(
        label="포지션",
        options=[ft.dropdown.Option(p) for p in POSITIONS[1:]],
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        bgcolor=SIDEBAR_BG, border_color=ACCENT_SOFT,
        focused_border_color=ACCENT, border_radius=8, text_size=13,
    )
    add_spawn = tf("추천 스폰 구역", "예: 6번 젠")
    add_memo  = ft.TextField(
        label="가이드 메모",
        color=TEXT_MAIN, label_style=ft.TextStyle(color=TEXT_SUB),
        border_color=ACCENT_SOFT, focused_border_color=ACCENT,
        bgcolor=SIDEBAR_BG, border_radius=8,
        text_size=13, multiline=True, min_lines=2, max_lines=4,
    )
    add_result = ft.Text("", color=TEXT_SUB, size=12)

    def on_add(_):
        if not all([add_map.value, add_pos.value, add_spawn.value]):
            add_result.value = "⚠ 맵, 포지션, 스폰 구역은 필수입니다."
            add_result.color = ACCENT
            page.update()
            return
        ok, msg = service.save_spawn_guide(
            add_map.value, add_pos.value,
            add_spawn.value, add_memo.value,
        )
        add_result.value = ("✅ " if ok else "❌ ") + msg
        add_result.color = SUCCESS if ok else ACCENT
        if ok:
            add_spawn.value = ""
            add_memo.value  = ""
        page.update()

    return ft.Column([
        ft.Text("맵 가이드 조회", size=20, color=TEXT_MAIN,
                weight=ft.FontWeight.BOLD),
        ft.Text("맵과 포지션을 선택하면 최적 스폰 구역과 동선 가이드를 표시합니다",
                color=TEXT_SUB, size=12),
        ft.Divider(color=ACCENT_SOFT + "44"),

        # 조회 섹션
        ft.Row([sel_map, sel_pos,
                ft.ElevatedButton("조회", on_click=do_query,
                                  style=ft.ButtonStyle(
                                      bgcolor=ACCENT, color="white",
                                      shape=ft.RoundedRectangleBorder(radius=8),
                                  ))], spacing=10),
        guide_card,

        ft.Container(height=16),
        ft.Text("── 스폰 가이드 추가 등록", color=TEXT_SUB, size=13,
                weight=ft.FontWeight.BOLD),
        ft.Row([add_map, add_pos], spacing=10),
        add_spawn,
        add_memo,
        ft.Row([
            ft.ElevatedButton("등록", on_click=on_add,
                              style=ft.ButtonStyle(
                                  bgcolor=ACCENT_SOFT, color="white",
                                  shape=ft.RoundedRectangleBorder(radius=8),
                              )),
        ]),
        add_result,
    ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)


# ════════════════════════════════════════════════════════════
#  앱 진입점
# ════════════════════════════════════════════════════════════

def main(page: ft.Page):
    # ── 기본 페이지 설정 ──
    page.title       = "IDV Meta-Analyzer"
    page.bgcolor     = DARK_BG
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width  = 1100
    page.window_height = 760
    page.window_min_width  = 800
    page.window_min_height = 600
    page.padding     = 0
    page.fonts       = {
        "NotoSans": "https://fonts.gstatic.com/s/notosans/v36/o-0bIpQlx3QUlC5A4PNjXhFlY9aA5W0.woff2"
    }

    # DB 초기화 (처음 실행 시 테이블 + 샘플 데이터 생성)
    init_db()

    # ── 상태 변수 ──
    current_view = [0]

    # ── 콘텐츠 영역 ──
    content_area = ft.Container(
        content=build_encyclopedia_view(page),
        expand=True, padding=20,
    )

    # ── 사이드바 버튼 참조 ──
    nav_refs = []

    def navigate(idx: int):
        current_view[0] = idx
        views = [
            lambda: build_encyclopedia_view(page),
            lambda: build_insert_view(page),
            lambda: build_map_guide_view(page),
        ]
        content_area.content = views[idx]()
        for i, ref in enumerate(nav_refs):
            ref.bgcolor  = ACCENT_SOFT + "55" if i == idx else "transparent"
            ref.border   = (ft.Border.all(1, ACCENT + "55")
                            if i == idx else None)
        page.update()

    # ── 사이드바 구성 ── 
    nav_items = [
        ("캐릭터 도감",   ft.Icons.MENU_BOOK_ROUNDED),
        ("데이터 삽입",   ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED),
        ("맵 가이드",     ft.Icons.MAP_ROUNDED),
    ]

    def make_nav(i, label, icon):
        def on_click(_): navigate(i)
        container = ft.Container(
            content=ft.Row([
                ft.Icon(icon, color=ACCENT if i == 0 else TEXT_SUB, size=18),
                ft.Text(label,
                        color=ACCENT if i == 0 else TEXT_SUB,
                        size=13,
                        weight=ft.FontWeight.BOLD if i == 0 else None),
            ], spacing=10),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border_radius=8,
            bgcolor=ACCENT_SOFT + "55" if i == 0 else "transparent",
            on_click=on_click,
            ink=True,
            animate=ft.Animation(200),
        )
        nav_refs.append(container)
        return container

    sidebar = ft.Container(
        width=180,
        bgcolor=SIDEBAR_BG,
        padding=ft.Padding.symmetric(vertical=20),
        content=ft.Column([
            # 로고 영역
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.SPORTS_ESPORTS, color=ACCENT, size=24),
                        ft.Text("IDV", color=ACCENT, size=18,
                                weight=ft.FontWeight.BOLD),
                    ], spacing=6),
                    ft.Text("Meta-Analyzer", color=TEXT_SUB, size=10),
                ], spacing=2),
                padding=ft.Padding.only(left=16, bottom=16),
            ),
            ft.Divider(color=ACCENT_SOFT + "44"),
            ft.Container(height=8),

            # 네비게이션 버튼들
            *[make_nav(i, label, icon)
              for i, (label, icon) in enumerate(nav_items)],

            ft.Container(expand=True),  # 하단 여백 채우기

            # 하단 정보
            ft.Container(
                content=ft.Column([
                    ft.Divider(color=ACCENT_SOFT + "44"),
                    ft.Text("제5인격 실전 메타 DB", color=TEXT_SUB, size=10),
                    ft.Text("DuckDB  ·  Flet", color=TEXT_SUB + "88", size=9),
                ], spacing=2),
                padding=ft.Padding.only(left=16),
            ),
        ], spacing=4, expand=True),
    )

    # ── 전체 레이아웃 ──
    page.add(
        ft.Row([
            sidebar,
            ft.VerticalDivider(width=1, color=ACCENT_SOFT + "33"),
            content_area,
        ], expand=True, spacing=0)
    )


if __name__ == "__main__":
    ft.app(target=main)
