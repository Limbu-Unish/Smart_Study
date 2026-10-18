import os
from dotenv import load_dotenv
from google import genai

# Loads the .env file
load_dotenv()

# The Google client automatically looks for GEMINI_API_KEY in your environment
client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Hello! Tell me a quick fun fact.",
)

print(response.text)