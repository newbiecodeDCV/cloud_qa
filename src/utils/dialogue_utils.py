import httpx
import asyncio
from io import BytesIO


PRIVATE_TOKEN = "41ad97aa3c747596a4378cc8ba101fe70beb3f5f70a75407a30e6ddab668310d"


async def call_dialogue_api(audio_bytes: bytes,
                            task_id: int):
    dialogue_url = "https://speech.aiservice.vn/asr/dialogue"
    result_url = "https://speech.aiservice.vn/asr/dialogue_result"
    headers = {'Authorization': PRIVATE_TOKEN}
    files = {'file': ('dialogue.wav', BytesIO(audio_bytes), 'audio/wav')}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(dialogue_url, headers=headers,
                                     data={'task_id': str(task_id)},
                                     files=files)
        task_id = response.json().get("task_id", None)
        if not task_id:
            return {'status': -1, 'message': 'Failed to start dialogue processing'}
        result_payload = {'task_id': task_id}
        while True:
            result_response = await client.post(result_url, headers=headers, data=result_payload)
            result_data = result_response.json()
            if result_data['status'] == 1:
                return {'status': 1,
                        'task_id': task_id,
                        'dialogue': result_data['result']['spk_dialogue'],
                        'message': 'Get dialogue complete'}
            elif result_data['status'] == -1:
                return {'status': -1,
                        'task_id': task_id,
                        'message': 'Get dialogue failed'}
            await asyncio.sleep(0.5)
