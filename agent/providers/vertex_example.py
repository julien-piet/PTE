#!/usr/bin/env python3
"""
Example usage of Vertex AI provider for MiniScope

This example demonstrates how to configure and use the Vertex AI provider
with Google Cloud authentication and project setup.
"""

import os
import sys
from pathlib import Path

from miniscope.providers.provider import ModelProvider
from miniscope.common.configurator import Configurator

def setup_vertex_environment():
    """Setup environment variables for Vertex AI"""
    # Set your Google Cloud project ID
    os.environ["GOOGLE_CLOUD_PROJECT"] = "your-project-id"
    
    # Set the location (optional, defaults to us-central1)
    os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
    
    # Ensure you have authenticated with gcloud
    # Run: gcloud auth application-default login

def main():
    """Main example function"""
    print("Vertex AI Provider Example")
    print("=" * 40)
    
    # Setup environment
    setup_vertex_environment()
    
    # Load configuration
    config = Configurator()
    
    # Create a provider instance for Vertex AI
    provider = ModelProvider(
        config=config,
        model_provider="google",
        model_name="gemini-1.5-flash"
    )
    
    try:
        # Get the LLM model
        llm = provider.get_llm_model_provider()
        
        # Test the model with a simple prompt
        test_prompt = "Hello! Can you help me understand what permissions I need for a Gmail API integration?"
        
        print(f"Testing Vertex AI with prompt: {test_prompt}")
        print("-" * 40)
        
        response = llm.invoke(test_prompt)
        print(f"Response: {response.content}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have set GOOGLE_CLOUD_PROJECT environment variable")
        print("2. Ensure you have authenticated with: gcloud auth application-default login")
        print("3. Verify your project has Vertex AI API enabled")
        print("4. Check that the model name is available in your region")

if __name__ == "__main__":
    main()
