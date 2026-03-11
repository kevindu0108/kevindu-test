#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "ipython==8.30.0",
#     "nbconvert==7.16.4",
# ]
# ///
import json
import nbformat
from nbconvert.exporters import ScriptExporter
import os
from pathlib import Path
import re
import sys

def obtain_code_file(filename: str) -> dict:

    valid_submission_files = [filename + ext for ext in ['.ipynb', '.py', '.r', '.do', '.Rmd']]
    valid_code_files = [filename + ext for ext in ['.py', '.r', '.do', '.Rmd']]

    # Check there is exactly one file matching the specified filename (not case sensitive)
    submitted_file_original = count_file_presence(
        valid_files = valid_submission_files,
        required = 1
    )[0]

    # Rename submitted file to lowercase
    submitted_file = submitted_file_original.lower()
    if submitted_file_original != submitted_file:
        os.rename(submitted_file_original, submitted_file)

    # If the submitted file is a Jupyter notebook, convert it to a script.
    if submitted_file == filename + '.ipynb':
        convert_notebook_to_script(submitted_file)

    # Check there is exactly one code file (not case sensitive)
    code_file = count_file_presence(
        valid_files = valid_code_files,
        required = 1
    )[0]

    # Check the file type of the code file
    submission = {
        'file': code_file,
        'original': submitted_file_original
    }

    if code_file.endswith('.py'):
        submission['lang'] = 'python'
        submission['python'] = True
        submission['r'] = False
        submission['stata'] = False
    elif code_file.endswith('.r') or code_file.endswith('.rmd'):
        submission['lang'] = 'r'
        submission['python'] = False
        submission['r'] = True
        submission['stata'] = False
    elif code_file.endswith('.do'):
        submission['lang'] = 'stata'
        submission['python'] = False
        submission['r'] = False
        submission['stata'] = True
    else:
        raise ValueError(f'ERROR: {code_file} must be .py, .r, .Rmd or .do')
    
    # Check if other languages are needed
    with open(code_file, 'r') as file:
        content = file.read()
        
        match = re.search(r'{"project_languages":\[.*?\]}', content)
        if match:
            languages_json_str = match.group(0)
            languages_json = json.loads(languages_json_str)
            project_languages = languages_json.get('project_languages', [])
            
            if "stata" in project_languages:
                submission['stata'] = True
            if "R" in project_languages or "r" in project_languages:
                submission['r'] = True
            if "python" in project_languages:
                submission['python'] = True

    return submission

def count_file_presence(valid_files: list[str], required: int = None) -> list[str]:
    ''' Check whether files in valid_files are present in cwd
        (not case sensitive)
    '''

    valid_files_lowercase = set(file.lower() for file in valid_files)
    found_files = set()
    found_files_lowercase = set()

    for file in os.listdir('.'):
        if os.path.isfile(file) and file.lower() in valid_files_lowercase:
            found_files.add(file)
            found_files_lowercase.add(file.lower())

    if required is not None:
        if len(found_files) != required:
            error_message = f"<h1>❌ Submission Error</h1> There must be exactly {required} of the following files, found {len(found_files)}: <ul>"
            for file in valid_files_lowercase:
                if file in found_files_lowercase:
                    error_message += f'<li>🔴 {file}</li>'
                else:
                    error_message += f'<li>{file}</li>'
            error_message += "</ul>"

            print(error_message)
            sys.exit(1)

    return list(found_files)

def convert_notebook_to_script(
    nb_path: Path | str,
    output_path: Path | str | None = None
) -> str:
    """
    Convert a Jupyter notebook to a script file using the same
    automatic extension detection as:
        jupyter nbconvert --to script YOUR_NOTEBOOK.ipynb

    Args:
        nb_path: Path to the Jupyter notebook file.
        output_path: Optional output path for the script.
                     If None, automatically derived from the notebook name
                     plus the detected extension.

    Returns:
        The filesystem path (as a string) where the script was written.
    """
    nb_path = Path(nb_path)
    
    # Create the ScriptExporter, which handles multi-language notebooks
    exporter = ScriptExporter()
    
    # This reads the notebook and exports it to a script + resource dict
    script, resources = exporter.from_filename(str(nb_path))

    # nbconvert sets resources['output_extension'] (e.g., .py, .R, etc.)
    detected_ext = resources.get('output_extension', '.txt')

    # If no output_path given, generate one from the notebook stem + extension
    if output_path is None:
        output_path = nb_path.with_suffix(detected_ext)
    else:
        output_path = Path(output_path)

    # Write out the resulting script
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script)

    return str(output_path)

def main() -> int:
    submission = obtain_code_file('submission')
    print(json.dumps(submission))
    return 0

if __name__ == '__main__':
    sys.exit(main())
