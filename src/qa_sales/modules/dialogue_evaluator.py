from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import os

load_dotenv()


class ScriptEvaluator:
    def __init__(self,
                 model: str = "gpt-4.1-mini",
                 prompt_template: str = "prompt_templates/evaluate_script.txt"):
        self.llm = ChatOpenAI(model=model,
                              temperature=0.0,
                              api_key=os.getenv("OPENAI_API_KEY"),
                              base_url=os.getenv("BASE_URL"))
        prompt = open(prompt_template).read()
        self.prompt = PromptTemplate.from_template(prompt)

    def __call__(self, sale_texts: str,
                 step_detail: str) -> str:
        chain = self.prompt | self.llm
        response = chain.invoke({
            "sale_texts": sale_texts,
            "step_detail": step_detail
        })
        return response.content



