from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import os

load_dotenv()


class DialogueEvaluator:
    def __init__(self,
                 model: str = "gpt-4.1-mini",
                 prompt_template: str = "prompt_templates/evaluate_dialogue.txt"):
        self.llm = ChatOpenAI(model=model,
                              temperature=0.0,
                              api_key=os.getenv("OPENAI_API_KEY"),
                              base_url=os.getenv("BASE_URL"))
        prompt = open(prompt_template).read()
        self.prompt = PromptTemplate.from_template(prompt)

    def __call__(self, step_texts: str,
                 step_criteria: str) -> str:
        chain = self.prompt | self.llm
        response = chain.invoke({
            "step_texts": step_texts,
            "step_criteria": step_criteria
        })
        return response.content

