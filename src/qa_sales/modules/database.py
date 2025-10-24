from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import CSVLoader, WebBaseLoader
from dotenv import load_dotenv
from typing import List, Dict, Any
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
        logger.info("Creating new Chroma database...")
        loader = CSVLoader(file_path=csv_path,
                           content_columns=['criteria_description'],
                           metadata_columns=['criteria_id', 'criteria_name', 'criteria_actions'])
        documents = loader.load()
        chroma_db = Chroma.from_documents(documents=documents,
                                          embedding=embeddings,
                                          persist_directory=db_path)
        chroma_db.persist()
        return chroma_db

    else:
        logger.info("Loading existing Chroma database...")
        chroma_db = Chroma(embedding_function=embeddings,
                           persist_directory=db_path)


def classify_utterances_to_criteria(utterances: List[Dict[str, Any]],
                                    chroma_db: Chroma,
                                    top_k: int = 3) -> List[Dict[str, Any]]:

    criteria_texts = {}
    for utterance in utterances:
        query = utterance['text']
        nearest_criteria = chroma_db.similarity_search(query, k=top_k)[0]
        nearest_criteria_id = nearest_criteria.metadata['criteria_id']
        if nearest_criteria_id not in criteria_texts:
            criteria_texts[nearest_criteria_id] = [query]
        else:
            criteria_texts[nearest_criteria_id].append(query)
    result = ""
    for criteria_id, texts in criteria_texts.items():
        result += f"criteria ID: {criteria_id}\n"
        for text in texts:
            result += f"- {text}\n"
        result += "\n"
    return result


def from_db_to_text(chroma_db: Chroma) -> str:
    result = ""
    all_metadatas = chroma_db.get(include=["metadatas"])
    for metadata in all_metadatas['metadatas']:
        criteria_id = metadata['criteria_id']
        criteria_name = metadata['criteria_name']
        criteria_actions = metadata['criteria_actions']
        result += f"criteria ID: {criteria_id}\ncriteria Name: {criteria_name}\ncriteria Actions: {criteria_actions}\n\n"
    return result
