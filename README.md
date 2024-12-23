# Misc Python Apps

Here are some random applications in Python that run in a terminal and are [helpful for various reasons](#how-these-apps-are-useful-to-me). These are just for fun and to learn Python. These are in no way meant to be used for anything serious, and many have _zero error checking or validation_. Maybe that is something I can come back and add in the future.

## Requirements

- To run the apps, you'll need to have Python installed on your system. You can download it from [here](https://www.python.org/downloads/).
- Since this is a terminal application, you'll need to be able to run Python scripts from the terminal. If you're on Windows, you may need to add Python to your PATH. You can do this by following the instructions [here](https://geek-university.com/python/add-python-to-the-windows-path/).
- Some apps require additional packages (details below), so you may need to install those as well. Do so by installing [pip](https://pypi.org/project/pip/), a Python package manager.

## Running the apps

- Clone this repository:

```bash
git clone https://github.com/leabs/misc-python-apps
```

- Open a terminal and change directories into the repository root.

```bash
cd misc-python-apps
```

- This project uses **prompt_toolkit** for the user interface. Install it by using the requirements.txt file by running:

```bash
pip3 install -r requirements.txt
```

- From there you can run to see a list of apps to choose from:

```bash
python main.py
```

_note_: some apps require additional packages. If you see a requirements.txt file in the app's directory, you'll need to install the packages by going into that directory and running:

```bash
pip3 install -r requirements.txt
```

in the app's directory. Also there might be a `.env` file that you'll need to copy the contents of the `example.env` file to like the `batch-ask-openai` app.

## App Explanations

- **Batch Ask OpenAI** - Asks the Open AI API a list of questions (from within a .csv) and generates a markdown file for each questions. Make sure to set your `OPENAI_API_KEY` by copying the `example.env` file to `.env` and adding your key.
- **BTC Power Law Investment**(\*) - This app calculates the power law of Bitcoin and adjusts the recommended investment amount based on the current power level. It takes into account today's Bitcoin price compares to its past trends by checking how 'high up' the current price is between its lowest and highest expected values when plotted on a special kind of graph that stretches time and price into logarithms.
- **CSV to JSON** - Converts a CSV file to a JSON file. This uses a csv file called `data.csv` within the `csv-to-json` directory. Want to convert your own? Replace the `data.csv` file with your own and run the app with `python3 main.py` in the directory. The output file will be called `data.json` and will be located within the `csv-to-json` directory.
- **Generate README** - This is a simple README template generator that takes in the project name and outputs README sections with links to the sections in markdown.
- **Get Rain Estimate** - Using the openweathermap API and a user specified zip code, this app will tell you if it's going to rain in the next 5 days. This does require an openweathermap API key which you can get [here](https://openweathermap.org/api).
- **Markdown to HTML**(\*) - Generates HTML from a markdown file (index.md) including HTML boilerplate elements.
- **Password Generator** - Generates a random password with letters, numbers, symbols, and punctuation using user input for the password length. (Between 8 and 64 characters)
- **Retirement Calculator** - Calculates how much you can withdraw on your retirement accounts using earn compounded interest. This also lets you calculate a yearly withdraw amount using a known pension. In addition, NYSLRS Tier 6 retirement benefits can be calculated using this app (because that's what my wife has, lol).
- **Scrape All Copy**(\*) - Scrapes all the text from a website and saves it to a text file. Has requirements.txt file for installing the required modules.
- **Scrape Project Idea**(\*) - Scrapes <https://rosettacode.org/wiki/Category:Programming_Tasks> for project ideas. Has requirements.txt file for installing the required modules.
- **Scrape Table**(\*) - Scrapes table data (tr, td, etc) from a user specified website and saves it to a CSV file in the root of the directory. Has requirements.txt file for installing the required modules.
- **Scrape Temperature**(\*) - Gets the current temperature for a given zip code. This uses BS4 to get the current temperature from [https://www.yahoo.com/news/weather](https://www.yahoo.com/news/weather).
- **Stock Comparison**(\*) - Compares common tech stocks and outputs a table of stock data including total return, annualized volatility, and projected 10-year trend to the user. This uses the yfinance package to get stock data.
- **Youtube Views and Subs**(\*) - Gets the number of views and subscribers for a given youtube channel.

## How these apps are useful to me

- **Batch Ask OpenAI** - This has the ability to generate markdown files for any number of topics which I can then host for free as a static site.
- **BTC Power Law Investment** - This quickly suggests an investment amount based on the current power level of Bitcoin. This is useful for me to quickly see how much I should invest based on a strategy I'm following and takes the emotion out of investing. (Lower power levels suggest a higher investment amount, and higher power levels suggest a lower investment amount.)
- **CSV to JSON Converter** - I'm working on a static site that has individual pages for trees. Converting the data from a CSV file to JSON makes it easier to build the pages with [Jekyll pagemaster](https://github.com/mnyrop/pagemaster/#readme). I have found that sometimes the formatting used by my client in csv doesn't always mesh well with pagemaster, but JSON does!
- **Generate README** - I'm using this to generate README markdown files for projects to make them have a consistent look and feel. It also builds out a table of contents with links, saving me the time of having to do that manually. This may evolve in the future, but for now it works and saves me time.
- **Get Rain Estimate** - I'm using this along with the macOS app called Alfred to quickly look up if I can expect rain in the next coming days. This informs me if I need to water my vegetable garden during the growing season.
- **Markdown to HTML** - A quick way to format markdown into HTML without needing to pass the markdown through a site generator.
- **Password Generator** - Sometimes you want to generate a password quickly and or want to know the password is truly random using python's random module.
- **Retirement Calculator** - This is a tool that informs me of an estimate of how much I can withdraw from my retirement accounts each year. This is useful for estimating how much I can spend each year in retirement.
- **Scrape Apps** - A way to both understand python / web scraping and to easily and quickly get data from sites for data hoarding or to use in other projects!
- **Stock Comparison** - I'm using this to compare the performance of tech stocks to see which ones are performing the best. This shows me the data I am looking for in a simple table format. I do not day trade, so I am looking at long term trends (10 years).
- **Youtube Views and Subs** - I'm using this to get the number of views and subscribers for a given youtube channel. I'm using this to track my own channel's growth.

## Contributing

I'm a Python noob, so if I'm doing something wrong or if you see something that can be done differently, please let me know by opening an issue or submitting a pull request.
