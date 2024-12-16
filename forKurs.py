import requests
import pyodbc
from bs4 import BeautifulSoup  # For cleaning HTML

# SQL Server connection settings
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=192.168.152.131;'
    'DATABASE=forKursova;'
    'UID=SA;'
    'PWD=Vlad09876Mouse'
)
cursor = conn.cursor()

# API URL for a specific game
url = "https://api.rawg.io/api/games/grand-theft-auto-v?key=f506b0be39bc4f63ac0c35a556518867"


def fetch_game(url):
    print("Fetching game data...")
    response = requests.get(url)
    if response.status_code == 404:
        print("Game not found.")
        return None
    elif response.status_code != 200:
        print(f"Failed to fetch data from API. Status code: {response.status_code}, Response: {response.text}")
        return None

    return response.json()


# Get game data from the API
game_data = fetch_game(url)
if game_data:
    print(f"Game fetched: {game_data['name']}")

    # Clean and print description
    raw_description = game_data.get("description", "")
    description = BeautifulSoup(raw_description, "html.parser").get_text() if raw_description else ""
    print(f"Description: {description}")

    # Prepare data for insertion
    game_id = game_data.get("id")
    title = game_data.get("name")
    release_year = game_data.get("released", "")[:4] if game_data.get("released") else None
    rating = game_data.get("rating", 0.0)
    genre = ', '.join(genre['name'] for genre in game_data.get("genres", []))  # Convert genres to a string
    tags = ', '.join(tag['name'] for tag in game_data.get("tags", []))
    site = game_data.get("website")

    # Check if the game already exists in the database
    cursor.execute("SELECT COUNT(*) FROM Games WHERE GameID = ?", game_id)
    if cursor.fetchone()[0] == 0:
        # Insert into Games table
        cursor.execute("""
            INSERT INTO Games (GameID, Title, Description, Genre, Tags, ReleaseYear, Rating, site)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, game_id, title, description, genre, tags, release_year, rating, site)

# Commit changes and close the connection
conn.commit()
conn.close()
print("Game data inserted successfully.")
