import re
import streamlit as st

# -----------------------------
# Page / Mobile-friendly styles
# -----------------------------
st.set_page_config(page_title="스케줄 자동 생성기", layout="centered")

st.markdown(
    """
<style>
/* 모바일에서 좌우 여백/폭 최적화 */
.block-container { padding-top: 1.1rem; padding-bottom: 2.0rem; max-width: 760px; }

/* 카드 UI */
.section-card {
  border: 1px solid rgba(49,51,63,.18);
  border-radius: 16px;
  padding: 14px 14px;
  margin: 12px 0;
  background: rgba(255,255,255,.03);
}

/* 섹션 타이틀 간격 */
.section-title { margin-bottom: .25rem; }

/* 작은 안내문 */
.small-muted { color: rgba(49,51,63,.7); font-size: 0.92rem; line-height: 1.35; }

/* 버튼은 모바일에서 꽉 차게 */
button[kind="primary"] { width: 100%; }

/* 입력 높이 살짝 키워서 모바일 터치 편하게 */
div[data-baseweb="input"] input { height: 2.6rem; }
div[data-baseweb="textarea"] textarea { font-size: 0.95rem; line-height: 1.4; }

/* 요일 라인 */
.day-line { font-size: 1.02rem; }

/* divider 여백 줄이기 */
hr { margin: 0.5rem 0; }

/* required section에서 columns를 모바일에서도 2열 유지 */
.required-grid [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important;
  gap: 0.75rem !important;
}
.required-grid [data-testid="stColumn"] {
  min-width: 0 !important;
}

</style>
""",
    unsafe_allow_html=True,
)

st.title("스케줄 자동 생성기")

# -----------------------------
# Constants
# -----------------------------
DAYS = ["월", "화", "수", "목", "금", "토", "일"]

MIN_TARGET = 3
SECONDARY_TARGET = 2
MAX_DAYS = 4


# -----------------------------
# Helpers
# -----------------------------
def parse_input(text: str):
    """'이름 - 불가능 요일' 입력을 파싱해 직원별 불가 요일 리스트를 만든다."""
    employees_blocked = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if "-" not in ln:
            continue
        name, right = ln.split("-", 1)
        name = name.strip()
        right = right.strip()

        # x 또는 빈칸 => 제한 없음 (blocked = [])
        if right == "" or right.lower() == "x":
            blocked = []
        else:
            blocked = re.findall(r"(월|화|수|목|금|토|일)", right)

        if name:
            employees_blocked[name] = blocked
    return employees_blocked


def attempt_schedule(employees_available, required, min_days):
    """
    그리디하게 스케줄을 생성하고,
    모든 직원이 min_days 이상 채웠는지(success) 반환.
    """
    schedule = {d: [] for d in DAYS}
    remaining = required.copy()
    assigned_count = {e: 0 for e in employees_available}

    # 가능한 요일이 적은 직원부터
    employees_sorted = sorted(
        employees_available.keys(), key=lambda e: len(employees_available[e])
    )

    # 1) 최소 일수 우선 배정
    for e in employees_sorted:
        prefer_days = sorted(
            [d for d in DAYS if d in employees_available[e]],
            key=lambda d: remaining[d],
            reverse=True,
        )
        for day in prefer_days:
            if assigned_count[e] >= min_days:
                break
            if remaining[day] > 0:
                schedule[day].append(e)
                assigned_count[e] += 1
                remaining[day] -= 1

    # 2) 남은 자리 채우기 (근무 적은 직원 우선)
    for day in DAYS:
        while remaining[day] > 0:
            candidates = [
                e
                for e in employees_available
                if day in employees_available[e]
                and assigned_count[e] < MAX_DAYS
                and e not in schedule[day]
            ]
            if not candidates:
                break
            candidates.sort(key=lambda x: assigned_count[x])
            pick = candidates[0]
            schedule[day].append(pick)
            assigned_count[pick] += 1
            remaining[day] -= 1

    success = all(assigned_count[e] >= min_days for e in employees_available)
    return schedule, assigned_count, success


def generate_schedule(employees_available, required):
    # 1차: 전원 3일 이상 목표
    schedule, assigned_count, success = attempt_schedule(
        employees_available, required, MIN_TARGET
    )

    if not success:
        # 2차: 전원 2일 이상 목표로 재시도
        schedule, assigned_count, _ = attempt_schedule(
            employees_available, required, SECONDARY_TARGET
        )

    unmet = [d for d in DAYS if len(schedule[d]) < required[d]]
    return schedule, assigned_count, unmet, success


def build_assigned_by_employee(schedule, employees_available):
    """schedule(요일->직원들)로부터 직원별 배정 요일 리스트를 만든다."""
    assigned_by_employee = {e: [] for e in employees_available}
    for day in DAYS:
        for name in schedule[day]:
            if name in assigned_by_employee and day not in assigned_by_employee[name]:
                assigned_by_employee[name].append(day)
    return assigned_by_employee


def parse_manual_schedule(text: str):
    schedule = {d: [] for d in DAYS}
    invalid_lines = []

    for ln in [line.strip() for line in text.splitlines() if line.strip()]:
        match = re.match(r"^(월|화|수|목|금|토|일)\s*(.*)$", ln)
        if not match:
            invalid_lines.append(ln)
            continue

        day, rest = match.groups()
        tokens = re.findall(r"[^\s,]+", rest)
        names = [t for t in tokens if t not in {"휴무/없음", "휴무", "없음", "-", "x", "X"}]
        schedule[day] = list(dict.fromkeys(names))  # 중복 제거(입력 순서 유지)

    return schedule, invalid_lines


