import os

import certifi
import truststore
from dotenv import load_dotenv
from openai import OpenAI

truststore.inject_into_ssl()

# 1. Force Python to use the correct SSL certificates
os.environ["SSL_CERT_FILE"] = certifi.where()

# 2. Load your .env file
load_dotenv()

# 3. Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    print("Connecting to OpenAI...")
    response = client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "Say hello!"}]
    )
    print(f"SUCCESS: {response.choices[0].message.content}")
except Exception as e:
    print(f"STILL FAILING. Error type: {type(e).__name__}")
    print(f"Details: {e}")


def main():
    print("Hello from compintel!")


if __name__ == "__main__":
    main()
