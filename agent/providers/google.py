import os
from langchain_google_genai import ChatGoogleGenerativeAI

class GoogleProvider(object):

    def __init__(self, config):
        pass

    def get_llm_model(self, config, model_name):
        model = None
        for model in config.llm_providers.google:
            if model.model == model_name:
                break
        if not model:
            raise Exception(f'{model_name} for Google Gemini provider not found in the config.yaml file')

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable must be set for Google Gemini backend.")

        return ChatGoogleGenerativeAI(
            model=model.model,
            temperature=model.temp,
            google_api_key=api_key,
        )