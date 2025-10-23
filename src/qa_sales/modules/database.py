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
                           content_columns=['step_description'],
                           metadata_columns=['step_id', 'step_name', 'step_criteria'])
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


def classify_utterances_to_steps(utterances: List[Dict[str, Any]],
                                 chroma_db: Chroma,
                                 top_k: int = 3) -> List[Dict[str, Any]]:

    step_texts = {}
    for utterance in utterances:
        query = utterance['text']
        nearest_step = chroma_db.similarity_search(query, k=top_k)[0]
        nearest_step_id = nearest_step.metadata['step_id']
        if nearest_step_id not in step_texts:
            step_texts[nearest_step_id] = [query]
        else:
            step_texts[nearest_step_id].append(query)
    result = ""
    for step_id, texts in step_texts.items():
        result += f"step ID: {step_id}\n"
        for text in texts:
            result += f"- {text}\n"
        result += "\n"
    return result


def from_db_to_text(chroma_db: Chroma) -> str:
    result = ""
    all_metadatas = chroma_db.get(include=["metadatas"])
    for metadata in all_metadatas['metadatas']:
        step_id = metadata['step_id']
        step_name = metadata['step_name']
        step_criteria = metadata['step_criteria']
        result += f"step ID: {step_id}\nstep Name: {step_name}\n step Criteria: {step_criteria}\n\n"
    return result
