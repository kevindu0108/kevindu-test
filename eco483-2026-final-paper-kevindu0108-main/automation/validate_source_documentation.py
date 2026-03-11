#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pyyaml==6.0.2",
# ]
# ///
import argparse
from datetime import datetime
import fnmatch
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
import yaml

SOURCE_FILENAME = 'source.yaml'
DEPRECATED_FILES = ['sources.yaml', 'source.yml', 'sources.yml', 'source.txt', 'sources.txt']
IGNORED_FILES = ['.DS_Store', '.gitignore', 'filelisting.txt', 'README.md'] + DEPRECATED_FILES


def parse_args() -> argparse.Namespace:
    """ Parse command line arguments
    """
    parser = argparse.ArgumentParser(description='Recursively scan a folder to validate that all files are documented in source.yaml files')
    parser.add_argument('-d', '--directory', required=True, help='target directory to recursively validate')
    args = parser.parse_args()
    return args


def get_root_dir() -> str | None:
    """ Parses command line and gets the root directory to scan for source.yaml files
    """

    # Parse command line arguments
    args = parse_args()

    # Verify that the directory exists
    if not os.path.isdir(args.directory):
        raise ValueError(
            f"directory argument provided is not a directory, directory argument provided was: {args.directory}"
        )

    if not os.path.exists(args.directory):
        raise ValueError(
            f"directory argument points to a directory that does not exist, directory argument provided was: {args.directory}"
        )

    return args.directory


def find_source_yaml(root_dir: str) -> Tuple[List, List]:
    """ Recursively find source.yaml files (and similarly named files)
    """

    source_yaml_paths = []
    deprecated_file_paths = []

    for (dir_path, dirs_found, files_found) in os.walk(root_dir):

        if SOURCE_FILENAME in files_found:
            source_yaml_paths.append(os.path.join(dir_path, SOURCE_FILENAME))

        deprecated_files = set(files_found).intersection(DEPRECATED_FILES)
        if deprecated_files:
            deprecated_file_paths.extend([dir_path + '/' + f for f in deprecated_files])

    return sorted(source_yaml_paths), sorted(deprecated_file_paths)


