# This converts a simple CSV file to JSON using a test csv called data
import csv
import json


def csv_to_json(csvFilePath, jsonFilePath):
    # Create an empty list to hold the data
    jsonArray = []

    # Read data from the CSV
    with open(csvFilePath, encoding='utf-8') as csvf:
        # Load the CSV file data using csv library's dictionary reader
        csvReader = csv.DictReader(csvf)

        # For each row in the CSV file
        for row in csvReader:
            # Add the data to the list
            jsonArray.append(row)

    # Output the JSON to a file
    with open(jsonFilePath, 'w', encoding='utf-8') as jsonf:
        jsonString = json.dumps(jsonArray, indent=4)
        jsonf.write(jsonString)


# Setting the default file paths
csvFilePath = r'./data.csv'
jsonFilePath = r'./data.json'

# Call the function
csv_to_json(csvFilePath, jsonFilePath)
# Print all done
print("CSV to JSON conversion completed")
