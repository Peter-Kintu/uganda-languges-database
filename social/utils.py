import os
from google import genai
from django.conf import settings

# Configure Gemini API Client (2025 Standard)
client = genai.Client(api_key=settings.GEMINI_API_KEY)

def translate_text(text, target_language='en', source_language='auto'):
    """
    Translate text using Google Gemini API.
    Supports multiple languages, especially African languages.
    """
    try:
        prompt = f"Translate the following text from {source_language} to {target_language}. If source is 'auto', detect the language. Text: {text}"
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original if translation fails

def detect_language(text):
    """
    Detect the language of the text using Gemini.
    """
    try:
        prompt = f"Detect the language of this text and return only the ISO language code: {text}"
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip().lower()
    except Exception as e:
        print(f"Language detection error: {e}")
        return 'en'

def summarize_text(text, max_length=100):
    """
    Summarize text for previews using Gemini.
    """
    try:
        prompt = f"Summarize this text in {max_length} characters or less: {text}"
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return text[:max_length]

def generate_tags(text):
    """
    Generate relevant tags for content using AI.
    """
    try:
        prompt = f"Generate 5-10 relevant hashtags for this content, separated by commas: {text}"
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        tags = response.text.strip().split(',')
        return [tag.strip('#').strip() for tag in tags if tag.strip()]
    except Exception as e:
        return []