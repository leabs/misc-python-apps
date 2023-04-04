# Misc Python Apps

Here are some random applications in Python that run in a terminal and are [helpful for various reasons](#how-these-apps-are-useful-to-me). These are just for fun and to learn Python. These are in no way meant to be used for anything serious, and many have _zero error checking or validation_. Maybe that is something I can come back and add in the future.

## Requirements

- To run the apps, you'll need to have Python installed on your system. You can download it from [here](https://www.python.org/downloads/).
- Some apps require additional packages (details below), so you may need to install those as well. Do so by installing [pip](https://pypi.org/project/pip/), a Python package manager.

## Running the apps

- Download, clone, or fork this repository.
- Open the terminal and navigate to the directory where the repository is located.
- Change directories into your chosen app.
- Run the app using the command `python3 main.py` inside the chosen app directory.
- NOTE: Some apps _may_ require you to install additional Python packages. Use the requirements.txt file to install the packages by running `pip3 install -r requirements.txt` in the app directory. Apps with requirements.txt file are marked with an asterisk (\*) in the list below.

## App Explanations

- **CSV to JSON** - Converts a CSV file to a JSON file. This uses a csv file called `data.csv` within the `csv-to-json` directory. Want to convert your own? Replace the `data.csv` file with your own and run the app with `python3 main.py` in the directory. The output file will be called `data.json` and will be located within the `csv-to-json` directory.
- **Get Rain Estimate** - Using the openweathermap API and a user specified zip code, this app will tell you if it's going to rain in the next 5 days. This does require an openweathermap API key which you can get [here](https://openweathermap.org/api).
- **Password Generator** - Generates a random password with letters, numbers, symbols, and punctuation using user input for the password length. (Between 8 and 64 characters)
- **Retirement Calculator** - Calculates how much you can withdraw on your retirement accounts using earn compounded interest. This also lets you calculate a yearly withdraw amount using a known pension. In addition, NYSLRS Tier 6 retirement benefits can be calculated using this app (because that's what my wife has, lol).
- **Scrape All Copy**(\*) - Scrapes all the text from a website and saves it to a text file. Has requirements.txt file for installing the required modules.
- **Scrape Table**(\*) - Scrapes table data (tr, td, etc) from a user specified website and saves it to a CSV file in the root of the directory. Has requirements.txt file for installing the required modules.
- **Scrape Temperature**(\*) - Gets the current temperature for a given zip code. This uses BS4 to get the current temperature from [https://www.yahoo.com/news/weather](https://www.yahoo.com/news/weather).

## Contributing

I'm a Python noob, so if I'm doing something wrong or if you see something that can be done differently, please let me know by opening an issue or submitting a pull request.

## How these apps are useful to me

- **CSV to JSON** - I'm working on a static site that has individual pages for trees. Converting the data from a CSV file to JSON makes it easier to build the pages with [Jekyll pagemaster](https://github.com/mnyrop/pagemaster/#readme)
- **Get Rain Estimate** - I'm using this along with the macOS app called Alfred to quickly look up if I can expect rain in the next coming days. This informs me if I need to water my vegetable garden during the growing season.
- **Password Generator** - Sometimes you want to generate a password quickly and or want to know the password is truly random using python's random module.
- **Retirement Calculator** - This is a tool that informs me of an estimate of how much I can withdraw from my retirement accounts each year. This is useful for estimating how much I can spend each year in retirement.
- **Scrape Apps** - A way to both understand python / web scraping and to easily and quickly get data from sites for data hoarding or to use in other projects!
