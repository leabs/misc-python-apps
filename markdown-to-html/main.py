import markdown
from pathlib import Path

# Read the contents of the Markdown file
markdown_file = Path("index.md")
markdown_content = markdown_file.read_text()

# Convert Markdown content to HTML
html_content = markdown.markdown(markdown_content)

# Add HTML boilerplate
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Markdown to HTML</title>
</head>
<body>
{html_content}
</body>
</html>
"""


# Save the HTML content to an HTML file
html_file = Path("index.html")
html_file.write_text(html_content)
