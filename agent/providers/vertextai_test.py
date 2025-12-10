#!/usr/bin/env python3
"""
LangChain + Vertex AI Gemini Complete Guide

This script shows how to use Vertex AI Gemini through LangChain for:
- Basic chat
- Streaming responses
- Conversation chains
- RAG (Retrieval Augmented Generation)
- Function calling
- Prompt templates

Prerequisites:
pip install langchain langchain-google-vertexai google-cloud-aiplatform
"""

import os
from typing import List, Dict, Any
import json

# LangChain imports
from langchain_google_vertexai import ChatVertexAI, VertexAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import LLMChain, ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

# For RAG example
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_google_vertexai import VertexAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.document_loaders import TextLoader
from langchain.schema import Document

# Configuration - UPDATE THESE
PROJECT_ID = "secure-agent-451919"  # Your project ID
LOCATION = "us-central1"            # Your region
MODEL_NAME = "gemini-2.0-flash-001" # Your model

class LangChainVertexAIDemo:
    def __init__(self, project_id: str, location: str, model_name: str):
        """Initialize LangChain with Vertex AI"""
        print(f"🚀 Setting up LangChain with Vertex AI...")
        
        # Initialize the chat model
        self.chat_model = ChatVertexAI(
            model_name=model_name,
            project=project_id,
            location=location,
            temperature=0.7,
            max_output_tokens=1000,
            # For streaming
            streaming=False,
        )
        
        # Initialize streaming model
        self.streaming_model = ChatVertexAI(
            model_name=model_name,
            project=project_id,
            location=location,
            temperature=0.7,
            max_output_tokens=1000,
            streaming=True,
            callbacks=[StreamingStdOutCallbackHandler()]
        )
        
        print(f"✅ LangChain + Vertex AI initialized")
        print("-" * 60)
    
    def basic_chat_example(self):
        """Basic chat with LangChain"""
        print("💬 BASIC CHAT EXAMPLE")
        print("-" * 30)
        
        # Simple message
        messages = [
            SystemMessage(content="You are a helpful AI assistant specialized in Python programming."),
            HumanMessage(content="Explain list comprehensions in Python with an example")
        ]
        
        response = self.chat_model.invoke(messages)
        print(f"Response: {response.content}")
        print()
    
    def streaming_chat_example(self):
        """Streaming chat responses"""
        print("🌊 STREAMING CHAT EXAMPLE")
        print("-" * 30)
        
        messages = [
            SystemMessage(content="You are a creative writing assistant."),
            HumanMessage(content="Write a short story about a robot learning to paint")
        ]
        
        print("Streaming response:")
        print("-" * 40)
        response = self.streaming_model.invoke(messages)
        print("\n" + "-" * 40)
        print("✅ Streaming complete")
        print()
    
    def prompt_template_example(self):
        """Using prompt templates"""
        print("📝 PROMPT TEMPLATE EXAMPLE")
        print("-" * 30)
        
        # Create a prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert {expertise} with {years} years of experience."),
            ("human", "Please explain {topic} in simple terms with practical examples.")
        ])
        
        # Create chain
        chain = prompt | self.chat_model
        
        # Test different scenarios
        scenarios = [
            {"expertise": "data scientist", "years": "10", "topic": "machine learning"},
            {"expertise": "web developer", "years": "8", "topic": "REST APIs"},
            {"expertise": "cybersecurity specialist", "years": "12", "topic": "encryption"}
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{i}. {scenario['expertise'].title()} explaining {scenario['topic']}:")
            response = chain.invoke(scenario)
            print(f"{response.content[:200]}...")
        print()
    
    def conversation_chain_example(self):
        """Conversation with memory"""
        print("🧠 CONVERSATION WITH MEMORY")
        print("-" * 30)
        
        # Create memory
        memory = ConversationBufferMemory()
        
        # Create conversation chain
        conversation = ConversationChain(
            llm=self.chat_model,
            memory=memory,
            verbose=False
        )
        
        # Simulate a conversation
        conversations = [
            "Hi! My name is Alex and I'm learning Python.",
            "Can you help me understand functions?",
            "What was my name again?",
            "Can you give me a simple function example?"
        ]
        
        for i, user_input in enumerate(conversations, 1):
            print(f"\n👤 User: {user_input}")
            response = conversation.predict(input=user_input)
            print(f"🤖 Assistant: {response[:150]}...")
        
        print("\n✅ Conversation complete")
        print()
    
    def rag_example(self):
        """RAG (Retrieval Augmented Generation) example"""
        print("🔍 RAG EXAMPLE")
        print("-" * 30)
        
        # Create sample documents
        sample_docs = [
            "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991.",
            "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data without being explicitly programmed.",
            "Docker is a platform that uses containerization to package applications and their dependencies into lightweight, portable containers.",
            "Kubernetes is an open-source container orchestration platform that automates deployment, scaling, and management of containerized applications.",
            "REST APIs use HTTP methods like GET, POST, PUT, and DELETE to perform operations on resources identified by URLs."
        ]
        
        # Convert to Document objects
        documents = [Document(page_content=doc) for doc in sample_docs]
        
        # Split documents (not really needed for this example, but good practice)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        splits = text_splitter.split_documents(documents)
        
        # Create embeddings
        print("Creating embeddings...")
        embeddings = VertexAIEmbeddings(
            model_name="textembedding-gecko@003",
            project=PROJECT_ID,
            location=LOCATION
        )
        
        # Create vector store
        vectorstore = FAISS.from_documents(splits, embeddings)
        
        # Create RAG chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.chat_model,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(search_kwargs={"k": 2}),
            return_source_documents=True
        )
        
        # Test RAG
        questions = [
            "What is Python?",
            "How does machine learning work?",
            "What are the benefits of Docker?"
        ]
        
        for question in questions:
            print(f"\n❓ Question: {question}")
            result = qa_chain.invoke({"query": question})
            print(f"📖 Answer: {result['result'][:200]}...")
            print(f"📚 Sources: {len(result['source_documents'])} documents used")
        
        print("\n✅ RAG example complete")
        print()
    
    def function_calling_example(self):
        """Function calling with LangChain"""
        print("🔧 FUNCTION CALLING EXAMPLE")
        print("-" * 30)
        
        # Define tools/functions
        from langchain.tools import tool
        
        @tool
        def get_weather(city: str) -> str:
            """Get the current weather for a city"""
            # Mock weather data
            weather_data = {
                "san francisco": "Sunny, 22°C",
                "new york": "Cloudy, 18°C", 
                "london": "Rainy, 15°C",
                "tokyo": "Clear, 25°C"
            }
            return weather_data.get(city.lower(), "Weather data not available")
        
        @tool
        def calculate_tip(bill_amount: float, tip_percentage: float) -> str:
            """Calculate tip amount and total bill"""
            tip = bill_amount * (tip_percentage / 100)
            total = bill_amount + tip
            return f"Tip: ${tip:.2f}, Total: ${total:.2f}"
        
        # Create model with tools
        model_with_tools = self.chat_model.bind_tools([get_weather, calculate_tip])
        
        # Test function calling
        test_prompts = [
            "What's the weather like in San Francisco?",
            "Calculate a 20% tip on a $85 bill",
            "What's the weather in Tokyo and calculate 15% tip on $120?"
        ]
        
        for prompt in test_prompts:
            print(f"\n💭 Prompt: {prompt}")
            response = model_with_tools.invoke([HumanMessage(content=prompt)])
            
            if response.tool_calls:
                print("🔧 Tools called:")
                for tool_call in response.tool_calls:
                    print(f"  - {tool_call['name']}: {tool_call['args']}")
                    
                    # Execute the tool (in real app, you'd have proper tool execution)
                    if tool_call['name'] == 'get_weather':
                        result = get_weather.invoke(tool_call['args'])
                        print(f"  → {result}")
                    elif tool_call['name'] == 'calculate_tip':
                        result = calculate_tip.invoke(tool_call['args'])
                        print(f"  → {result}")
            else:
                print(f"📝 Response: {response.content}")
        
        print("\n✅ Function calling complete")
        print()
    
    def langchain_advanced_features(self):
        """Advanced LangChain features"""
        print("⚡ ADVANCED LANGCHAIN FEATURES")
        print("-" * 30)
        
        # 1. Custom output parser
        from langchain.schema import BaseOutputParser
        
        class JsonOutputParser(BaseOutputParser):
            def parse(self, text: str) -> dict:
                try:
                    return json.loads(text)
                except:
                    return {"error": "Failed to parse JSON", "raw_text": text}
        
        # 2. Chain with custom parser
        prompt = PromptTemplate(
            template="Generate a JSON object about {topic} with fields: name, description, benefits (array), difficulty_level (1-10)",
            input_variables=["topic"]
        )
        
        chain = prompt | self.chat_model | JsonOutputParser()
        
        topics = ["Python programming", "Machine learning", "Docker containers"]
        
        for topic in topics:
            print(f"\n📊 Generating structured data for: {topic}")
            try:
                result = chain.invoke({"topic": topic})
                if isinstance(result, dict) and "error" not in result:
                    print(f"✅ Parsed JSON successfully")
                    for key, value in result.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"⚠️ Parse failed: {result}")
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n✅ Advanced features demo complete")
        print()
    
    def run_all_examples(self):
        """Run all LangChain examples"""
        print("=" * 60)
        print("🦜 LANGCHAIN + VERTEX AI COMPLETE DEMO")
        print("=" * 60)
        
        examples = [
            ("Basic Chat", self.basic_chat_example),
            ("Streaming Chat", self.streaming_chat_example),
            ("Prompt Templates", self.prompt_template_example),
            ("Conversation Memory", self.conversation_chain_example),
            ("RAG (Retrieval)", self.rag_example),
            ("Function Calling", self.function_calling_example),
            ("Advanced Features", self.langchain_advanced_features),
        ]
        
        for name, func in examples:
            try:
                print(f"\n{'='*60}")
                print(f"Running: {name}")
                print(f"{'='*60}")
                func()
                print(f"✅ {name} completed")
            except Exception as e:
                print(f"❌ {name} failed: {e}")
            
            input("\n🔄 Press Enter to continue...")
        
        print("\n" + "="*60)
        print("🎉 ALL LANGCHAIN EXAMPLES COMPLETED!")
        print("="*60)

def quick_langchain_example():
    """Quick example for immediate use"""
    print("🚀 QUICK LANGCHAIN + VERTEX AI EXAMPLE")
    print("="*50)
    
    # Initialize
    chat = ChatVertexAI(
        model_name=MODEL_NAME,
        project=PROJECT_ID,
        location=LOCATION,
        temperature=0.7
    )
    
    # Simple chat
    response = chat.invoke([
        SystemMessage(content="You are a helpful coding assistant."),
        HumanMessage(content="Write a Python function to reverse a string")
    ])
    
    print(f"Response:\n{response.content}")
    print("\n✅ Quick example complete!")

def main():
    """Main function"""
    print("🦜 LangChain + Vertex AI Setup")
    print("="*40)
    
    choice = input("""
Choose an option:
1. Quick example (fast)
2. Full demo (comprehensive)
3. Exit

Enter choice (1-3): """).strip()
    
    if choice == "1":
        quick_langchain_example()
    elif choice == "2":
        demo = LangChainVertexAIDemo(PROJECT_ID, LOCATION, MODEL_NAME)
        demo.run_all_examples()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()