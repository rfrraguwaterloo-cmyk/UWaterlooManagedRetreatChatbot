"""Quick smoke test for OpenAI gpt-4o-mini API call."""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def test_basic_completion():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'API connection successful' and nothing else."},
        ],
        max_tokens=20,
    )

    reply = response.choices[0].message.content.strip()
    print(f"Response: {reply}")
    print(f"Model: {response.model}")
    print(f"Tokens used: {response.usage.total_tokens}")
    assert "successful" in reply.lower(), f"Unexpected response: {reply}"
    print("Test passed.")


if __name__ == "__main__":
    test_basic_completion()
