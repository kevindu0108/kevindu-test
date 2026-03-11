#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from typing import List, Literal

def parse_args() -> argparse.Namespace:
    """Parse command line arguments
    """
    parser = argparse.ArgumentParser(description="Install and configure Stata on a Debian-based linux system.")

    parser.add_argument('-i', '--install-source', choices=['cache', 'decrypt', 'password'],
                        required=True,
                        help="Specify the source for the Stata installation: cached, decrypted public download, or password-protected download.")

    parser.add_argument('-l', '--license-source', choices=['cache', 'decrypt', 'env', 'interactive', 'password'],
                        required=True,
                        help="Specify the source for the Stata license.")

    parser.add_argument('--edition', choices=['be', 'se', 'mp'], type=str.lower,
                        default='be',
                        help="Specify Stata edition for the license. Default: BE.")

    parser.add_argument('--version', type=int,
                        default=18,
                        help="Specify the Stata version. Default: 18.")

    parser.add_argument('--no-upgrade', action='store_true',
                        help="Skip upgrading Stata to latest minor release.")

    parser.add_argument('--interactive', action='store_true',
                        help="Enter Stata license interactively.")

    parser.add_argument('--install-age', action='store_true',
                        help="Install age encryption tool, even if not necessary for Stata install.")

    parser.add_argument('--add', nargs='*',
                        default=[],
                        help="List of additional packages to install, separated by spaces.")

    return parser.parse_args()


def print_color(text: str, color: Literal["green", "red"]):
    """ Print text in specified color

        ### Args:
            text: text to print
            color: color code
    """

    if color not in ["green", "red"]:
        raise ValueError(f'Unexpected color: {color}. Expected "green" or "red"')

    if color=="green":
        color_val = 32
    elif color=="red":
        color_val = 31
    
    print(f'\033[{color_val}m{text}\033[0m')


def window_manager_present(installed_packages: subprocess.CompletedProcess) -> bool:
    """Check if a window manager is installed.

    Args:
        installed_packages: subprocess object containing the output of 'dpkg -l'

    Returns:
        bool: True if a window manager is installed, False otherwise.
    """

    pattern = r'\b(gnome-shell|xfce4-session|plasma-desktop|mate-desktop-environment|lxsession|cinnamon-session|budgie-desktop|xpra)\b'
    return bool(re.search(pattern, installed_packages.stdout))


def check_license_available(license_source: Literal["cache", "decrypt", "env", "interactive", "password"]):
    """ 
    Check if Stata license is available

    Args:
        license_source (str): The source type of the Stata license.
    """

    if license_source == 'cache':
        print_color('Stata installed from cache...', "green")
    elif license_source == 'decrypt':
        # Check that decryption key is available and 'stata.lic.encrypted' exists
        if os.getenv('STATA_AGE_PRIVATE_KEY') is None:
            raise ValueError('STATA_AGE_PRIVATE_KEY env variable not found')
        elif not os.path.isfile('stata.lic.encrypted'):
            raise ValueError('stata.lic.encrypted not found')
        else:
            print_color('Stata license detected in stata.lic.encrypted, installing Stata...', "green") 
    elif license_source == 'env':
        if os.getenv('STATA_LIC'):
            print_color('Stata license detected in env variable, installing Stata...', "green")
        elif os.getenv('stata_serial') and os.getenv('stata_code') and os.getenv('stata_authorization') and os.getenv('name') and os.getenv('institution'):
            print_color('Stata license information detected in env variables, installing Stata...', "green")
        else:
            raise ValueError('Stata license information not found in env variables')
    elif license_source == 'interactive':
        print_color('Installing Stata interactively, enter your Stata license information when prompted...', "green")
    elif license_source == 'password':
        if os.getenv('STATA_URL_PW') is None:
            raise ValueError('STATA_URL_PW env variable not found')
        elif os.getenv('STATA_URL_BASE') is None:
            raise ValueError('STATA_URL_BASE env variable not found')
        else:
            print_color('Stata license will be fetched from password-protected URL, installing Stata...', "green")
    else:
        raise ValueError(f'Unexpected license source: {license_source}')


