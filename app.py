import os
import uuid
import calendar
from datetime import datetime, date, timedelta

os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import streamlit as st
from openai import OpenAI
from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore

st.set_page_config(page_title="김보듬 케어 대시보드", page_icon="🧸", layout="wide")

# ── 1. 클라이언트 초기화 ─────────────────────────────────────────────────────
try:
    api_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    admin_password = st.secrets["admin_password"]
    patient_info = dict(st.secrets.get("patient", {}))
except KeyError as e:
    st.error(f"Secrets 설정이 필요합니다: {e}")
    st.stop()

client = OpenAI(api_key=api_key)
supabase_client = create_client(supabase_url, supabase_key)
embeddings = OpenAIEmbeddings(openai_api_key=api_key, model="text-embedding-3-small")
vector_store = SupabaseVectorStore(
    client=supabase_client,
    embedding=embeddings,
    table_name="documents",
    query_name="match_documents",
)

# ── 2. 시스템 프롬프트 ───────────────────────────────────────────────────────
system_instruction = """
## 1. 진단서 및 의학용어 해석 (Deep Interpretation)
사용자가 용어나 진단서를 물어보면 **단순 사전적 정의**를 넘어 **'임상적 의미'**를 설명하세요.

## 2. 생활 및 식단 가이드 (Contextual Advice)
"먹어도 돼?"라는 질문에 O/X만 하지 말고 **상황별 판단 기준**을 주세요.

## 3. 커뮤니티 및 정보 연결 (Resource Mapping)
답변 후, 환자의 질병 코드나 상황에 맞춰 아래 링크를 **반드시** 버튼 형태로 추천해주세요. 한번만 추천하고 이후에는 추천하지 마세요.
* **담도암:** "👉 [담도암 환우들의 치료 일지 보러가기](https://cafe.naver.com/cholangiocarcinoma2)"
* **위암 (Stomach Cancer) 관련:** "👉 [위암 환우들의 식단 & 극복 후기 보러가기](https://cafe.naver.com/ilovestomach)"
* **유방암 (Breast Cancer) 관련:** "👉 [유방암 환우들의 치료 일지 보러가기](https://cafe.naver.com/pinkribbon)"
* **기타 암/식별 불가:** "👉 [12만 환우들과 소통하러 가기](https://cafe.naver.com/beautifulcompanion)"

# Safety Protocol
* 당신은 진단(Diagnosis)을 내리는 주체가 아닙니다. 설명 끝에는 항상 **"하지만 정확한 현재 상태는 주치의 선생님의 판단이 가장 중요합니다."**라고 부드럽게 넘겨주세요.
* 특정 건강기능식품이나 민간요법을 맹신하는 질문에는, 그 위험성을 **과학적 근거**를 들어 단호하게 경고하세요.

# Empathy First
사용자의 질문에서 **불안, 공포, 지침** 등의 감정이 감지되면, 바로 의학적 정보를 나열하지 말고 먼저 마음을 읽어주세요.

# Red Flag Detection
만약 질문 내용 중에 **응급 상황(Red Flags)**이 포함되어 있다면, **즉시 응급실 방문을 권유**하세요.
1. 발열: 체온이 38도 이상일 때
2. 통증: 갑작스럽고 참을 수 없는 극심한 통증
3. 호흡: 숨이 차거나 가슴이 답답할 때
4. 의식: 환자가 쳐지거나 의식이 흐릿할 때
"""

# ── 3. 핵심 함수 ─────────────────────────────────────────────────────────────
def retrieve_context(query: str, k: int = 3) -> str:
    try:
        docs = vector_store.similarity_search(query, k=k)
        if not docs:
            return ""
        context = "\n\n---\n\n".join([doc.page_content for doc in docs])
        return f"## 참고 자료 (최신 의료 데이터)\n{context}"
    except Exception:
        return ""

def get_or_create_session():
    if "session_id" not in st.session_state:
        session_id = str(uuid.uuid4())
        supabase_client.table("sessions").insert({"id": session_id}).execute()
        st.session_state.session_id = session_id
    return st.session_state.session_id

def save_log_to_db(role, content):
    session_id = get_or_create_session()
    supabase_client.table("chat_logs").insert({
        "session_id": session_id,
        "role": role,
        "content": str(content)
    }).execute()

def save_daily_record(record_date, caregiver_name, condition_text, pain_score, has_files):
    result = supabase_client.table("daily_records").insert({
        "record_date": str(record_date),
        "caregiver_name": caregiver_name,
        "condition_text": condition_text,
        "pain_score": pain_score,
        "has_files": has_files
    }).execute()
    return result.data[0]["id"] if result.data else None

def get_monthly_records(year, month):
    start = f"{year}-{month:02d}-01"
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{end_year}-{end_month:02d}-01"
    result = supabase_client.table("daily_records").select("*").gte("record_date", start).lt("record_date", end).execute()
    return result.data

