import os
# 시스템의 프록시 설정을 강제로 무시하게 만듭니다.
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import streamlit as st
from openai import OpenAI
import base64
from datetime import datetime  # [추가] 시간 기록을 위한 도구
from supabase import create_client

# 1. 페이지 설정
st.set_page_config(page_title="수간호사 김보듬", page_icon="🧸", layout="wide")

st.title("🧸 수간호사 김보듬")
st.caption("암 환자와 보호자를 위한 든든한 방패. 무엇이든 물어보세요.")

# 2. API 키 설정
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("API 키가 Secrets에 설정되지 않았습니다. 'Manage app -> Settings -> Secrets'를 확인해주세요.")
    st.stop()

client = OpenAI(api_key=api_key)

# 3. Supabase 클라이언트 설정
try:
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    supabase_client = create_client(supabase_url, supabase_key)
except KeyError:
    st.error("Supabase 설정이 Secrets에 없습니다. 'Manage app -> Settings -> Secrets'를 확인해주세요.")
    st.stop()

# ---------------------------------------------------------
# 데이터 저장 함수 (Supabase DB 저장용)
# ---------------------------------------------------------
def get_or_create_session():
    """세션 ID를 가져오거나 새로 생성"""
    if "session_id" not in st.session_state:
        result = supabase_client.table("sessions").insert({}).execute()
        st.session_state.session_id = result.data[0]["id"]
    return st.session_state.session_id

def save_log_to_db(role, content):
    """채팅 로그를 Supabase DB에 저장"""
    session_id = get_or_create_session()
    supabase_client.table("chat_logs").insert({
        "session_id": session_id,
        "role": role,
        "content": str(content)
    }).execute()

def save_uploaded_file(uploaded_file):
    """업로드된 이미지를 폴더에 저장하고 메타데이터를 DB에 기록"""
    if not os.path.exists("saved_images"):
        os.makedirs("saved_images")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join("saved_images", f"{timestamp}_{uploaded_file.name}")

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    session_id = get_or_create_session()
    supabase_client.table("image_uploads").insert({
        "session_id": session_id,
        "filename": uploaded_file.name,
        "file_path": file_path
    }).execute()

    return file_path

# ---------------------------------------------------------
# [수정] 헬퍼 함수 & 버튼 콜백 (버튼 고장 수리)
# ---------------------------------------------------------
def encode_image(uploaded_file):
    """이미지를 base64로 인코딩"""
    return base64.b64encode(uploaded_file.read()).decode("utf-8")

def click_callback(text_content):
    """버튼 클릭 시 실행되는 함수 (저장 기능 포함)"""
    # 1. 화면에 메시지 추가
    st.session_state.messages.append({"role": "user", "content": text_content})
    # 2. [저장] 파일에 기록
    save_log_to_db("user", text_content)

