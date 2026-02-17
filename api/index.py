from http.server import BaseHTTPRequestHandler
import os
import json
import base64
import requests
from langchain_groq import ChatGroq

PROMPT_TEMPLATE = """
You are a music recommendation assistant.

User likes: {liked}
User dislikes: {disliked}

Preferred genres: {genres}
Mood: {mood}

Return 8 songs by different artists NOT previously liked or disliked.
Return ONLY valid JSON in the format:
[
  {{ "artist": "Artist name", "song": "Song title" }},
  ...
]
"""

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            artists = data.get("artists", "")
            genres = data.get("genres", "")
            mood = data.get("mood", "")
            liked = data.get("liked", [])
            disliked = data.get("disliked", [])

            # Initialize LLM
            llm = ChatGroq(
                model="openai/gpt-oss-20b",
                api_key=os.environ["GROQ_API_KEY"],
                temperature=0.7
            )

            prompt = PROMPT_TEMPLATE.format(
                liked=json.dumps(liked),
                disliked=json.dumps(disliked),
                genres=genres,
                mood=mood
            )

            raw_output = llm.invoke(prompt)
            text = raw_output.content.strip()

            # Remove ```json markdown if present
            if text.startswith("```"):
                text = text.strip("`").replace("json", "").strip()

            # Extract JSON array
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]

            try:
                recommendations = json.loads(text)
            except Exception:
                # fallback dummy recommendations
                recommendations = [
                    {"artist": "The Weeknd", "song": "Blinding Lights"},
                    {"artist": "Arctic Monkeys", "song": "Do I Wanna Know?"},
                    {"artist": "Frank Ocean", "song": "Nikes"},
                    {"artist": "Dua Lipa", "song": "Levitating"},
                    {"artist": "Tame Impala", "song": "The Less I Know the Better"},
                    {"artist": "Kendrick Lamar", "song": "HUMBLE."},
                    {"artist": "Billie Eilish", "song": "Happier Than Ever"},
                    {"artist": "Doja Cat", "song": "Say So"}
                ]

            token = self.get_spotify_token()
            for rec in recommendations:
                spotify_data = self.search_spotify(rec["song"], rec["artist"], token)
                if spotify_data:
                    rec["spotify_url"] = spotify_data["spotify_url"]
                    rec["album_image_url"] = spotify_data["album_image_url"]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(recommendations).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "API is running"}).encode("utf-8"))

    def get_spotify_token(self):
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            return None

        auth_str = f"{client_id}:{client_secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()

        url = "https://accounts.spotify.com/api/token"
        headers = {"Authorization": f"Basic {b64_auth_str}"}
        data = {"grant_type": "client_credentials"}

        resp = requests.post(url, headers=headers, data=data)
        if resp.status_code == 200:
            return resp.json()["access_token"]
        return None

    def search_spotify(self, song, artist, token):
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        query = f"{song} {artist}"
        url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=5"

        resp = requests.get(url, headers=headers)
        items = resp.json().get("tracks", {}).get("items", [])

        # Try to match exact artist first
        for t in items:
            if artist.lower() in [a["name"].lower() for a in t["artists"]]:
                return {
                    "spotify_url": t["external_urls"]["spotify"],
                    "album_image_url": t["album"]["images"][1]["url"]
                }

        # fallback to first track
        if items:
            return {
                "spotify_url": items[0]["external_urls"]["spotify"],
                "album_image_url": items[0]["album"]["images"][1]["url"]
            }
        return None