def get_date_record(record_date):
    result = supabase_client.table("daily_records").select("*").eq("record_date", str(record_date)).order("created_at", desc=True).execute()
    return result.data

def get_all_records():
    result = supabase_client.table("daily_records").select("*").order("record_date", desc=True).execute()
    return result.data

def pain_icon(score):
    if score is None:
        return "⬜"
    if score <= 3:
        return "🟢"
    if score <= 6:
        return "🟡"
    return "🔴"

def send_chat_message(user_input):
    save_log_to_db("user", user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    try:
        context = retrieve_context(user_input)
        messages_with_context = list(st.session_state.messages)
        if context:
            messages_with_context.insert(1, {"role": "system", "content": context})
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages_with_context,
            temperature=0.2,
        )
        full_response = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_log_to_db("assistant", full_response)
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"오류가 발생했습니다: {e}"})

# ── 4. 로그인 화면 ───────────────────────────────────────────────────────────
def show_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("## 🧸 김보듬 케어")
        st.caption("암 환자 보호자 케어 대시보드")
        st.divider()
        name = st.text_input("보호자 이름", placeholder="이름을 입력하세요")
        password = st.text_input("비밀번호", type="password", placeholder="공유 비밀번호 입력")
        if st.button("로그인", use_container_width=True, type="primary"):
            if password == admin_password:
                st.session_state.logged_in = True
                st.session_state.caregiver_name = name.strip() if name.strip() else "보호자"
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")

if not st.session_state.get("logged_in"):
    show_login()
    st.stop()

# ── 5. 세션 상태 초기화 ──────────────────────────────────────────────────────
if "view" not in st.session_state:
    st.session_state.view = "calendar"
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()
if "cal_year" not in st.session_state:
    st.session_state.cal_year = date.today().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = date.today().month
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_instruction}]
if "add_record_mode" not in st.session_state:
    st.session_state.add_record_mode = False

# ── 6. 메인 레이아웃 (3단) ───────────────────────────────────────────────────
col_left, col_center, col_right = st.columns([1, 2, 1.5])

