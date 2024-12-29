import os
import dspy
from typing import Optional
from configs.logger import logger
from configs.settings import get_settings
class DSPyManager:
    def __init__(self):
        self.lm_configs = {
            "openai": {
                "gpt-4o-mini": "openai/gpt-4o-mini",
                "gpt-4o-mini": "openai/gpt-4o-mini",
                "gpt-4-turbo": "openai/gpt-4-turbo-preview",
                "gpt-3.5-turbo": "openai/gpt-3.5-turbo"
            },
            "anthropic": {
                "claude-3-opus": "anthropic/claude-3-opus-20240229",
                "claude-3-sonnet": "anthropic/claude-3-sonnet-20240229",
                "claude-3-haiku": "anthropic/claude-3-haiku-20240229"
            },
            "gemini": {
                "gemini-1.5-pro": "google/gemini-1.5-pro",
                "gemini-pro": "google/gemini-pro"
            }
        }
        
        # Initialize API keys from environment variables
        self.api_keys = {
            "openai": get_settings().OPENAI_API_KEY,
            "anthropic": get_settings().ANTHROPIC_API_KEY,
            "gemini": get_settings().GOOGLE_API_KEY
        }

    def get_lm(self, provider: str, model: str, temperature: float = 0.7) -> Optional[dspy.LM]:
        """
        Get a configured LM instance based on provider and model
        """
        if provider not in self.lm_configs or model not in self.lm_configs[provider]:
            raise ValueError(f"Unsupported provider/model combination: {provider}/{model}")

        model_path = self.lm_configs[provider][model]
        api_key = self.api_keys[provider]

        if not api_key:
            raise ValueError(f"API key not found for provider: {provider}")

        if provider == "openai":
            return dspy.LM(model_path, api_key=api_key, temperature=temperature)
        elif provider == "anthropic":
            return dspy.LM(model_path, api_key=api_key, temperature=temperature)
        elif provider == "gemini":
            return dspy.LM(model_path, api_key=api_key, temperature=temperature)
        
        return None

    def configure_default_lm(self, provider: str = "openai", model: str = "gpt-4o-mini", temperature: float = 0.7):
        """
        Configure the default LM for DSPy
        """
        logger.info(f"Configuring LM: {provider}/{model}")
        lm = self.get_lm(provider, model, temperature)
        dspy.configure(lm=lm)
        return None