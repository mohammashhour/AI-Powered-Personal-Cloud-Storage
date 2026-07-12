from sentence_transformers import SentenceTransformer

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue
)

COLLECTION_NAME = "drive_files"

client = QdrantClient(
    host="localhost",
    port=6333
)

model = SentenceTransformer(
    "BAAI/bge-base-en-v1.5"
)

def search_files(query, user_id):
    query_embedding = model.encode(query).tolist()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(
                        value=user_id
                    )
                )
            ]
        ),
        limit=3
    ).points
    return results