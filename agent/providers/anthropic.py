
from langchain_anthropic import ChatAnthropic
import os

class AnthropicProvider(object):

    def __init__(self, config):
        pass;

    def get_llm_model(self, config, model_name):
        model = None
        for model in config.llm_providers.anthropic:
            if model.model == model_name:
                break
        if not model:
            raise (f'{model} for Anthropic provider  not found in the config.yaml file ')

        return ChatAnthropic(anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                model = model.model,
                temperature = model.temp)
