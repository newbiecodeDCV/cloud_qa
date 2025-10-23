from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from litellm import completion
from dotenv import load_dotenv
import os
import ast
import openai
import json


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("BASE_URL")
print(f"Using OpenAI API key: {api_key}, Base URL: {base_url}")
openai.api_key = api_key
openai.base_url = base_url


class DialogueProcessor:

    def extract_speaker_roles(dialogue: List[Dict[str, Any]]):
        """Extract speaker roles from the dialogue.

        Args:
            dialogue (List[Dict[str, Any]]): The dialogue to process.
            [{"speaker": "0", "text": "Alo em chao anh a"}, ...]

        Returns:
            the dialogue with speaker roles assigned.
            [{"speaker": "nhan vien sale", "text": "Alo em chao anh a"}, ...]
        """
        prompt = open("prompt_templates/preprocess.txt").read().format(dialogue=dialogue)
        messages = [{"role": "user", "content": prompt}]
        try:
            response = completion(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=0.0,
                api_key=api_key,
                base_url=base_url,
            )
        except Exception as e:
            print(f"Error during completion: {e}")

        # ==========================
        # 🔹 Parse kết quả structured
        # ==========================
        arguments = response.choices[0].message.content
        arguments_dict = ast.literal_eval(arguments)
        return arguments_dict, response.usage.total_tokens

    def classify_utterances_to_steps(utterances: List[Dict[str, Any]],
                                     chroma_db: Chroma,
                                     top_k: int = 1) -> List[Dict[str, Any]]:
        for utterance in utterances:
            query = utterance['text']
            nearest_step = chroma_db.similarity_search(query, k=top_k)[0]
            utterance['step_id'] = nearest_step.metadata['step_id']
        return utterances

    def __call__(self, dialogue: List[Dict[str, Any]], chroma_db: Chroma):
        sale_dialogue,  preprocess_token = self.extract_speaker_roles(dialogue)
        sale_dialogue = self.classify_utterances_to_steps(sale_dialogue,
                                                          chroma_db,
                                                          top_k=1)
        return sale_dialogue, preprocess_token

