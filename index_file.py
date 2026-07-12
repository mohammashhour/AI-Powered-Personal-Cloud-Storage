from pathlib import Path
import uuid
from pypdf import PdfReader
from pdf2image import convert_from_path
from docx import Document
import pytesseract
import tiktoken
import os
from dotenv import load_dotenv, dotenv_values
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct
)

load_dotenv()

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

POPPLER_PATH = os.getenv("PATH")

client = QdrantClient(
    host="localhost",
    port=6333
)
COLLECTION_NAME = "drive_files"
model = SentenceTransformer(
    "BAAI/bge-base-en-v1.5"
)
VECTOR_SIZE = 768
collections = [
    c.name
    for c in client.get_collections().collections
]
if COLLECTION_NAME not in collections:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )

encoding = tiktoken.get_encoding(
    "cl100k_base"
)

def chunk_text(
    text,
    chunk_size=400,
    overlap=100
):
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk = encoding.decode(
            tokens[start:end]
        )
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def index_file(
    file_path,
    user_id,
    username,
    data_id
):
    path = Path(file_path)
    text = ""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        if len(text.split()) < 10:
            images = convert_from_path(
                path,
                dpi=300,
                poppler_path=POPPLER_PATH
            )
            text = ""
            for image in images:
                text += pytesseract.image_to_string(image)
    elif suffix in (
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".webp"
    ):
        text = pytesseract.image_to_string(
            str(path)
        )
    elif suffix == ".docx":
        doc = Document(path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    elif suffix == ".txt":
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    else:
        return
    if not text.strip():
        return
    chunks = chunk_text(text)
    points = []
    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "username": username,
                    "data_id": data_id,
                    "file": path.name,
                    "path": str(path),
                    "chunk_id": i,
                    "text": chunk
                }
            )
        )
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )