import os

class AnthropicProvider(object):

    def __init__(self, config):
        pass

    def get_llm_model(self, config, model_name):
        model = None
        for m in config.llm_providers.anthropic:
            if m.model == model_name:
                model = m
                break
        if model is None:
            raise Exception(f'{model_name} for Anthropic provider not found in the config.yaml file')

        # Validate API key exists
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable must be set")

        # Return pydantic-ai format string
        return f"anthropic:{model.model}"
