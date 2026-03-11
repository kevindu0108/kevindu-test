#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pyyaml==6.0.2",
# ]
# ///
import argparse
import json
import os
import sys
import textwrap
import yaml


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Validate submitted results")
    parser.add_argument(
        "--config", help="Specify YAML file containing results config", required=True
    )
    parser.add_argument(
        "--correct", help="JSON string containing correct results", required=True
    )
    parser.add_argument(
        "--output",
        help="Write validation results in HTML to specified file",
        required=True,
    )
    parser.add_argument(
        "--output-yaml", help="Write validation results in YAML to specified file"
    )
    return parser.parse_args()


def load_config(filename: str) -> dict:
    with open(filename, "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    return config


def check_submitted_results_are_valid(filename: str, output_file: str) -> bool:
    if not os.path.isfile(filename):
        validation_output = f"<h1>❌ Results Numbers Validation</h1> ❌ Your code did not produce a <code>{filename}</code> file, which is required for grading. Please review the README and update your code."
    else:
        with open(filename, "r") as f:
            try:
                submitted = yaml.load(f, Loader=yaml.SafeLoader)
                if submitted:
                    validation_output = ""
                else:
                    validation_output = f"<h1>❌ Results Numbers Validation</h1> ❌ Your code produced an empty <code>{filename}</code> file, which is required for grading. Please review the README and update your code."
            except (yaml.constructor.ConstructorError, yaml.parser.ParserError) as e:
                if (
                    "python/object/apply"
                    in str(e)
                ):
                    validation_output = textwrap.dedent(f"""
                        <h1>🚩 Results Numbers Validation</h1> Your code produced a <code>{filename}</code> file that contains Python objects.
                        You probably intended them to be human-readable strings or numbers.
                        See the example Python code and the
                        <a href='https://github.com/UofT-Econ-DataAnalytics/files/wiki/%E2%98%81%EF%B8%8F-Online:-Python#the-code-to-automatically-validate-your-results-failed-with-an-error'>guide for troubleshooting Python</a>
                        for more details.<br><br>
                        """)
                elif "expected <block end>, but found '<scalar>'" in str(e):
                    validation_output = textwrap.dedent(f"""
                        <h1>🚩 Results Numbers Validation</h1> Your code produced a <code>{filename}</code> file that is malformed.
                        The most likely issue is that one of your results has extra quotation marks in it, which could be
                        because your code that outputs <code>{filename}</code> has incorrect quotation marks.
                        Please check your code carefully, comparing it to the example code and paying special attention to the quotes.
                        """)
                else:
                    raise e
    if validation_output:
        with open(output_file, "w") as f:
            f.write(validation_output)
        return False
    return True


def load_submitted_results(filename: str) -> dict:
    with open(filename, "r") as f:
        submitted = yaml.load(f, Loader=yaml.SafeLoader)

    # Convert numeric strings to floats
    for key, value in submitted.items():
        if isinstance(value, str):
            try:
                submitted[key] = float(value)
            except ValueError:
                pass

    return submitted


def load_correct_results(json_string: str) -> dict:
    if json_string:
        correct = json.loads(json_string)
    else:
        raise ValueError("No correct results provided, --correct cannot be empty.")
    return correct


def compare_results(
    submitted: dict, correct: dict, input_file: str, output_html: str, output_yaml: str
) -> bool:
    validation_output = []
    errors = False

    def reldif(a, b):
        """Uses the same formula as reldif() in Stata"""
        return abs(a - b) / (abs(a) + 1)

    validated = {"VALIDATED_COUNT": 0}

    for key, value in correct.items():
        if key not in submitted:
            errors = True
            validation_output.append(f"⭕️ no value submitted for <code>{key}</code>")
            validated["VALIDATED_" + key] = "⭕️"
        elif isinstance(submitted[key], str):
            errors = True
            validation_output.append(
                f"⭕️ non-numeric value submitted for <code>{key}</code>"
            )
            validated["VALIDATED_" + key] = "⭕️"
        elif reldif(value, submitted[key]) > 0.01:
            errors = True
            validation_output.append(
                f"❌ {submitted[key]} is not the correct result for <code>{key}</code>"
            )
            validated["VALIDATED_" + key] = "❌"
        else:
            validation_output.append(f"✅ <code>{key}</code>")
            validated["VALIDATED_" + key] = "✅"
            validated["VALIDATED_COUNT"] += 1

    with open(output_html, "w") as f:
        if errors:
            f.write(
                f"<h1>❌ Results Numbers Validation</h1> There are mistakes or omissions in <code>{input_file}</code>: <ul>"
            )
        else:
            f.write(
                f"<h1>✅ Results Numbers Validation</h1> All results in <code>{input_file}</code> are correct: <ul>"
            )
        for line in validation_output:
            f.write(f"<li>{line}</li>")
        f.write("</ul>\n\n")
        f.write("<b>Generated output:</b>\n\n")
        f.write("```yaml\n")
        with open(input_file, "r") as f_input:
            f.write(f_input.read())
        f.write("```\n\n")

    if output_yaml:
        with open(output_yaml, "w") as f:
            yaml.dump(validated, f, allow_unicode=True)

    return not errors


def check_numbers_exist(
    submitted: dict, expected_keys: list, input_file: str, output_html: str
) -> bool:
    validation_output = []
    errors = False
    for key in expected_keys:
        if key not in submitted:
            errors = True
            validation_output.append(f"⭕️ no value submitted for <code>{key}</code>")
        elif isinstance(submitted[key], str):
            errors = True
            validation_output.append(
                f"⭕️ non-numeric value submitted for <code>{key}</code>"
            )
        else:
            validation_output.append(f"🟢 <code>{key}</code>")

    # Append validation output to existing file
    with open(output_html, "a") as f:
        if errors:
            f.write(
                f"<h1>⭕️ Results Numbers Existence</h1> Some expected numbers were not provided in <code>{input_file}</code>: <ul>"
            )
        else:
            f.write(
                f"<h1>🟢 Results Numbers Existence</h1> All expected numbers were provided in <code>{input_file}</code>: <ul>"
            )
        for line in validation_output:
            f.write(f"<li>{line}</li>")
        f.write("</ul>")
        f.write(
            "<i>This check only verifies the numbers exist, not whether they are correct. Your work will be graded manually.</i>"
        )

    return not errors


def check_files_exist(expected_files: list, output_html: str) -> bool:
    validation_output = []
    errors = False
    for file in expected_files:
        if not os.path.isfile(file):
            errors = True
            validation_output.append(f"⭕️ did not find <code>{file}</code>")
        else:
            validation_output.append(f"🟢 <code>{file}</code>")

    # Append validation output to existing file
    with open(output_html, "a") as f:
        if errors:
            f.write(
                "<h1>⭕️ Results Files Existence</h1> Some expected results files were not created: <ul>"
            )
        else:
            f.write(
                "<h1>🟢 Results Files Existence</h1> All expected results files were created: <ul>"
            )
        for line in validation_output:
            f.write(f"<li>{line}</li>")
        f.write("</ul>")
        f.write(
            "<i>This check only verifies the files exist, not whether they are correct. Your work will be graded manually.</i>"
        )

    return not errors


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    # Check numbers
    valid_yaml = check_submitted_results_are_valid(
        filename=config["results_submitted_path"], output_file=args.output
    )

    results_match = None
    results_exist = None
    if valid_yaml:
        if args.correct:
            results_match = compare_results(
                submitted=load_submitted_results(config["results_submitted_path"]),
                correct=load_correct_results(args.correct),
                input_file=config["results_submitted_path"],
                output_html=args.output,
                output_yaml=args.output_yaml,
            )
        if config.get("results_created_numbers"):
            results_exist = check_numbers_exist(
                submitted=load_submitted_results(config["results_submitted_path"]),
                expected_keys=config["results_created_numbers"],
                input_file=config["results_submitted_path"],
                output_html=args.output,
            )
        if not args.correct and not config.get("results_created_numbers"):
            with open(args.output, "a") as f:
                f.write(
                    f"<h1>⚪️ Results Numbers Validation</h1> The results file <code>{config["results_submitted_path"]}</code> is a valid YAML file. The correct numbers aren't configured, so the correctness of your numbers was not validated."
                )
        

    # Check files
    files_exist = None
    if config.get("results_created_files"):
        files_exist = check_files_exist(
            expected_files=config["results_created_files"],
            output_html=args.output,
        )

    # Return with specific exit code
    if not valid_yaml:
        return 3
    elif (results_match is False) or (results_exist is False) or (files_exist is False):
        return 2
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
