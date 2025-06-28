from time import sleep
import os
from typing import Literal, Optional, Union
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
import botocore.config


class BedrockClaudeClient(ChatBedrock):
    
    def __init__(
        self, 
        model: str,
        *,
        region: str = 'us-west-2',
        streaming: bool = False, 
        max_tokens: int = 8192,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
    ):
        # model ID mapping
        MODEL_ID_MAPPING = {
            'claude-3.5-sonnet-v2': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            'claude-3.5-haiku': 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
        }

        # Validate AWS credentials
        aws_access_key_id = self._get_required_env_var("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = self._get_required_env_var("AWS_SECRET_ACCESS_KEY")
        
        # Build model kwargs efficiently
        model_kwargs = {
            key: value for key, value in {
                'temperature': temperature,
                'top_k': top_k,
                'top_p': top_p
            }.items() if value is not None
        }

        super().__init__(
            model_id=MODEL_ID_MAPPING[model],
            region=region,
            streaming=streaming,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            max_tokens=max_tokens,
            model_kwargs=model_kwargs,
            config=botocore.config.Config(
                connect_timeout=30,
                read_timeout=12000,
            )
        )
    
    @staticmethod
    def _get_required_env_var(var_name: str) -> str:
        """Get required environment variable or raise ValueError."""
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"{var_name} is not set for BedrockClaudeClient.")
        return value


class OpenAIClient(ChatOpenAI):
    """OpenAI client with simplified initialization."""
    
    def __init__(
        self, 
        model: str, 
        *,
        streaming: bool = False, 
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        proxy: Optional[str] = None
    ):
        super().__init__(
            model=model,
            streaming=streaming,
            temperature=temperature,
            top_p=top_p,
            max_completion_tokens=max_tokens,
            max_tokens=max_tokens,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
            openai_proxy=proxy or os.getenv("OPENAI_PROXY"),
        )



@lru_cache()
def get_llm_client(model: str, **kwargs) -> Union[OpenAIClient, BedrockClaudeClient]:

    MODEL_GROUPS = {
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1'],
        'claude': ['claude-3.5-haiku', 'claude-3.5-sonnet-v2'],
    }

    CLIENT_CLASSES = {
        'openai': OpenAIClient,
        'claude': BedrockClaudeClient,
    }

    for group, models in MODEL_GROUPS.items():
        if model in models:
            client_class = CLIENT_CLASSES[group]
            return client_class(model=model, **kwargs)
    
    raise ValueError(f"Model '{model}' is not supported.")


class LLMAPICallError(RuntimeError):
    """Exception raised when LLM API calls fail after retries."""
    pass


def llm_call_with_retry(
    client: OpenAIClient | BedrockClaudeClient,
    messages: list[HumanMessage | SystemMessage | AIMessage],
    *,
    retry: int = 16,
    wait_after_retry: float = 0.2
):
    """Call LLM with retry logic on failure."""
    last_exception = None
    
    for attempt in range(1, retry + 1):
        try:
            return client.invoke(messages)
        except Exception as e:
            last_exception = e
            if attempt == retry:
                break
            sleep(wait_after_retry)
    
    raise LLMAPICallError(
        f"Error calling LLM: Retry limit reached with last error: {last_exception}"
    ) from last_exception



def lcmsg_to_msg(lcmsg: list[BaseMessage], accept_system: bool = True) -> list[dict]:
    """Convert LangChain messages to standard message format."""
    
    def get_role(msg: BaseMessage, accept_sys: bool = True) -> Literal["system", "user", "assistant"]:
        """Map message type to role string."""
        role_mapping = {
            SystemMessage: "system" if accept_sys else "user",
            HumanMessage: "user", 
            AIMessage: "assistant"
        }
        return role_mapping.get(type(msg), "user")
    
    return [
        {"role": get_role(msg, accept_system), "content": msg.content}
        for msg in lcmsg
    ]


def msg_to_lcmsg(messages: list[dict]) -> list[BaseMessage]:
    """Convert standard message format to LangChain messages."""
    
    def create_message(role: str, content: str) -> BaseMessage:
        """Create appropriate message type based on role."""
        message_classes = {
            "system": SystemMessage,
            "user": HumanMessage,
            "assistant": AIMessage
        }
        message_class = message_classes.get(role, HumanMessage)
        return message_class(content)
    
    return [
        create_message(msg["role"], msg["content"])
        for msg in messages
    ]


