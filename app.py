import os
# 시스템의 프록시 설정을 강제로 무시하게 만듭니다.
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import streamlit as st
from openai import OpenAI
import base64

# 1. 페이지 설정
st.set_page_config(page_title="수간호사 김보듬", page_icon="🧸", layout="wide")

st.title("🧸 수간호사 김보듬")
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
당신의 이름은 '김보듬'입니다. 암 환자와 보호자를 위한 전문 의료 코디네이터이자 심리적 방패입니다.
국가 공인 데이터에 기반한 정확한 사실만을 전달하며, 전문적이고 다정한 말투를 사용하세요.
항상 답변 하단에 면책 조항을 포함해야 합니다.
"""
# (기존에 작성하신 긴 system_instruction 내용을 여기에 그대로 넣으셔도 됩니다. 
# 지면상 짧게 줄였으니, 실제 파일에는 기존의 긴 내용을 넣으셔도 좋습니다.)

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