def install_linux_dependencies(install_source: str, license_source: str, install_age: bool) -> subprocess.CompletedProcess:
    """ Install Stata dependencies, and the 'age' encryption tool if necessary

        Resolves the following errors:
        - stata: error while loading shared libraries: libtinfo.so.5: cannot open shared object file: No such file or directory
        - stata: error while loading shared libraries: libncurses.so.5: cannot open shared object file: No such file or directory
        - xstata: Gtk-WARNING **: ##:##:##.###: Unable to locate theme engine in module_path: "pixmap"

        Args:
            install_source (str): The source type of the Stata installation.
            license_source (str): The source type of the Stata license.
            install_age (bool): Whether to install 'age'
        Returns:
            subprocess.CompletedProcess: The output of 'dpkg -l' prior to the installation of additional packages in this function.
    """
    installed_packages = subprocess.run(['dpkg', '-l'], capture_output=True, text=True)
    to_install = []

    def package_is_available(package_name: str) -> bool:
        available_packages = subprocess.run(['apt-cache', 'search', package_name], capture_output=True, text=True)

        if re.search(rf'^{re.escape(package_name)}\b', available_packages.stdout):
            return True
        else:
            return False

    def package_is_installed(package_name: str, installed_packages) -> bool:
        if re.search(rf'\b{re.escape(package_name)}\b', installed_packages):
            return True
        else:
            return False

    # Identify packages to install
    for pkg in ['libtinfo5', 'libncurses5']:

        if package_is_installed(pkg, installed_packages.stdout):
            pass
        elif package_is_available(pkg):
            to_install.append(pkg)
        else:
            print_color(f"Warning: {pkg} not installed or available from apt, Stata might not run without it", "red")

    if (install_source == 'decrypt' or license_source == 'decrypt' or install_age) and not package_is_installed('age', installed_packages.stdout):
        to_install.append('age')

    if window_manager_present(installed_packages) and not package_is_installed('gtk2-engines-pixbuf', installed_packages.stdout):
        to_install.append('gtk2-engines-pixbuf')

    # Install packages
    if to_install:
        print_color(f'Installing apt packages: {", ".join(to_install)}', "green")
        subprocess.run(['sudo', 'apt-get', 'update'], check=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y'] + to_install, check=True)
        subprocess.run(['sudo', 'apt-get', 'clean'], check=True)
        subprocess.run(['sudo', 'rm', '-rf', '/var/lib/apt/lists/*'], check=True)

    # Return list of installed packages prior to installing additional packages
    return installed_packages


def install_stata(install_source: Literal['cache', 'decrypt', 'password'], version: int, working_dir: str):
    """Install Stata from specified source.

    Args:
        install_source: The source type from which to install Stata.
        version: The version of Stata to install.
        working_dir: The working directory to return to after installation.

    Returns:
        None
    """

    if install_source == 'cache':
        return
    elif install_source == 'decrypt':
        private_key = os.getenv('STATA_AGE_PRIVATE_KEY')
        url = f'https://github.com/UofT-Econ-DataAnalytics/files/releases/download/files/St{version}Linux64.installed.encrypted'
        installer_file = f'/tmp/statafiles/Stata{version}Linux64_installed.tar.gz'
        cmd = (f'wget --progress=dot:giga -qO- {url} | '
               f'age --decrypt --identity <(echo "{private_key}") --output {installer_file}')
        
        os.makedirs('/tmp/statafiles', exist_ok=True)
        subprocess.run(cmd, shell=True, executable='/bin/bash', check=True)

        subprocess.run(['sudo', 'mkdir', '-p', '/usr/local/stata'], check=True)
        subprocess.run(['sudo', 'tar', '-xzf', installer_file, '-C', '/usr/local/stata'], check=True)
    elif install_source == 'password':
        url_base = os.getenv('STATA_URL_BASE')
        url_installer = f'{url_base}/Stata{version}Linux64.tar.gz'
        installer_file = f'/tmp/statafiles/Stata{version}Linux64.tar.gz'
        download_username = 'oi'
        download_password = os.getenv('STATA_URL_PW')

        os.makedirs('/tmp/statafiles', exist_ok=True)
        subprocess.run(['wget', '--progress=dot:giga', '--user', download_username, '--password', download_password, '-O', installer_file, url_installer], check=True)

        os.chdir('/tmp/statafiles')
        subprocess.run(['tar', '-xzf', installer_file], check=True)
        subprocess.run(['sudo', 'mkdir', '-p', '/usr/local/stata'], check=True)
        os.chdir('/usr/local/stata')

        # The following command returns exit code = 1 even though it's ok. Therefore check=False.
        subprocess.run("sudo sh -c 'yes | /tmp/statafiles/install'", shell=True, check=False)

    os.chdir(working_dir)


def install_stata_license(license_source: str, interactive: bool, working_dir: str) -> None:
    """Install Stata license from specified source.

    Args:
        license_source: The source type of the Stata license.
        interactive: Whether to enter the Stata license interactively. (unused arg?)
        working_dir: The working directory to use.
    """
    
    os.chdir('/usr/local/stata')
    if license_source == 'cache':
        os.chdir(working_dir)
        return
    elif license_source == 'decrypt':
        private_key = os.getenv('STATA_AGE_PRIVATE_KEY')
        cmd = f'cat "{working_dir}/stata.lic.encrypted" | age --decrypt --identity <(echo "{private_key}") --output stata.lic'

        subprocess.run(['sudo', 'touch', 'stata.lic'], check=True)
        subprocess.run(['sudo', 'chmod', 'a+w', 'stata.lic'], check=True)
        subprocess.run(cmd, shell=True, executable='/bin/bash', check=True)
        subprocess.run(['sudo', 'chmod', 'a-w', 'stata.lic'], check=True)
    elif license_source == 'env':
        stata_lic = os.getenv('STATA_LIC')
        if stata_lic:
            subprocess.run(['sudo', 'touch', 'stata.lic'], check=True)
            subprocess.run(['sudo', 'chmod', 'a+w', 'stata.lic'], check=True)
            with open('stata.lic', 'w') as f:
                f.write(stata_lic)
            subprocess.run(['sudo', 'chmod', 'a-w', 'stata.lic'], check=True)
        else:
            # Getting environment variables
            stata_serial = os.getenv('stata_serial')
            stata_code = os.getenv('stata_code')
            stata_authorization = os.getenv('stata_authorization')
            name = os.getenv('name')
            institution = os.getenv('institution')

            # Ensure required environment variables are present
            if not all([stata_serial, stata_code, stata_authorization, name, institution]):
                raise ValueError('One or more required environment variables are missing.')

            # Prepare the input for the stinit command
            input_data = f"""Y
Y
{stata_serial}
{stata_code}
{stata_authorization}
Y
Y
{name}
{institution}
Y
"""

            # If stata.lic file exists, delete it
            if os.path.isfile('stata.lic'):
                subprocess.run(['sudo', 'rm', 'stata.lic'], check=True)
            if os.path.isfile('stata.lic'):
                raise ValueError('stata.lic file exists, but could not be deleted.')

            # Execute the command
            subprocess.run(['sudo', './stinit'], input=input_data.encode(), check=True)
    elif license_source == 'interactive':
        subprocess.run(['sudo', './stinit'], check=True)
    elif license_source == 'password':
        url_base = os.getenv('STATA_URL_BASE')
        url_license = f'{url_base}/stata.lic'
        license_file = 'stata.lic'
        download_username = 'oi'
        download_password = os.getenv('STATA_URL_PW')

        subprocess.run(['sudo', 'touch', 'stata.lic'], check=True)
        subprocess.run(['sudo', 'chmod', 'a+w', 'stata.lic'], check=True)
        subprocess.run(['wget', '--user', download_username, '--password', download_password, '-O', license_file, url_license], check=True)
        subprocess.run(['sudo', 'chmod', 'a-w', 'stata.lic'], check=True)
    else:
        raise ValueError(f'Unexpected license source: {license_source}')
    
    os.chdir(working_dir)


def finish_stata_install(install_source: str, edition: str, no_upgrade: bool, installed_packages: subprocess.CompletedProcess):
    """Tidy temporary files and place Stata executable on PATH.

    Args:
        install_source: The source type of the Stata installation.
        edition: The edition of Stata to install.
        installed_packages: The subprocess.CompletedProcess object containing information about the installed packages.
    """

    if install_source != 'cache':
        # Remove temporary files
        subprocess.run(['rm', '-r', '/tmp/statafiles'], check=True)

        # Allow all users to run Stata
        subprocess.run(['sudo', 'chmod', 'a+r', '-R', '/usr/local/stata'], check=True)

        # Update Stata to latest minor release
        if not no_upgrade:
            subprocess.run(['sudo', 'chmod', 'o+w', '-R', '/usr/local/stata'], check=True)
            input_data = """
update query
update all, exit
"""
            subprocess.run(['/usr/local/stata/stata'], input=input_data.encode(), check=True)
            subprocess.run(['/usr/local/stata/stata'], input=input_data.encode(), check=True)
            subprocess.run(['sudo', 'chmod', 'o-w', '-R', '/usr/local/stata'], check=True)

    # Create symbolic link to Stata executable in PATH
    if edition == 'be':
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/stata', '/usr/local/bin/stata'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/xstata', '/usr/local/bin/xstata'], check=True)

        # Delete symbolic links for other editions if they exist
        subprocess.run(['sudo', 'rm', '-f', '/usr/local/bin/stata-se', '/usr/local/bin/stata-mp', '/usr/local/bin/xstata-se', '/usr/local/bin/xstata-mp'], check=False)

    elif edition == 'se':
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/stata-se', '/usr/local/bin/stata'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/stata-se', '/usr/local/bin/stata-se'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/xstata-se', '/usr/local/bin/xstata'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/xstata-se', '/usr/local/bin/xstata-se'], check=True)

        # Delete symbolic links for other editions if they exist
        subprocess.run(['sudo', 'rm', '-f', '/usr/local/bin/stata-mp', '/usr/local/bin/xstata-mp'], check=False)
    elif edition == 'mp':
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/stata-mp', '/usr/local/bin/stata'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/stata-mp', '/usr/local/bin/stata-mp'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/xstata-mp', '/usr/local/bin/xstata'], check=True)
        subprocess.run(['sudo', 'ln', '-sf', '/usr/local/stata/xstata-mp', '/usr/local/bin/xstata-mp'], check=True)

        # Delete symbolic links for other editions if they exist
        subprocess.run(['sudo', 'rm', '-f', '/usr/local/bin/stata-se', '/usr/local/bin/xstata-se'], check=False)
    else:
        raise ValueError(f'Unexpected Stata edition: {edition}')

    print('')
    print_color('Stata installed successfully!', "green")
    print('')


