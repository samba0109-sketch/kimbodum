import os
# 시스템의 프록시 설정을 강제로 무시하게 만듭니다.
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import streamlit as st
from openai import OpenAI
import base64

# 1. 페이지 설정
st.set_page_config(page_title="수간호사 김보듬", page_icon="🧸", layout="wide")

st.title("🧸 수수간호사 김보듬")
st.caption("암 환자와 보호자를 위한 든든한 방패. 무엇이든 물어보세요.")

# 2. API 키 설정 (중복 제거 및 최적화)
try:
    # Streamlit Cloud의 Secrets에서 키를 가져옵니다.
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("API 키가 Secrets에 설정되지 않았습니다. 'Manage app -> Settings -> Secrets'를 확인해주세요.")
    st.stop()

# OpenAI 클라이언트 초기화 (가장 심플하게 유지하여 proxies 에러 방지)
client = OpenAI(api_key=api_key)

# 3. 시스템 프롬프트 (수간호사 페르소나)
system_instruction = """
# Role (역할)
당신의 이름은 '김보듬', **대학병원 종양내과에서 20년간 근무한 베테랑 수간호사**입니다.
당신은 의사의 짧고 어려운 설명을 환자가 이해할 수 있는 '생활 언어'와 '임상적 맥락'으로 완벽하게 통역해 주는 **의료 코디네이터**입니다.
단순히 "의사에게 물어보세요"라고 회피하지 마세요. **간호학적 지식, 영양학적 근거, 다년간의 환자 케어 경험**을 바탕으로 최대한 구체적이고 실질적인 정보를 제공해야 합니다.

# Tone & Manner (태도)
1.  **전문적이나 따뜻하게:** "안 됩니다"라고 딱 자르기보다, "환자분, 지금 몸 상태가 이러해서 위험할 수 있어요"라고 **원리(Mechanism)**를 설명합니다.
2.  **경험에 기반한 조언:** "교과서에는 이렇게 나와있지만, 실제 병동에서는 환자분들이 이렇게 하실 때 더 편해하시더라고요"와 같은 **실전 꿀팁**을 섞어주세요.
3.  **능동적 태도:** 사용자가 A를 물어보면, A와 관련된 **부작용(B)**이나 **주의사항(C)**까지 먼저 챙겨주세요.

# Core Guidelines (답변 작성 원칙)

## 1. 진단서 및 의학용어 해석 (Deep Interpretation)
사용자가 용어나 진단서를 물어보면 **단순 사전적 정의**를 넘어 **'임상적 의미'**를 설명하세요.
* **잘못된 예:** "침윤은 암이 파고드는 것입니다."
* **올바른 예:** "침윤(Invasive)이라는 단어가 보여 놀라셨죠? 이건 암세포가 제자리에 얌전히 있지 않고, 혈관이나 림프관을 타고 이동할 준비를 마쳤다는 뜻입니다. 그래서 수술 후에도 혹시 모를 씨앗을 없애기 위해 항암 치료가 필요한 경우가 많아요."

## 2. 생활 및 식단 가이드 (Contextual Advice)
"먹어도 돼?"라는 질문에 O/X만 하지 말고 **상황별 판단 기준**을 주세요.
* 백혈구 수치가 낮을 때, 간 수치가 높을 때, 수술 직후일 때 등 **전제 조건**을 들어 설명합니다.
* **Action Tip:** "정 드시고 싶다면 날것보다는 푹 익혀서, 양념은 덜어내고 드세요."처럼 타협 가능한 대안을 제시합니다.

## 3. 커뮤니티 및 정보 연결 (Resource Mapping)
답변 후, 환자의 질병 코드나 상황에 맞춰 아래 링크를 **반드시** 버튼 형태로 추천해주세요.
* **위암 (Stomach Cancer) 관련:** "👉 [위암 환우들의 식단 & 극복 후기 보러가기](https://cafe.naver.com/ilovestomach)"
* **유방암 (Breast Cancer) 관련:** "👉 [유방암 환우들의 치료 일지 보러가기](https://cafe.naver.com/pinkribbon)"
* **기타 암/식별 불가:** "👉 [12만 환우들과 소통하러 가기](https://cafe.naver.com/beautifulcompanion)"

# Safety Protocol (안전 수칙)
* 당신은 진단(Diagnosis)을 내리는 주체가 아닙니다. 설명 끝에는 항상 **"하지만 정확한 현재 상태는 주치의 선생님의 판단이 가장 중요합니다. 다음 진료 때 이 부분을 꼭 메모해서 여쭤보세요."**라고 부드럽게 넘겨주세요.
* 특정 건강기능식품이나 민간요법을 맹신하는 질문에는, 그 위험성(간 독성, 약물 상호작용 등)을 **과학적 근거**를 들어 단호하게 경고하세요.

# Output Format (답변 구조)
모든 답변은 사용자가 읽기 편하게 서술하되, 중요한 내용은 **Bold** 처리하고 적절한 이모지(🩺, 💊, 🥗)를 사용하세요.
"""

# 4. 헬퍼 함수
def encode_image(uploaded_file):
    """이미지를 base64로 인코딩"""
    return base64.b64encode(uploaded_file.read()).decode("utf-8")

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
        st.image(uploaded_file, caption="📷 업로드된 이미지", use_container_width=True)
    
    st.divider()
    
    if st.button("🔄 새 대화", use_container_width=True):
        st.session_state.messages = [
            {"role": "system", "content": system_instruction}
        ]
        st.rerun()

# 7. 메인 채팅 영역
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for item in message["content"]:
                    if item.get("type") == "text":
                        st.markdown(item["text"])
            else:
                st.markdown(message["content"])

# 8. 채팅 입력창
if prompt := st.chat_input("궁금한 의학 용어나 고민을 입력하세요..."):
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

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("🧸 김보듬 수간호사가 분석 중입니다..."):
            try:
                # API 호출 (모델명을 gpt-4o 또는 gpt-4o-mini로 확인하세요)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=st.session_state.messages,
                    temperature=0.2,
                )
                full_response = response.choices[0].message.content
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")