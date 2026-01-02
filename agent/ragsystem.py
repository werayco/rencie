from langchain.tools import tool
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from pymongo import MongoClient
from langchain_text_splitters import RecursiveCharacterTextSplitter
import warnings
import os
from dotenv import load_dotenv
import numpy as np

vectordbpath = os.path.join(os.getcwd(), "faissDB")
warnings.filterwarnings("ignore")

# load_dotenv(dotenv_path=r".\all.env")

MONGO = os.getenv("MONGODB")
client = MongoClient(MONGO)
news_db = client["renci_db"]
news_collection = news_db["finance_news"]

news_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"})

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

@tool
def search_finance_news(query: str) -> str:
    """Search for the latest finance news articles relevant to the user's query. Use this when users ask about market news, stocks, crypto, economy, or financial events."""
    
    query_embedding = news_model.embed_query(query)  # Already returns a list
    
    articles = list(news_collection.find(
        {},
        {"embedding": 1, "title": 1, "summary": 1, "link": 1, "published": 1}
    ).sort("fetched_at", -1).limit(200))
    
    if not articles:
        return "No finance news available at the moment."
    
    scored = []
    for article in articles:
        if "embedding" in article and article["embedding"]:
            score = cosine_similarity(query_embedding, article["embedding"])
            scored.append((score, article))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    top_articles = scored[:5]
    
    if not top_articles:
        return "No relevant finance news found for your query."
    
    results = []
    for score, article in top_articles:
        published = article.get("published", "Unknown date")
        summary = article.get("summary", "No summary available.")
        results.append(
            f"**{article['title']}**\n"
            f"{summary}\n"
            f"Published: {published}\n"
            f"Link: {article['link']}"
        )
    return "\n\n---\n\n".join(results)


def vectorstorecreator(filepath, db_path="faissDB"):
    docs = PyPDFLoader(filepath).load()
    textsplitter = RecursiveCharacterTextSplitter(
        chunk_size=200, separators=["\n\n", "\n", " ", ""]
    )
    document_chunks = textsplitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )
    faiss_vector_database = FAISS.from_documents(document_chunks, embeddings)
    faiss_vector_database.save_local(db_path)

# vectorstorecreator(r"C:\Users\ADMIN\Downloads\Rencie Faq Pdf.pdf")

@tool
def vectordbMemory(query):
    "this vector database tool should be used when the query of the user is about Renci FAQ"
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )
    vector_store = FAISS.load_local(
        vectordbpath, embeddings, allow_dangerous_deserialization=True
    )
    retriever = vector_store.as_retriever()
    response = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in response])
    return context