def install_addons(addons: List[str]):
    """ Install additional packages

        Args:
            addons: List of additional packages to install.
    """

    if not addons:
        # Launch Stata just to create the log file and check license
        input_data = """
exit, clear
"""
        result = subprocess.run(['stata'], input=input_data, capture_output=True, text=True)

        with open('stata.log', 'a') as f:
            f.write(result.stdout)
            print(result.stdout)

    if 'requirements' in addons:
        print_color("Installing add-on: Stata package 'require' from https://github.com/sergiocorreia/stata-require/tree/1.4.0 and requirements from ./packages-stata.txt", "green")
        input_data = """
net set ado SITE
net install require, from("https://raw.githubusercontent.com/sergiocorreia/stata-require/1.4.0/src/")
require using packages-stata.txt, install
"""
        
        subprocess.run(['sudo', 'mkdir', '-p', '/usr/local/ado'], check=True)
        subprocess.run(['sudo', 'chmod', 'a+w', '-R', '/usr/local/ado'], check=True)
        result = subprocess.run(['stata'], input=input_data, capture_output=True, text=True)
        subprocess.run(['sudo', 'chmod', 'a-w', '-R', '/usr/local/ado'], check=True)

        with open('stata.log', 'a') as f:
            f.write(result.stdout)
            print(result.stdout)

        addons.remove('requirements')

    if 'project' in addons:
        url_base = os.getenv('STATA_URL_BASE')
        url_project = f'{url_base}/project_stata.zip'
        project_file = '/tmp/statafiles_project/project_stata.zip'
        download_username = 'oi'
        download_password = os.getenv('STATA_URL_PW')

        # Ensure required environment variables are present
        if not all([url_base, download_password]):
            print_color("Skipping add-on: Stata package 'project' can only be installed if env variables STATA_URL_BASE and STATA_URL_PW are defined", "red")
        else:
            print_color("Installing add-on: Stata package 'project' from password-protected URL", "green")
            os.makedirs('/tmp/statafiles_project/ado', exist_ok=True)
            subprocess.run(['wget', '--user', download_username, '--password', download_password, '-O', project_file, url_project], check=True)
            subprocess.run(['unzip', project_file, '-d', '/tmp/statafiles_project/ado'], check=True)

            input_data = """
net set ado SITE
net install project, from(/tmp/statafiles_project/ado)
"""
            
            subprocess.run(['sudo', 'mkdir', '-p', '/usr/local/ado'], check=True)
            subprocess.run(['sudo', 'chmod', 'a+w', '-R', '/usr/local/ado'], check=True)
            result = subprocess.run(['stata'], input=input_data, capture_output=True, text=True)
            subprocess.run(['sudo', 'chmod', 'a-w', '-R', '/usr/local/ado'], check=True)

            with open('stata.log', 'a') as f:
                f.write(result.stdout)
                print(result.stdout)

            subprocess.run(['rm', '-r', '/tmp/statafiles_project'], check=True)
        
        addons.remove('project')

    if 'jupyter' in addons:
        try:
            import stata_kernel
            print_color("Skipping add-on: Stata Jupyter kernel already installed", "green")
        except:
            print_color("Installing add-on: Stata Jupyter kernel from https://kylebarron.dev/stata_kernel", "green")
            subprocess.run(['pip', 'install', 'notebook', '--user'], check=True)
            subprocess.run(['pip', 'install', 'stata_kernel', 'setuptools'], check=True)
            subprocess.run(["python", "-m", "stata_kernel.install"], check=True)
        
        addons.remove('jupyter')

    if 'setroot' in addons:
        print_color("Installing add-on: Stata package 'setroot' from https://github.com/sergiocorreia/stata-setroot", "green")
        input_data = """
net set ado SITE
net install setroot, from("https://raw.githubusercontent.com/sergiocorreia/stata-setroot/master/src/")
"""
        
        subprocess.run(['sudo', 'mkdir', '-p', '/usr/local/ado'], check=True)
        subprocess.run(['sudo', 'chmod', 'a+w', '-R', '/usr/local/ado'], check=True)
        result = subprocess.run(['stata'], input=input_data, capture_output=True, text=True)
        subprocess.run(['sudo', 'chmod', 'a-w', '-R', '/usr/local/ado'], check=True)

        with open('stata.log', 'a') as f:
            f.write(result.stdout)
            print(result.stdout)
        
        addons.remove('setroot')

    # Verify whether Stata gave a 'license not applicable' error
    if os.path.isfile('stata.log'):
        with open('stata.log', 'r') as f:
            log = f.read()
            if 'License not applicable to this Stata' in log:
                raise ValueError('ERROR: License is valid but not for this Stata version or edition.')

    # Verify if there were any addons specified but not installed
    if addons:
        addons = ', '.join(addons)
        print_color(f'Skipping unrecognized addons: {addons}', "red")


def main() -> int:
    args = parse_args()
    working_dir = os.getcwd()
    check_license_available(args.license_source)
    installed_packages = install_linux_dependencies(args.install_source, args.license_source, args.install_age)
    install_stata(args.install_source, args.version, working_dir)
    install_stata_license(args.license_source, args.interactive, working_dir)
    finish_stata_install(args.install_source, args.edition, args.no_upgrade, installed_packages)
    install_addons(args.add)
    return 0


if __name__ == '__main__':
    sys.exit(main())
