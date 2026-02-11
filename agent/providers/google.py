import os
from langchain_google_vertexai import ChatVertexAI

class GoogleProvider(object):

    def __init__(self, config):
        pass

    def get_llm_model(self, config, model_name):
        model = None
        for model in config.llm_providers.google:
            if model.model == model_name:
                break
        if not model:
            raise Exception(f'{model_name} for Vertex AI provider not found in the config.yaml file')
        
        return ChatVertexAI(
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", "secure-agent-451919"),  # Your project ID
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),        # Your region
            model_name=model.model,
            temperature=model.temp
        )