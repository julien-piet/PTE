import os
<<<<<<< HEAD
from pydantic_ai import models
=======
from langchain_google_genai import ChatGoogleGenerativeAI
>>>>>>> b20074fcade00dfff39c6d4c3d93334193e2640e

class GoogleProvider(object):

    def __init__(self, config):
        pass

    def get_llm_model(self, config, model_name):
        model = None
        for model in config.llm_providers.google:
            if model.model == model_name:
                break
        if not model:
<<<<<<< HEAD
            raise Exception(f'{model_name} for Google provider not found in the config.yaml file')
        
        # Use direct Gemini API instead of Vertex AI
        # pydantic-ai uses GOOGLE_API_KEY, but also check GEMINI_API_KEY for backwards compatibility
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable must be set")

        return f"google-gla:{model.model}"  # pydantic-ai format for Gemini
=======
            raise Exception(f'{model_name} for Google Gemini provider not found in the config.yaml file')

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable must be set for Google Gemini backend.")

        return ChatGoogleGenerativeAI(
            model=model.model,
            temperature=model.temp,
            google_api_key=api_key,
        )
>>>>>>> b20074fcade00dfff39c6d4c3d93334193e2640e
