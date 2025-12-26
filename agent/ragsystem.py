from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import warnings
import os

vectordbpath = os.path.join(os.getcwd(), "faissDB")
warnings.filterwarnings("ignore")

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


from langchain.tools import tool


@tool
def vectordbMemory(query):
    "this vector database tool should be used when the query of the user is about renci"
    db_directory_path = vectordbpath
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )
    vector_store = FAISS.load_local(
        db_directory_path, embeddings, allow_dangerous_deserialization=True
    )
    retriever = vector_store.as_retriever()
    response = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in response])
    return context
