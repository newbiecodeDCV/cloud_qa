from src.qa_communicate.audio_processing.dialogue import call_dialogue_api
from src.qa_sales.modules.database import create_csvdatabase
from src.qa_sales.modules.dialogue_processor import DialogueProcessor
from src.qa_sales.modules.evaluators import ScriptEvaluator


class QASalesMainProcessor:
    def __init__(self,
                 model: str = "gpt-4.1-mini",
                 csv_path: str = "data/sale_criteria.tsv",
                 eval_prompt_template: str = "prompt_templates/evaluate_script.txt",
                 preprocess_prompt_template: str = "prompt_templates/preprocess.txt",
                 classify_prompt_template: str = "prompt_templates/classify_utterances.txt",
                 db_path: str = "data/sale_criteria_db"):
        self.sale_script_db = create_csvdatabase(csv_path=csv_path,
                                                 db_path=db_path)

        self.dialogue_processor = DialogueProcessor()
        self.script_evaluator = ScriptEvaluator(model=model,
                                                eval_prompt_template=eval_prompt_template,
                                                classify_prompt_template=classify_prompt_template,
                                                chroma_db=self.sale_script_db,
                                                tsv_path=csv_path)
        self.pre_prompt_template = preprocess_prompt_template

    async def run_evaluate(self,
                           audio_bytes: bytes,
                           task_id: int):
        # Get dialogure result from audio
        dialogue_result = await call_dialogue_api(audio_bytes=audio_bytes,
                                                  task_id=task_id)

        if dialogue_result['status'] != 1:
            return {'status': -1,
                    'message': 'Failed to get dialogue from audio'}
        # Process dialogue to extract speaker roles and classify utterances
        processed_result = self.dialogue_processor(dialogue=dialogue_result['dialogue'],
                                                   prompt_template=self.pre_prompt_template)

        if processed_result['status'] != 1:
            return {'status': -1,
                    'message': 'Failed to process dialogue'}

        # Evaluate
        results = self.script_evaluator(dialogue=processed_result['dialogue'])

        if results['status'] != 1:
            return {'status': -1,
                    'message': 'Failed to evaluate dialogue'}
        return results


if __name__ == "__main__":
    processor = QASalesMainProcessor()
    with open("src/qa_sales/modules/232949_173039217479455.wav", "rb") as f:
        audio_bytes = f.read()
    
    import asyncio
    result = asyncio.run(processor.run_evaluate(audio_bytes=audio_bytes,
                                                task_id=1234))
    print(result)