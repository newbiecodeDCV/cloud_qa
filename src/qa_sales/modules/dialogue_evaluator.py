from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Any
from dotenv import load_dotenv
from ast import literal_eval
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

    def score_and_response(self,
                           criteria_evals: List[Dict[str, Any]],
                           criteria_score: Dict[int, float]) -> Dict:
        for criteria_eval in criteria_evals:
            criteria_id = criteria_eval['criteria_id']
            criteria_eval['score'] = criteria_score.get(criteria_id, 0) * criteria_eval['status']
        return criteria_evals

    def __call__(self,
                 sale_texts: str,
                 step_detail: str,
                 criteria_score: Dict[int, float]) -> str:
        chain = self.prompt | self.llm
        response = chain.invoke({
            "sale_texts": sale_texts,
            "step_detail": step_detail
        })
        criteria_evals = literal_eval(response.content)
        criteria_evals = self.score_and_response(criteria_evals, criteria_score)
        return criteria_evals

