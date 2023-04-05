# This app generates a README.md template for projects for consistency in my code repos

# Import modules
import os
import sys
import datetime

# Get the project name from the command line
project_name = input("Enter the project name: ")

# Get the current date
project_created = datetime.datetime.now().strftime("%B %d, %Y")

# Create Array of README.md sections
readme_sections = [
    f"# {project_name}",
    # Table of contents
    "## Table of Contents",
    "## Objective",
    "## How It Works",
    "## How To Use",
    "## How To Contribute",
    "## Acknowledgements"
]

# Generate table of contents
table_of_contents = []
# Generate the table of contents for all sections within readme_sections EXCEPT for readme_sections[0] (the title) and readme_sections[1] (the table of contents)
for section in readme_sections[2:]:
    # Get the section title
    section_title = section.split("## ")[1]
    # Add the section title to the table of contents
    table_of_contents.append(
        f"- [{section_title}](#{section_title.lower().replace(' ', '-')})")


# Create the README.md file showing the section[0] then the table of contents then the rest of the sections
with open("README.md", "w") as readme:
    readme.write(f"{readme_sections[0]}")
    readme.write("\n\n")
    readme.write(f"{readme_sections[1]}")
    readme.write("\n\n")
    # Add the table of contents
    for section in table_of_contents:
        readme.write(f"{section}")

    readme.write("\n\n")
    for section in readme_sections[2:]:
        readme.write(f"{section}")
        # If the section is the last section, only add one line break
        if section == readme_sections[-1]:
            readme.write("\n")
        else:
            readme.write("\n\n")
