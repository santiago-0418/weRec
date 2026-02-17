import os
from fastapi import FastAPI, Request
from langchain.prompts import PromptTemplate
from langchain.output_parsers import JsonOutputParser
from langchain.chat_models import ChatOpenAI

app = FastAPI()

# Initialize the LLM
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# Prompt template
prompt_template = PromptTemplate(
    input_variables=["artists", "genres", "mood"],
    template="""
You are a music recommendation assistant.

User likes these artists: {artists}
Preferred genres: {genres}
Mood: {mood}

Return 5 song recommendations in JSON format like this:
[
  {{ "artist": "...", "song": "..." }}
]
"""
)

# Parser to ensure output is JSON
json_parser = JsonOutputParser()

@app.post("/recommend")
async def recommend(request: Request):
    data = await request.json()
    artists = data.get("artists", "")
    genres = data.get("genres", "")
    mood = data.get("mood", "")

    # Build prompt
    prompt = prompt_template.format(
        artists=artists,
        genres=genres,
        mood=mood
    )

    # Call LLM
    raw_output = llm.predict(prompt)

    # Parse JSON
    try:
        recommendations = json_parser.parse(raw_output)
    except Exception:
        # Fallback if parsing fails
        recommendations = [
            {"artist": "The Weeknd", "song": "Blinding Lights"},
            {"artist": "Arctic Monkeys", "song": "Do I Wanna Know?"},
            {"artist": "Frank Ocean", "song": "Nikes"}
        ]

    return recommendations
