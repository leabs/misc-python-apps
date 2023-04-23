# This scrapes Table data from an HTML table and saves it to a CSV file
import bs4 as bs
import urllib.request
import csv # for writing to csv

# Ask user what website the table is on
website = input('What website do you want to scrape? ')
# Collect table data from user selected website in a table with the class ws-table-all
soup = bs.BeautifulSoup(urllib.request.urlopen(
    website).read(), 'html.parser')

# Ask user what HTML class the table has
table_class = input('What is the HTML class of the table? (inspect to find class): ')

# target table class table
table = soup.find('table', {'class': table_class})

# Convert the <td> and <tr> into a list of lists for csv ensuring a comma at the end of each row <tr>
table_data = [[cell.text for cell in row.find_all(['td', 'th'])]
              for row in table.find_all('tr')]
# Remove white space
table_data = [[cell.strip() for cell in row] for row in table_data]

# Write the table data to a CSV file
with open('table.csv', 'w') as csv_file:
    csv_writer = csv.writer(csv_file)
    csv_writer.writerows(table_data)

print('Done!')
