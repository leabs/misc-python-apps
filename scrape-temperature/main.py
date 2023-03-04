# Asks the user for a zip code and returns the current weather for that zip code. Note that there is no error handling for invalid zip codes.

# Import the requests module
import requests
# Import beautiful soup 4
from bs4 import BeautifulSoup

# Define the main function


def main():
    # Print a blank line
    print()
    # Ask the user for a zip code
    zip_code = input(str("Enter a zip code: "))
    # Get the web address
    r = requests.get(
        "https://www.yahoo.com/news/weather/?location-picker=" + zip_code)
    # Parse the web address
    soup = BeautifulSoup(r.text, "html.parser")
    # Find the current temp
    current_temp = soup.find("span", class_="fahrenheit")
    current_temp_c = soup.find("span", class_="celsius")
    # Print the current weather
    print("The current temp is " + current_temp.text.strip() + "°F or " + current_temp_c.text.strip() + "°C.")


# Call the main function
main()
