#!/usr/bin/env python3
"""Test script to verify Gemini API integration."""

import os
import google.generativeai as genai

def test_gemini_api():
    """Test the Gemini API with the provided key."""
    
    # Configure API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable is not set.")
        return False
    genai.configure(api_key=api_key)

    print("Testing Gemini API connection...")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Initialize the model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Test with a simple prompt
        test_prompt = """
        Analyze this sample TikTok advertising data and provide a brief insight:
        - Campaign: Summer Sale 2024
        - Spend: $5,000
        - Revenue: $15,000
        - Orders: 300
        - ROI: 3.0x
        
        Provide a one-paragraph analysis of this campaign's performance.
        """
        
        print("\nSending test prompt to Gemini...")
        response = model.generate_content(test_prompt)
        
        print("\n✅ API Connection Successful!")
        print("\nGemini Response:")
        print("-" * 50)
        print(response.text)
        print("-" * 50)
        
        # List available models
        print("\n📊 Available Models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ API Test Failed!")
        print(f"Error: {str(e)}")
        
        if "API_KEY_INVALID" in str(e):
            print("\n⚠️  The API key appears to be invalid.")
            print("Please check that the key is correct and has the necessary permissions.")
        elif "RATE_LIMIT" in str(e):
            print("\n⚠️  Rate limit exceeded.")
            print("The API key is valid but you've hit the rate limit.")
        else:
            print(f"\n⚠️  Unexpected error: {type(e).__name__}")
        
        return False

if __name__ == "__main__":
    print("🤖 Gemini AI API Test\n")
    success = test_gemini_api()
    
    if success:
        print("\n✨ Gemini AI is ready to use in your dashboard!")
        print("The AI insights feature will work with your TikTok ads data.")
    else:
        print("\n⚠️  Please resolve the issues above before using AI insights.")