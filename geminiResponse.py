import base64
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json

load_dotenv()

def geminiResponseGenerator(fileName):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-1.5-flash"

    # Read the EFL text from file
    with open(fileName, 'r') as file:
        efl_text = file.read()

    # Encode the EFL text as base64
    efl_base64 = base64.b64encode(efl_text.encode('utf-8')).decode('utf-8')

    prompt = """You are an electricity provider analyzing an Electricity Facts Label (EFL). Extract the following data and format it as JSON:
    Company Name: The electricity provider's name, listed right after "Electricity Facts Label (EFL)".
    Base Price: The monthly base charge in dollars (remove the dollar sign).
    Tiers:
    If the energy charge is flat (e.g., "All kWh"), set min to 0 and max to null, then provide the rate.
    If tiered, list each kWh range with min/max values and their corresponding rates.
    For open-ended ranges (e.g., "> 1000 kWh"), set max to null.
    Description: Combine all key terms, discounts, and disclosures into a single string under description.
    Output format:
    {
      "company_name": "",
      "base_price": "",
      "tiers": [
        {
          "min": 0,
          "max": null,
          "rate": ""
        }
      ],
      "description": ""
    }"""

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    mime_type="text/plain",
                    data=base64.b64decode(efl_base64),
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(response_mime_type="text/plain")

    raw_response = ""
    for chunk in client.models.generate_content_stream(
        model=model, contents=contents, config=generate_content_config
    ):
        raw_response += chunk.text

    # Remove triple backticks and 'json' label if present
    cleaned_response = raw_response.strip()
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response.replace("```json", "", 1)
    if cleaned_response.endswith("```"):
        cleaned_response = cleaned_response.rsplit("```", 1)[0]

    cleaned_response = cleaned_response.strip()

    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse JSON",
            "raw_response": raw_response
        }