def render_schedule_cards(schedule):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("생성된 스케줄")

    output_lines = []
    for day in DAYS:
        names = " ".join(schedule[day]) if schedule[day] else "휴무/없음"
        output_lines.append(f"{day} {names}")

    copy_text = "\n".join(output_lines)

    st.text_area(
        "",
        copy_text,
        height=180,
        label_visibility="collapsed",
    )

    st.markdown("</div>", unsafe_allow_html=True)



def render_employee_table(assigned_count, assigned_by_employee):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("직원별 배정")
    rows = []
    for e, cnt in assigned_count.items():
        rows.append(
            {
                "직원": e,
                "근무일수": cnt,
                "배정요일": ", ".join(assigned_by_employee.get(e, [])) or "-",
            }
        )
    # Streamlit이 list[dict]도 표로 잘 보여줍니다 (pandas 불필요)
    rows.sort(key=lambda x: x["근무일수"], reverse=True)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 1) Required staff per day (2 columns)
# -----------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("1) 요일별 필요 인원")


required = {}
for day in DAYS:
    required[day] = st.number_input(
        f"{day}요일",
        min_value=0,
        max_value=6,
        value=3,
        step=1,
        key=f"req_{day}",
    )

st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 2) Blocked days input
# -----------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("2) 출근 불가 요일 입력")


raw = st.text_area(
    "출근 불가 요일 입력",
    value="",
    height=180,
    label_visibility="collapsed",
)
st.markdown("</div>", unsafe_allow_html=True)

employees_blocked = parse_input(raw)

# 직원별 가능한 요일
employees_available = {}
for name, blocked in employees_blocked.items():
    employees_available[name] = [d for d in DAYS if d not in blocked]

# 가능한 요일 미리보기 (모바일에선 접어두는 게 깔끔)
with st.expander("직원별 가능한 요일 보기", expanded=False):
    if employees_available:
        for name, avail in employees_available.items():
            st.write(
                f"- {name}: {', '.join(avail) if avail else '없음(전부 불가)'}"
            )
    else:
        st.info("직원 정보를 입력하면 여기에서 확인할 수 있어요.")

# -----------------------------
# Schedule generation
# -----------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("스케줄 생성")


gen_clicked = st.button("스케줄 생성", type="primary", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

if gen_clicked:
    if not employees_available:
        st.error("직원 정보가 없습니다. 입력을 확인하세요.")
    else:
        schedule, assigned_count, unmet, min3_success = generate_schedule(
            employees_available, required
        )

        render_schedule_cards(schedule)

        assigned_by_employee = build_assigned_by_employee(schedule, employees_available)
        render_employee_table(assigned_count, assigned_by_employee)

        if min3_success:
            st.success("모든 인원이 주 3일 이상 근무하도록 배치되었습니다.")
        else:
            st.info("3일 배치는 불가능하여, 최소 2일 이상으로 맞췄어요.")

        if unmet:
            for d in unmet:
                st.error(
                    f"{d}요일: 필요한 인원({required[d]})을 채우지 못했습니다. (배정: {len(schedule[d])})"
                )

        

st.divider()

# -----------------------------
# 3) Manual schedule validation
# -----------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("3) 직접 작성한 스케줄 검증")


manual_text = st.text_area(
    "직접 작성한 스케줄 입력",
    value="",
    height=180,
    label_visibility="collapsed",
    help="예) 월 철수 영희 / 화 휴무",
)

verify_clicked = st.button("스케줄 검증", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

if verify_clicked:
    if not employees_available:
        st.error("직원 정보가 없습니다. 출근 불가 요일을 먼저 입력해주세요.")
    else:
        manual_schedule, invalid_lines = parse_manual_schedule(manual_text)

        assigned_days = {e: 0 for e in employees_available}
        assigned_by_employee = {e: [] for e in employees_available}
        blocked_violations = []
        unknown_names = set()

        for day in DAYS:
            for name in manual_schedule[day]:
                if name not in employees_available:
                    unknown_names.add(name)
                    continue

                if day in employees_blocked.get(name, []):
                    blocked_violations.append((name, day))

                assigned_days[name] += 1
                if day not in assigned_by_employee[name]:
                    assigned_by_employee[name].append(day)

        missing_min_days = [name for name, cnt in assigned_days.items() if cnt < MIN_TARGET]

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("검증 결과")

        if invalid_lines:
            st.warning("형식 오류로 무시된 라인이 있습니다: " + ", ".join(invalid_lines))

        if unknown_names:
            st.warning("직원 목록에 없는 이름이 포함되어 있습니다: " + ", ".join(sorted(unknown_names)))

        if blocked_violations:
            st.error("출근 불가 요일에 배정된 항목이 있습니다.")
            for name, day in blocked_violations:
                st.write(f"- {name}: {day}요일 불가")
        else:
            st.success("출근 불가 요일 배정 없음")

        if missing_min_days:
            st.error("주 3일 이상 근무 조건을 충족하지 못한 인원이 있습니다.")
            for name in missing_min_days:
                days_str = ", ".join(assigned_by_employee[name]) if assigned_by_employee[name] else "배정 없음"
                st.write(f"- {name}: {assigned_days[name]}일 / 배정 요일 → {days_str}")
        else:
            st.success("모든 인원이 주 3일 이상 근무합니다.")

        st.markdown("</div>", unsafe_allow_html=True)

        # 직원별 상세 표
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("직원별 배정 상세")
        rows = []
        for e, cnt in assigned_days.items():
            rows.append({"직원": e, "근무일수": cnt, "배정요일": ", ".join(assigned_by_employee[e]) or "-"})
        rows.sort(key=lambda x: x["근무일수"], reverse=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)