# ════════════════════════════════════════════════════════════════════════════
# 좌측: 환자 프로필 & 툴바
# ════════════════════════════════════════════════════════════════════════════
with col_left:
    patient_name = patient_info.get("name", "환자명")
    diagnosis = patient_info.get("diagnosis", "진단명")
    doctor = patient_info.get("doctor", "주치의")
    hospital = patient_info.get("hospital", "병원명")

    st.markdown(f"""
<div style="background:#f8f9fa;border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid #eee;">
  <div style="font-size:11px;color:#999;margin-bottom:6px;">환자 정보</div>
  <div style="font-size:20px;font-weight:700;">{patient_name}</div>
  <div style="font-size:13px;color:#e74c3c;margin:4px 0;">{diagnosis}</div>
  <div style="font-size:12px;color:#999;">{doctor} · {hospital}</div>
</div>
<div style="font-size:13px;color:#555;margin-bottom:12px;">
  <b>{st.session_state.caregiver_name}</b> 님 환영합니다
</div>
""", unsafe_allow_html=True)

    st.divider()

    if st.button("📅  캘린더", use_container_width=True,
                 type="primary" if st.session_state.view == "calendar" else "secondary"):
        st.session_state.view = "calendar"
        st.rerun()

    if st.button("📋  기록 로그", use_container_width=True,
                 type="primary" if st.session_state.view == "log" else "secondary"):
        st.session_state.view = "log"
        st.rerun()

    if st.button("📄  회진 레포트", use_container_width=True,
                 type="primary" if st.session_state.view == "report" else "secondary"):
        st.session_state.view = "report"
        st.rerun()

    st.divider()

    # 채팅 팝업 (st.popover)
    with st.popover("💬  김보듬에게 질문", use_container_width=True):
        st.markdown("#### 🧸 수간호사 김보듬")
        st.caption("암 환자와 보호자를 위한 든든한 방패")

        chat_container = st.container(height=320)
        with chat_container:
            for msg in st.session_state.messages:
                if msg["role"] == "system":
                    continue
                with st.chat_message(msg["role"]):
                    content = msg["content"]
                    if isinstance(content, list):
                        st.markdown(content[0].get("text", ""))
                    else:
                        st.markdown(content)

        chat_input = st.text_input(
            "질문", label_visibility="collapsed",
            key="chat_text_input",
            placeholder="궁금한 점을 물어보세요..."
        )
        if st.button("전송", key="chat_send_btn", use_container_width=True, type="primary"):
            if chat_input.strip():
                send_chat_message(chat_input.strip())
                st.rerun()

    st.divider()
    if st.button("🚪 로그아웃", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# 중앙: 캘린더 / 로그 / 레포트 뷰
# ════════════════════════════════════════════════════════════════════════════
with col_center:

    # ── 캘린더 뷰 ────────────────────────────────────────────────────────
    if st.session_state.view == "calendar":
        year = st.session_state.cal_year
        month = st.session_state.cal_month

        # 월 네비게이션
        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("◀", key="prev_month"):
                if month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else:
                    st.session_state.cal_month -= 1
                st.rerun()
        with nav2:
            st.markdown(f"<h3 style='text-align:center;margin:0'>{year}년 {month}월</h3>",
                        unsafe_allow_html=True)
        with nav3:
            if st.button("▶", key="next_month"):
                if month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else:
                    st.session_state.cal_month += 1
                st.rerun()

        # 기록 조회
        monthly_records = get_monthly_records(year, month)
        record_by_date = {r["record_date"]: r for r in monthly_records}

        # 요일 헤더
        day_headers = st.columns(7)
        for i, d in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
            day_headers[i].markdown(
                f"<div style='text-align:center;font-weight:600;color:#888;padding:6px 0;font-size:13px;'>{d}</div>",
                unsafe_allow_html=True
            )

        # 달력 그리드
        cal_matrix = calendar.monthcalendar(year, month)
        for week in cal_matrix:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    week_cols[i].write("")
                    continue
                d = date(year, month, day)
                date_str = str(d)
                has_record = date_str in record_by_date
                is_selected = str(st.session_state.selected_date) == date_str
                is_today = d == date.today()

                if has_record:
                    pain = record_by_date[date_str].get("pain_score") or 5
                    icon = pain_icon(pain)
                    label = f"{day}\n{icon}"
                elif is_today:
                    label = f"📌{day}"
                else:
                    label = str(day)

                btn_type = "primary" if is_selected else "secondary"
                if week_cols[i].button(label, key=f"cal_{date_str}",
                                       use_container_width=True, type=btn_type):
                    st.session_state.selected_date = d
                    st.session_state.add_record_mode = False
                    st.rerun()

        # 범례
        st.markdown("""
<div style="font-size:12px;color:#999;margin-top:8px;">
  🟢 통증 낮음(1-3) &nbsp;·&nbsp; 🟡 보통(4-6) &nbsp;·&nbsp; 🔴 높음(7-10) &nbsp;·&nbsp; 📌 오늘
</div>
""", unsafe_allow_html=True)

    # ── 기록 로그 뷰 ─────────────────────────────────────────────────────
    elif st.session_state.view == "log":
        st.markdown("### 📋 전체 기록 로그")
        all_records = get_all_records()
        if all_records:
            for r in all_records:
                pain = r.get("pain_score")
                with st.expander(
                    f"{pain_icon(pain)} {r['record_date']} — {r['caregiver_name']} "
                    f"(통증: {pain if pain else '-'}/10)"
                ):
                    st.markdown(r.get("condition_text") or "_텍스트 기록 없음_")
                    if r.get("has_files"):
                        st.caption("📎 파일 첨부됨")
        else:
            st.info("아직 기록이 없습니다.")

    # ── 회진 레포트 뷰 ───────────────────────────────────────────────────
    elif st.session_state.view == "report":
        st.markdown("### 📄 회진 레포트 생성")
        st.caption("선택 기간의 기록을 AI가 의사용 요약문으로 작성합니다.")

        date_range = st.date_input(
            "기간 선택",
            value=(date.today() - timedelta(days=7), date.today()),
            format="YYYY/MM/DD",
            key="report_date_range"
        )

        if st.button("🤖 AI 레포트 생성", type="primary", use_container_width=True):
            if len(date_range) == 2:
                start_date, end_date = date_range
                result = supabase_client.table("daily_records").select("*") \
                    .gte("record_date", str(start_date)) \
                    .lte("record_date", str(end_date)) \
                    .order("record_date").execute()
                records = result.data

                if not records:
                    st.warning("해당 기간에 기록이 없습니다.")
                else:
                    with st.spinner("📊 AI가 레포트를 작성 중입니다..."):
                        records_text = "\n".join([
                            f"[{r['record_date']}] 보호자: {r['caregiver_name']}, "
                            f"통증점수: {r.get('pain_score', '기록없음')}/10\n"
                            f"{r.get('condition_text', '내용 없음')}"
                            for r in records
                        ])

                        pname = patient_info.get("name", "환자")
                        report_prompt = f"""
다음은 {pname} 환자의 {start_date}부터 {end_date}까지의 보호자 관찰 기록입니다.
담당 의사가 회진 시 참고할 수 있도록 핵심 내용을 의학적 관점에서 요약해주세요.

[관찰 기록]
{records_text}

다음 형식으로 작성해 주세요:
1. 통증 패턴 요약 (평균 점수, 악화 시간대 등)
2. 주요 증상 변화
3. 보호자가 특별히 우려한 사항
4. 의사에게 건의할 사항"""

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "당신은 암 환자의 담당 의사를 보조하는 임상 코디네이터입니다."},
                                {"role": "user", "content": report_prompt}
                            ],
                            temperature=0.3,
                        )
                        report_text = response.choices[0].message.content

                    st.divider()
                    st.markdown(report_text)
                    st.divider()

                    # TXT 다운로드
                    report_content = (
                        f"회진 레포트\n기간: {start_date} ~ {end_date}\n"
                        f"환자: {pname}\n\n{report_text}"
                    )
                    st.download_button(
                        "📥 레포트 다운로드 (TXT)",
                        data=report_content.encode("utf-8"),
                        file_name=f"회진레포트_{start_date}_{end_date}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

                    # PDF 다운로드 (한글 폰트 파일 있을 때만)
                    try:
                        from fpdf import FPDF
                        pdf = FPDF()
                        pdf.add_page()
                        font_path = os.path.join(os.path.dirname(__file__), "NanumGothic.ttf")
                        if os.path.exists(font_path):
                            pdf.add_font("NanumGothic", fname=font_path)
                            pdf.set_font("NanumGothic", size=12)
                        else:
                            pdf.set_font("Helvetica", size=12)
                        pdf.cell(0, 10, f"Ward Round Report - {pname}", ln=True)
                        pdf.cell(0, 10, f"Period: {start_date} ~ {end_date}", ln=True)
                        pdf.ln(4)
                        for line in report_text.split("\n"):
                            safe_line = line.encode("latin-1", "replace").decode("latin-1")
                            pdf.multi_cell(0, 8, safe_line)
                        pdf_bytes = bytes(pdf.output())
                        st.download_button(
                            "📥 PDF 다운로드",
                            data=pdf_bytes,
                            file_name=f"report_{start_date}_{end_date}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception:
                        pass

# ════════════════════════════════════════════════════════════════════════════
# 우측: 날짜별 기록 입력 / 조회
# ════════════════════════════════════════════════════════════════════════════
with col_right:
    if st.session_state.view in ["calendar", "log"]:
        selected = st.session_state.selected_date
        st.markdown(f"### 📝 {selected.strftime('%Y년 %m월 %d일')}")

        existing = get_date_record(selected)

        if existing and not st.session_state.add_record_mode:
            for rec in existing:
                pain = rec.get("pain_score")
                st.markdown(
                    f"**{rec['caregiver_name']}** 기록 &nbsp; "
                    f"{pain_icon(pain)} **{pain if pain else '-'}/10**"
                )
                if rec.get("condition_text"):
                    st.markdown(
                        f"<div style='background:#f8f9fa;border-radius:8px;"
                        f"padding:12px;margin:8px 0;font-size:14px;'>"
                        f"{rec['condition_text']}</div>",
                        unsafe_allow_html=True
                    )
                if rec.get("has_files"):
                    st.caption("📎 파일 첨부됨")
                st.divider()
            if st.button("+ 추가 기록 작성", use_container_width=True):
                st.session_state.add_record_mode = True
                st.rerun()

        if not existing or st.session_state.add_record_mode:
            with st.form(key=f"record_form_{selected}", clear_on_submit=True):
                condition_text = st.text_area(
                    "오늘 컨디션 좀 어떠세요?",
                    placeholder="환자의 상태, 특이사항, 복용 약물 등을 자유롭게 적어주세요...",
                    height=130
                )
                pain_score = st.slider(
                    "통증 정도",
                    min_value=1, max_value=10, value=5,
                    help="1 = 거의 없음  |  10 = 매우 심함"
                )
                uploaded_files = st.file_uploader(
                    "파일 업로드 (사진, 검사결과, 처방전 등)",
                    accept_multiple_files=True,
                    type=["jpg", "jpeg", "png", "pdf", "docx"]
                )
                submitted = st.form_submit_button(
                    "💾 저장하기", use_container_width=True, type="primary"
                )

                if submitted:
                    has_files = len(uploaded_files) > 0
                    record_id = save_daily_record(
                        selected,
                        st.session_state.caregiver_name,
                        condition_text,
                        pain_score,
                        has_files
                    )
                    if record_id and uploaded_files:
                        if not os.path.exists("saved_images"):
                            os.makedirs("saved_images")
                        for f in uploaded_files:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_path = os.path.join("saved_images", f"{ts}_{f.name}")
                            with open(file_path, "wb") as fp:
                                fp.write(f.getbuffer())
                            supabase_client.table("record_files").insert({
                                "record_id": record_id,
                                "caregiver_name": st.session_state.caregiver_name,
                                "filename": f.name,
                                "file_path": file_path
                            }).execute()
                    st.success("✅ 기록이 저장되었습니다!")
                    st.session_state.add_record_mode = False
                    st.rerun()
