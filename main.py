import subprocess
from pathlib import Path
from prompt_toolkit.shortcuts import radiolist_dialog


def get_child_directories():
    root_path = Path.cwd()  # Set root to current directory
    directories = [
        d for d in root_path.glob('**/') 
        if d.is_dir() and d != root_path and not any(part.startswith('.') for part in d.parts)  # Exclude root and hidden directories
    ]
    print(f"Directories found: {directories}")  # Debugging output
    return directories


def run_main_py(directory):
    main_py = directory / 'main.py'  # Using Path object directly
    print(f"Checking for main.py in {directory}")  # Debugging output
    if main_py.exists():
        print(f"Running {main_py}")  # Debugging output
        subprocess.run(['python', str(main_py)])
    else:
        print(f"No main.py found in {directory}")


def select_directory_and_run():
    directories = get_child_directories()
    
    if not directories:
        print("No directories found!")
        return
    
    # Prepare list of choices with just the directory names
    choices = [(i, d.name) for i, d in enumerate(directories)]  # Use d.name for display
    print(f"Choices: {choices}")  # Debugging output

    selected = radiolist_dialog(
        title="Select a directory",
        text="Select a directory to run its main.py:",
        values=choices
    ).run()

    print(f"Selected: {selected}")  # Debugging output

    if selected is not None:
        selected_directory = directories[selected]
        print(f"Running main.py in: {selected_directory}")  # Debugging output
        run_main_py(selected_directory)
    else:
        print("No directory selected.")


if __name__ == "__main__":
    print("Starting the program...")  # Debugging output
    select_directory_and_run()
