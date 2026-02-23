"""
관리자용 문서 업로드 스크립트
사용법: python upload_docs.py <파일경로 또는 URL>

실행 전 환경변수 설정:
  export OPENAI_API_KEY="sk-..."
  export SUPABASE_URL="https://xxxx.supabase.co"
  export SUPABASE_KEY="eyJ..."

예시:
  python upload_docs.py ./cancer_guide.pdf
  python upload_docs.py ./treatment.docx
  python upload_docs.py https://example.com/article
  python upload_docs.py ./notes.txt
"""

import os
import sys

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    WebBaseLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not all([OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ 환경변수를 설정해주세요: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY")
    sys.exit(1)

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model="text-embedding-3-small")


def upload(source: str):
    print(f"📄 로딩 중: {source}")

    if source.startswith("http://") or source.startswith("https://"):
        loader = WebBaseLoader(source)
    elif source.endswith(".pdf"):
        loader = PyPDFLoader(source)
    elif source.endswith(".docx"):
        loader = Docx2txtLoader(source)
    else:
        loader = TextLoader(source, encoding="utf-8")

    docs = loader.load()
    print(f"✅ 문서 로드 완료 ({len(docs)}페이지)")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    print(f"✅ {len(chunks)}개 청크로 분할 완료")

    print("⏳ 임베딩 생성 및 Supabase 저장 중...")
    SupabaseVectorStore.from_documents(
        chunks,
        embeddings,
        client=supabase_client,
        table_name="documents",
        query_name="match_documents",
    )
    print(f"🎉 업로드 완료: {len(chunks)}개 청크 저장됨")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python upload_docs.py <파일경로 또는 URL>")
        sys.exit(1)
    upload(sys.argv[1])
