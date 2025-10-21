from typing import List, Dict, Any
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
        prompt = open("prompt_templates/preprocess.py").read().format(dialogue=dialogue)
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

    def __call__(self, dialogue: List[Dict[str, Any]]):
        sale_dialogue,  preprocess_token = self.extract_speaker_roles(dialogue)
        return sale_dialogue, preprocess_token