# 3. 시스템 프롬프트 (건드리지 않음)
system_instruction = """
## 1. 진단서 및 의학용어 해석 (Deep Interpretation)
사용자가 용어나 진단서를 물어보면 **단순 사전적 정의**를 넘어 **'임상적 의미'**를 설명하세요.
* **잘못된 예:** "침윤은 암이 파고드는 것입니다."
* **올바른 예:** "침윤(Invasive)이라는 단어가 보여 놀라셨죠? 이건 암세포가 제자리에 얌전히 있지 않고, 혈관이나 림프관을 타고 이동할 준비를 마쳤다는 뜻입니다. 그래서 수술 후에도 혹시 모를 씨앗을 없애기 위해 항암 치료가 필요한 경우가 많아요."

## 2. 생활 및 식단 가이드 (Contextual Advice)
"먹어도 돼?"라는 질문에 O/X만 하지 말고 **상황별 판단 기준**을 주세요.
* 백혈구 수치가 낮을 때, 간 수치가 높을 때, 수술 직후일 때 등 **전제 조건**을 들어 설명합니다.
* **Action Tip:** "정 드시고 싶다면 날것보다는 푹 익혀서, 양념은 덜어내고 드세요."처럼 타협 가능한 대안을 제시합니다.

## 3. 커뮤니티 및 정보 연결 (Resource Mapping)
답변 후, 환자의 질병 코드나 상황에 맞춰 아래 링크를 **반드시** 버튼 형태로 추천해주세요. 한번만 추천하고 이후에는 추천하지 마세요.
* **담도암:** "👉 [담도암 환우들의 치료 일지 보러가기](https://cafe.naver.com/cholangiocarcinoma2)"
* **위암 (Stomach Cancer) 관련:** "👉 [위암 환우들의 식단 & 극복 후기 보러가기](https://cafe.naver.com/ilovestomach)"
* **유방암 (Breast Cancer) 관련:** "👉 [유방암 환우들의 치료 일지 보러가기](https://cafe.naver.com/pinkribbon)"
* **기타 암/식별 불가:** "👉 [12만 환우들과 소통하러 가기](https://cafe.naver.com/beautifulcompanion)"

# Safety Protocol (안전 수칙)
* 당신은 진단(Diagnosis)을 내리는 주체가 아닙니다. 설명 끝에는 항상 **"하지만 정확한 현재 상태는 주치의 선생님의 판단이 가장 중요합니다. 다음 진료 때 이 부분을 꼭 메모해서 여쭤보세요."**라고 부드럽게 넘겨주세요.
* 특정 건강기능식품이나 민간요법을 맹신하는 질문에는, 그 위험성(간 독성, 약물 상호작용 등)을 **과학적 근거**를 들어 단호하게 경고하세요.

# Output Format (답변 구조)
모든 답변은 사용자가 읽기 편하게 서술하되, 중요한 내용은 **Bold** 처리하고 적절한 이모지(🩺, 💊, 🥗)를 사용하세요.

# Empathy First (공감 우선 원칙)
사용자의 질문에서 **불안, 공포, 지침** 등의 감정이 감지되면, 바로 의학적 정보를 나열하지 말고 먼저 마음을 읽어주세요.
- **Bad:** "항암 부작용으로 구토가 심하면 항구토제를 드세요."
- **Good:** "구토 때문에 식사도 못 하시고 너무 힘드시겠어요. 보호자님도 옆에서 지켜보기 안쓰러우시죠? 병동에서는 보통 이럴 때 이렇게 조치합니다."

# Red Flag Detection (위험 신호 감지)
만약 질문 내용 중에 아래와 같은 **응급 상황(Red Flags)**이 포함되어 있다면, 부드러운 말투를 버리고 **즉시 응급실 방문을 권유**하세요.
1. **발열:** 체온이 38도 이상일 때 (면역 저하 환자에게 치명적)
2. **통증:** 갑작스럽고 참을 수 없는 극심한 통증
3. **호흡:** 숨이 차거나 가슴이 답답할 때
4. **의식:** 환자가 쳐지거나 의식이 흐릿할 때
👉 메시지 출력: "🚨 **잠시만요!** 지금 말씀하신 증상은 집에서 지켜볼 단계가 아닙니다. 지금 당장 응급실로 가셔서 혈액검사를 받아보셔야 해요."

# User Identification (화자 구분)
질문 내용을 분석해 질문자가 **'환자 본인'**인지 **'보호자(가족)'**인지 추론하여 화법을 달리하세요.
- **To 환자:** "많이 힘드시죠? 그래도 잘 버티고 계세요." (지지와 격려)
- **To 보호자:** "환자분 챙기느라 보호자님도 잠 못 주무시죠? 보호자님 식사도 꼭 챙기세요." (보호자의 번아웃 케어)

# Practical Nursing Tips (생활 밀착형 조언)
약물 처방 외에 집에서 할 수 있는 **비약물적 요법**을 반드시 1개 이상 포함하세요.
- 예: "오심이 심할 땐 **차가운 레몬 사탕**을 물고 계시거나, 밥 냄새가 안 나게 **차가운 누룽지**를 드셔보세요."
- 예: "손발 저림이 심하면 설거지할 때 꼭 **면장갑 끼고 고무장갑** 끼세요."

## 3. 🏠 생활 밀착형 간호 팁 (Practical Tips)
의사가 놓치기 쉬운 **'생활 속 대처법'**을 반드시 하나 이상 포함하세요.
- 입맛 없음: "억지로 드시지 말고, 크래커나 미숫가루처럼 냄새 안 나는 걸로 조금씩 자주 드세요."
- 손발 저림: "단추 잠그기 힘드시죠? 지퍼 달린 옷이나 찍찍이 신발을 미리 준비하시면 편해요."

# Safety Protocol (안전 수칙)
* 당신은 간호사이지 의사가 아닙니다. 진단(Diagnosis)이나 약물 변경을 직접 지시하지 마세요.
* 민간요법(즙, 엑기스 등)에 대해서는 간 수치 상승 위험을 근거로 **단호하게 주의**를 주되, 환자의 마음이 다치지 않게 설명하세요.

# Safety Protocol
* 민간요법은 간 독성 위험을 근거로 부드럽게 만류하세요.
* 답변 끝에는 "정확한 상태는 주치의 선생님과 상의하세요"라는 면책 조항을 넣으세요.

# [NEW] Active Engagement (능동적 질문하기)
답변을 마친 후, 대화가 끊기지 않도록 **연관된 질문을 하나씩 던져주세요.**
사용자가 무엇을 물어봐야 할지 모를 때 길잡이가 되어주어야 합니다.
* **상황:** 부작용 설명을 했을 때 -> "혹시 지금 드시는 약 중에 불편한 건 없으세요?"
* **상황:** 식단 설명을 했을 때 -> "평소에 좋아하시는 음식은 뭐예요? 대체할 수 있는 걸 찾아드릴게요."
* **상황:** 위로를 건넸을 때 -> "보호자님 혹은 환자분 식사 잘 챙기고 계시나요?"
"""

