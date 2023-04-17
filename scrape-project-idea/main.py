# Returns a random project suggestion from https://rosettacode.org/wiki/Category:Programming_Tasks, this helps me to find new projects to work on.

import requests
import random
import bs4 as bs

BASE_URL = "https://rosettacode.org/wiki/Category:Programming_Tasks"


def get_project_suggestions():
    response = requests.get(BASE_URL)
    soup = bs.BeautifulSoup(response.text, 'html.parser')
    # Get all the links on the page within the div id="mw-pages"
    links = soup.find(id="mw-pages").find_all('a')
    # Get the text from the links
    links = [link.text for link in links]
    # Remove the "next page" link
    links.pop()

    # From Links get a random project title
    project_title = random.choice(links)
    # Replace spaces with underscores
    project_title = project_title.replace(" ", "_")
    # print URL
    print(f"https://rosettacode.org/wiki/{project_title}")


get_project_suggestions()
