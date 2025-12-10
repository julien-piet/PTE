
import os
from langchain_openai import ChatOpenAI

class OpenAIProvider(object):

    def __init__(self, config):
        pass;

    def get_llm_model(self, config, model_name):
        model = None
        for model in config.llm_providers.openai:
            if model.model == model_name:
                break
        if not model:
            raise (f'{model_name} for openAI provider  not found in the config.yaml file ')
        return ChatOpenAI(api_key=os.environ["OPENAI_API_KEY"],
                  model = model.model,
                  temperature = model.temp)