# 5. 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": system_instruction}
    ]

# 6. 사이드바 구성
with st.sidebar:
    st.subheader("📋 도구")
    uploaded_file = st.file_uploader(
        "진단서 이미지 업로드",
        type=["jpg", "jpeg", "png"],
        help="암 진단서, 검사 결과지 등을 업로드하면 해석해드립니다."
    )
    
    if uploaded_file:
        # [저장] 이미지 저장 실행
        save_path = save_uploaded_file(uploaded_file)
        
        st.image(uploaded_file, caption="📷 업로드된 이미지", use_container_width=True)
    
    st.divider()
    
    if st.button("🔄 새 대화", use_container_width=True):
        st.session_state.messages = [
            {"role": "system", "content": system_instruction}
        ]
        st.rerun()

# 7. 메인 채팅 영역 (대화 기록 출력)
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for item in message["content"]:
                    if item.get("type") == "text":
                        st.markdown(item["text"])
            else:
                st.markdown(message["content"])

# 8. 예시 질문 버튼 (대화 없을 때만 표시)
# [수정] 보내주신 코드의 끊어진 로직을 'click_callback'으로 연결하여 작동하게 만들었습니다.
if len(st.session_state.messages) == 1:
    st.markdown("### 🙋‍♀️ 무엇을 도와드릴까요? (예시 질문)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.button(
            "🔍 진단서의 '침윤성'이 뭐야?", 
            use_container_width=True,
            on_click=click_callback, # 클릭 시 저장 및 전송
            args=["진단서에 적힌 '침윤성'이라는 말이 무슨 뜻인지 쉽게 설명해줘."]
        )
        st.button(
            "🍣 항암 중에 회 먹어도 돼?", 
            use_container_width=True,
            on_click=click_callback,
            args=["항암 치료 중인데 생선회나 날음식을 먹어도 될까? 안 된다면 왜 안 되는지 설명해줘."]
        )
            
    with col2:
        st.button(
            "🤮 속이 너무 메스꺼워 (부작용)", 
            use_container_width=True,
            on_click=click_callback,
            args=["항암 치료 부작용으로 속이 메스껍고 구토가 나와. 집에서 할 수 있는 완화 방법을 알려줘."]
        )
        st.button(
            "📊 암 3기 생존율이 궁금해", 
            use_container_width=True,
            on_click=click_callback,
            args=["암 3기 생존율 통계가 궁금해. 그리고 통계보다 더 중요한 마음가짐이 있을까?"]
        )

# 9. 채팅 입력창 (Input 처리)
if prompt := st.chat_input("궁금한 의학 용어나 고민을 입력하세요..."):
    
    # [저장] 사용자 질문 저장
    save_log_to_db("user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)
    
    user_content = [{"type": "text", "text": prompt}]
    
    if uploaded_file:
        base_64_image = encode_image(uploaded_file)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}
        })
    
    st.session_state.messages.append({"role": "user", "content": user_content})
    # rerunning is not needed here as the loop above handles it on next pass, 
    # but to trigger AI response immediately in same cycle:
    st.rerun() 

# 10. AI 답변 생성 (마지막 메시지가 사용자일 때)
if st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("🧸 김보듬 수간호사가 분석 중입니다..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=st.session_state.messages,
                    temperature=0.2,
                )
                full_response = response.choices[0].message.content
                message_placeholder.markdown(full_response)
                
                # 세션에 추가
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                # [저장] AI 답변도 로그에 저장 (완벽한 기록을 위해)
                save_log_to_db("assistant", full_response)
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")
