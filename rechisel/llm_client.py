import json
import os
import logging
import dotenv
import boto3
from functools import lru_cache
from typing import List, Dict, Literal, Optional


dotenv.load_dotenv()

assert 'OPENAI_API_KEY' in os.environ, 'OPENAI_API_KEY is not set'
assert 'OPENAI_API_ENDPOINT' in os.environ, 'OPENAI_API_ENDPOINT is not set'
assert 'AWS_ACCESS_KEY_ID' in os.environ, 'AWS_ACCESS_KEY_ID is not set'
assert 'AWS_SECRET_ACCESS_KEY' in os.environ, 'AWS_SECRET_ACCESS_KEY is not set'
assert 'BEDROCK_REGION_NAME_FOR_35' in os.environ, 'BEDROCK_REGION_NAME_FOR_35 is not set'

import openai
from openai import OpenAI


@lru_cache(maxsize=1)
def get_openai_client():
    return OpenAI(
        api_key=os.environ['OPENAI_API_KEY'],
        base_url=os.environ['OPENAI_API_ENDPOINT'],
    )


@lru_cache(maxsize=1)
def get_claude_client():
    return boto3.client(
        service_name="bedrock-runtime", 
        region_name=os.environ['BEDROCK_REGION_NAME_FOR_35'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
    )


def get_openai_completion(
        messages: List[Dict[Literal["role", "content"], str]], 
        model="gpt-4o-mini", 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        on_error: Literal['raise', 'ignore'] = 'raise'
):
    def _get_openai_completion():
        response = get_openai_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        # If response.error exists, it means that the request failed
        if hasattr(response, 'error'):
            raise Exception(response.error)
        res = response.choices[0].message.content
        # Get the number of tokens used for prompt and completion
        prompt_tokens_num = response.usage.prompt_tokens
        output_tokens_num = response.usage.completion_tokens
        return res, prompt_tokens_num, output_tokens_num
    
    if on_error == 'ignore':
        try:
            res, prompt_tokens_num, output_tokens_num = _get_openai_completion()
            return res, prompt_tokens_num, output_tokens_num
        except openai.APIConnectionError as e:
            logging.error(f'The server could not be reached, cause:{e.__cause__}')
        except openai.RateLimitError as e:
            logging.error('A 429 status code was received; we should back off a bit.')
        except openai.APIStatusError as e:
            logging.error(
                f'Another non-200-range status code was received, status_code: {e.status_code}, error response: {e.response}')
        except Exception as e:
            logging.error(f'An error occurred: {e}')
        return '', 0, 0
    elif on_error == 'raise':
        try:
            return _get_openai_completion()
        except Exception as e:
            raise e


def get_claude_completion(
        messages: List[Dict[Literal["role", "content"], str]],
        model: str,
        on_error: Literal['raise', 'ignore'] = 'raise'
):
    def _get_claude_completion():
        body = json.dumps({
            "messages": messages,
            "max_tokens": 8192,
            "anthropic_version": "bedrock-2023-05-31"
        })
        response = get_claude_client().invoke_model(
            body=body, 
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("content")[0]['text'], 0, 0
    
    if on_error == 'ignore':
        try:
            return _get_claude_completion(), 0, 0
        except Exception as e:
            logging.error(f'An error occurred: {e}')
        return '', 0, 0
    elif on_error == 'raise':
        try:
            return _get_claude_completion()
        except Exception as e:
            raise e



def get_model_completion(
        messages: List[Dict[Literal["role", "content"], str]],
        model: str,
        on_error: Literal['raise', 'ignore'] = 'raise'
):
    if model.startswith("gpt"):
        return get_openai_completion(messages, model=model, on_error=on_error)
    elif model.startswith("anthropic"):
        # Replace all `system` roles with `user` roles
        for message in messages:
            if message["role"] == "system":
                message["role"] = "user"
        return get_claude_completion(messages, model=model, on_error=on_error)
    else:
        raise ValueError(f"Invalid model name: {model}")



if __name__ == '__main__':
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of China."}
    ]
    model = "anthropic.claude-3-5-haiku-20241022-v2:0"
    print(get_model_completion(messages, model=model)[0])
