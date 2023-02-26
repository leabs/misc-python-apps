# This app asks the user for a web address and returns all copy from the website into a text file. This includes all headings and paragraphs. Note that there is no error handling for invalid web addresses.

# Import the requests module
import requests
# Import beautiful soup 4
from bs4 import BeautifulSoup

# Define the main function


def main():
    # Print a blank line
    print()
    # Ask the user for a web address
    web_address = input(
        str("Enter a web address (example: https://stevenleabo.com): "))
    # Get the web address
    r = requests.get(web_address)
    # Parse the web address
    soup = BeautifulSoup(r.text, "html.parser")
    # Find all the headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    # Find all the paragraphs
    paragraphs = soup.find_all("p")
    # Open a text file
    with open("copy.txt", "w") as f:
        # Write the headings to the text file
        f.write("Headings: " + "\n")
        for heading in headings:
            f.write(heading.text.strip() + "\n")

        # Print a blank line
        print()

        # Write the paragraphs to the text file
        f.write("Paragraph Contents: " + "\n")
        print()
        for paragraph in paragraphs:
            f.write(paragraph.text.strip() + "\n")

    # Print a blank line
    print()
    # Print a message
    print("All copy from the website has been saved to copy.txt")


# Call the main function
main()