def is_iso_date(dateval: datetime):
    """ Check if date is ISO format: YYYY-MM-DD
    """

    try:
        datetime.strptime(str(dateval), '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_source_yaml(root_dir: str):
    """ Validate the source documentation yaml files
    """

    # recursively find source.yaml files (and similarly named files)
    source_yaml_paths, deprecated_file_paths = find_source_yaml(root_dir)

    errors = {}

    # validate source.yaml files
    for file in source_yaml_paths:
        errors[file] = []
        with open(file, 'r') as f:
            try:
                source_yaml = yaml.safe_load(f)
            except yaml.YAMLError:
                errors[file].append('invalid YAML syntax')
                continue

        if source_yaml:
            try:
                documented_paths = source_yaml.keys()
            except AttributeError:
                errors[file].append('unexpected YAML syntax for documented paths')
                continue

            for documented_path in documented_paths:
                try:
                    keys = source_yaml.get(documented_path).keys()
                except AttributeError:
                    errors[file].append(f'unexpected YAML syntax for documentation of {documented_path}')
                    continue

                if 'source' not in keys:
                    errors[file].append(f'missing "source:" for {documented_path}')
                elif type(source_yaml.get(documented_path).get('source')) is not str:
                    errors[file].append(f'source is not string for {documented_path}')

                if 'description' not in keys:
                    errors[file].append(f'missing "description:" for {documented_path}')
                elif type(source_yaml.get(documented_path).get('description')) is not str:
                    errors[file].append(f'description is not string for {documented_path}')

                if 'obtained' not in keys:
                    errors[file].append(f'missing "obtained:" for {documented_path}')
                else:
                    obtained = source_yaml.get(documented_path).get('obtained')
                    if not (type(obtained) is str and obtained.lower() == 'na') and not is_iso_date(obtained):
                        errors[file].append(f'obtained is not YYYY-MM-DD or "NA" for {documented_path}')

        if not errors[file]:
            del errors[file]

    return errors, deprecated_file_paths


class SourceDocumentedPath:
    """ Recursively crawl through the contents of a directory,
        verifying that all files are documented in source.yaml

        Adapted from the code in: https://stackoverflow.com/a/49912639
    """
    display_filename_prefix_middle = '├──'
    display_filename_prefix_last = '└──'
    display_parent_prefix_middle = '    '
    display_parent_prefix_last = '│   '

    def __init__(self, path, parent=None, doc_pattern=[]):
        self.path = Path(str(path))
        self.parent = parent
        self.children = {'documented': [], 'undocumented': []}
        self.contains_undocumented_files = False
        self.find_and_label_children(self.path, self.parent, doc_pattern)

    def find_and_label_children(self, path: Path, parent: Optional["SourceDocumentedPath"], doc_pattern: List =[]) -> None:
        """ traverse path's tree and label children as documented or undocumented
            files
        """

        if self.path.is_dir():
            # Load any patterns documented in 'path/source.yaml'
            source_doc = self.path.joinpath(SOURCE_FILENAME)
            if source_doc.is_file():
                newly_documented = self.source_yaml_documented_paths(path, source_doc)
                doc_pattern.extend(newly_documented)
                # print('Documented: {}'.format(doc_pattern))

            # List contents of directory, excluding source.yaml and ignored files
            children = sorted(list(path for path in self.path.iterdir()
                                   if path.name not in IGNORED_FILES + [SOURCE_FILENAME]),
                              key=lambda s: str(s).lower())

            # Add directories and undocumented files to list of children
            for path in children:
                child = SourceDocumentedPath(path=path, parent=self, doc_pattern=doc_pattern.copy())
                if child.contains_undocumented_files:
                    self.children.get('undocumented').append(child)
                else:
                    self.children.get('documented').append(child)

        else:
            file_documented = False
            for pattern in doc_pattern:
                if fnmatch.fnmatch(str(path), pattern):
                    file_documented = True
                elif path.name.endswith('.dvc') and fnmatch.fnmatch(str(path)[:-4], pattern):
                    file_documented = True
            if not file_documented:
                self.contains_undocumented_files = True
                while parent is not None:
                    parent.contains_undocumented_files = True
                    parent = parent.parent

    @classmethod
    def source_yaml_documented_paths(cls, root: Path, doc: Path):
        with open(doc, 'r') as file:
            try:
                source_yaml = yaml.safe_load(file)
            except yaml.YAMLError:
                return []

        if source_yaml:
            try:
                documented_paths = source_yaml.keys()
            except AttributeError:
                return []
            
            return [str(root) + '/' + path for path in documented_paths]

        return []

    @property
    def displayname(self):
        if self.path.is_dir():
            return self.path.name + '/'
        return self.path.name

    @property
    def is_last_undocumented_child(self):
        if self == self.parent.children.get('undocumented')[-1]: # last in parent's list of undocumented children
            return True
        else:
            return False

    def print_tree_undocumented(self):
        if self.parent is None:
            print(str(self.path) + '/')
        else:
            _filename_prefix = (self.display_filename_prefix_last
                                if self.is_last_undocumented_child
                                else self.display_filename_prefix_middle)

            if self.path.is_dir():
                parts = ['{!s} {!s}'.format(_filename_prefix,
                                            self.displayname)]
            else:
                parts = ['{!s} \033[91m{!s}\033[00m'.format(_filename_prefix,
                                            self.displayname)]

            parent = self.parent
            while parent and parent.parent is not None:
                parts.append(self.display_parent_prefix_middle
                            if parent.is_last_undocumented_child
                            else self.display_parent_prefix_last)
                parent = parent.parent

            print(''.join(reversed(parts)))

        for child in self.children.get('undocumented'):
            child.print_tree_undocumented()

def print_validation_results(root_dir: str, errors: Dict, deprecated_filenames: List, parsed_dir: SourceDocumentedPath):
    """ Print all results of the validation in a user-friendly format
    """

    if errors or parsed_dir.contains_undocumented_files:
        print('===========================\n'
              '          SUMMARY          \n'
              '===========================\n')
        if errors:
            print('\033[1mThe following source.yaml files are malformed:\033[00m')
            count = 1
            for file in sorted(errors.keys()):
                is_last = count == len(errors)
                if is_last:
                    print(f'└── {file.removeprefix(root_dir + "/")}')
                else:
                    print(f'├── {file.removeprefix(root_dir + "/")}')
                count += 1
        else:
            print('\033[92mAll source.yaml files are valid.\033[00m')
        print('')

        if parsed_dir.contains_undocumented_files:
            print('\033[1mThe following top-level subdirectories contain undocumented files:\033[00m')
            count = 1
            topdirs = sorted(path.displayname for path in parsed_dir.children.get('undocumented') if path.path.is_dir())
            for dir in topdirs:
                is_last = count == len(topdirs)
                if is_last:
                    print(f'└── {dir}')
                else:
                    print(f'├── {dir}')
                count += 1
        else:
            print(f'\033[92mAll files are documented in {SOURCE_FILENAME} files.\033[00m')
        print('')

        if errors:
            print('\n'
                  '===========================\n'
                  '   INVALID DOCUMENTATION   \n'
                  '===========================\n')
            for file in errors.keys():
                print(f'\033[91m{file.removeprefix(root_dir + "/")}\033[00m')
                for error in errors[file]:
                    print(f'  ─ {error}')
            print('')

        if parsed_dir.contains_undocumented_files:
            print('\n'
                  '===========================\n'
                  '    UNDOCUMENTED FILES     \n'
                  '===========================\n')
            parsed_dir.print_tree_undocumented()
            print('')

    else:
        print('\033[92mAll source.yaml files are valid.\033[00m')
        print('')
        print(f'\033[92mAll files are documented in {SOURCE_FILENAME} files.\033[00m')

    if deprecated_filenames:
        print('\n'
              '===========================\n'
              '   DEPRECATED FILENAMES    \n'
              '===========================\n')
        print('All data source documentation should be stored in files named \033[92msource.yaml\033[00m\n\n'
              '\033[1mThe following filenames are deprecated and the files should be removed or renamed:\033[00m')
        for filename in deprecated_filenames:
            print(f'└── {filename.removeprefix(root_dir + "/")}')
        print('')


def main(root_dir: str | None = None) -> int:
    """ Main loop, prints a list of problem directories and a description of what's wrong
    """

    # Get the root directory to scan
    if root_dir is None:
        root_dir = get_root_dir()

    # Validate source.yaml files are in spec
    errors, deprecated_filenames = validate_source_yaml(root_dir)

    # Search for undocumented files
    parsed_dir = SourceDocumentedPath(path=root_dir)

    # Print errors and warnings
    print_validation_results(root_dir, errors, deprecated_filenames, parsed_dir)

    if errors or parsed_dir.contains_undocumented_files: # any out-of-spec source.yaml files or undocumented files
        return 1
    else:
        return 0


if __name__ == '__main__':
    sys.exit(main())
