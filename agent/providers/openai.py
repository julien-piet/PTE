import os

class OpenAIProvider(object):

    def __init__(self, config):
        pass

    def get_llm_model(self, config, model_name):
        model = None
        for m in config.llm_providers.openai:
            if m.model == model_name:
                model = m
                break
        if model is None:
            raise Exception(f'{model_name} for OpenAI provider not found in the config.yaml file')

        # Validate API key exists
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable must be set")

        # Return pydantic-ai format string
        return f"openai:{model.model}"
