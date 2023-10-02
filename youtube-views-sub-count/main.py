# This program returns the number of views and subscribers for a given channel
import os
import json
import requests
import datetime
import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Load environment variables
load_dotenv()

# Get API key from environment variable
API_KEY = os.getenv("API_KEY")

# Get channel ID from environment variable
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Get the current date
current_date = datetime.datetime.now()

# Create a dictionary to store the parameters for the YouTube API request
parameters = {
    "part": "statistics",
    "id": CHANNEL_ID,
    "key": API_KEY,
}

# Make a request to the YouTube API
response = requests.get(
    "https://youtube.googleapis.com/youtube/v3/channels", params=parameters)

# Convert the response to JSON
response = response.json()

# Get the number of views from the response
views = response["items"][0]["statistics"]["viewCount"]
subs = response["items"][0]["statistics"]["subscriberCount"]

# Print the number of views
print("Total channel views are currently: " + views +
      " and you have " + subs + " subscribers.")