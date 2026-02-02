import streamlit as st
from openai import OpenAI
import os

st.title("💬 질문 → 답변 앱")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

question = st.text_input("질문을 입력하세요")

if st.button("질문하기"):
    if question.strip() == "":
        st.warning("질문을 입력하세요")
    else:
        with st.spinner("생각 중..."):
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": question}]
            )
        st.success("답변")
        st.write(res.choices[0].message.content)