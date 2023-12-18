import openai
import pandas as pd
import os
from dotenv import load_dotenv

# Set your OpenAI API key in the .env file (use example.env as a template)
openai.api_key = os.getenv("OPENAI_API_KEY")

# This example takes a CSV file with a list of trees and generates a markdown file for each tree
def generate_tree_info(tree_name):
    try:
        response = openai.Completion.create(
          model="text-davinci-003",  # You can change the model as per your requirement
          prompt=f"Write a detailed description about the tree: {tree_name} with sections for appearance, habitat, and uses and history. Please add section headings in the proper markdown format and add as many details as you can.",
          temperature=0.7,
          max_tokens=150
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"Error generating info for {tree_name}: {e}")
        return ""

def create_markdown_file(tree_name, content):
    filename = f"{tree_name.replace(' ', '_')}.md"
    with open(filename, 'w') as file:
        file.write(f"# {tree_name}\n\n{content}")

def process_trees(csv_file):
    df = pd.read_csv(csv_file)
    for tree in df['TreeName']:
        info = generate_tree_info(tree)
        create_markdown_file(tree, info)

if __name__ == "__main__":
    csv_file = 'trees.csv'  # Update this with your CSV file path
    process_trees(csv_file)
