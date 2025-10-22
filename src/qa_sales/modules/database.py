from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import CSVLoader, WebBaseLoader
from dotenv import load_dotenv
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
base_url = os.getenv("BASE_URL")
api_key = os.getenv("OPENAI_API_KEY")


def create_csvdatabase(csv_path: str,
                       embedding_model: str,
                       db_path: str,
                       ) -> FAISS:
    embeddings = OpenAIEmbeddings(model=embedding_model,
                                  base_url=base_url,
                                  api_key=api_key)
    if not os.path.exists(db_path):
        logger.info("Creating new FAISS database...")
        loader = CSVLoader(file_path=csv_path,
                           content_columns=['step_description'],
                           metadata_columns=['step_id', 'step_name', 'step_criteria'])
        documents = loader.load()
        faiss_db = FAISS.from_documents(documents, embeddings)
        faiss_db.save_local(db_path)
        return faiss_db

    else:
        logger.info("Loading existing FAISS database...")
        faiss_db = FAISS.load_local(db_path, embeddings)


