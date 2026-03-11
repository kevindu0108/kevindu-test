#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "dvc[s3]==3.66.1",
#     "GitPython==3.1.46",
#     "streamlit==1.53.1",
# ]
# ///

import logging
import os
import secrets
import sys
from datetime import datetime
from html import escape
from io import StringIO
from zoneinfo import ZoneInfo

import dvc.repo
import git
import streamlit as st
from git.exc import GitCommandError

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adjust the logging level for DVC and GitPython
logging.getLogger("aiobotocore").setLevel(logging.CRITICAL)
logging.getLogger("dvc").setLevel(logging.CRITICAL)
logging.getLogger("git").setLevel(logging.CRITICAL)


@st.cache_resource
def get_secret_key() -> str:
    """Get the secret key (generated before Streamlit launch)."""
    return os.environ.get("_UPLOAD_SECRET_KEY", secrets.token_urlsafe(64))


@st.cache_resource
def get_git_repo() -> git.Repo:
    """Initialize and return the git repository."""
    repo = git.Repo(".")
    if os.getenv("GIT_AUTHOR_NAME"):
        repo.config_writer().set_value(
            "user", "name", os.getenv("GIT_AUTHOR_NAME")
        ).release()
    if os.getenv("GIT_AUTHOR_EMAIL"):
        repo.config_writer().set_value(
            "user", "email", os.getenv("GIT_AUTHOR_EMAIL")
        ).release()
    return repo


@st.cache_resource
def get_dvc_repo() -> dvc.repo.Repo:
    """Initialize and return the DVC repository."""
    return dvc.repo.Repo(".")


def log_server_url(secret_key: str) -> None:
    """Log the server URL with secret key to the terminal."""
    server_url = os.getenv("URL")
    if server_url:
        print(f"\n⬆️  Upload raw data: {server_url}/?key={secret_key}")
    else:
        print(f"\n⬆️  Upload raw data: http://localhost:8501/?key={secret_key}")


class FileUpload:
    """Track the upload progress for a single file."""

    def __init__(self, uploaded_file, git_repo, dvc_repo):
        self.timestamp = datetime.now(ZoneInfo("America/Toronto"))
        self.filename = self.sanitize_filename(uploaded_file.name)
        self.filepath = os.path.join("./data/raw", self.filename)
        self.step1_save = None
        self.step2_dvc_local = None
        self.step3_dvc_remote = None
        self.step4_git_local = None
        self.step5_git_remote = None
        self.terminal_logged = False
        self.log_file_uploads = os.getenv("LOG_FILE_UPLOADS")
        self._file_content = uploaded_file.read()
        self._git_repo = git_repo
        self._dvc_repo = dvc_repo
        uploaded_file.seek(0)  # Reset file pointer for potential re-reads

    @staticmethod
    def sanitize_filename(filename):
        """
        Sanitize the input filename to remove directory paths and
        ensure that the file is saved in the intended directory.
        """
        return os.path.basename(filename)

    def save_to_disk(self):
        """Save the file to the data/raw directory."""
        try:
            with open(self.filepath, "wb") as f:
                f.write(self._file_content)
            self.step1_save = True
        except Exception:
            logger.exception(f"Failed to save {self.filename} to disk")
            self.step1_save = False

    def dvc_add(self):
        """Add the file to DVC and stage the .dvc file in git."""
        try:
            self._dvc_repo.add(self.filepath)
            dvc_file = self.filepath + ".dvc"
            self._git_repo.git.add(dvc_file)

            # Check if the .dvc file has any staged changes
            staged_diff = self._git_repo.index.diff("HEAD", paths=[dvc_file])
            if not staged_diff:
                # No changes - file is identical to what's already in git
                self.step2_dvc_local = True
                self.step3_dvc_remote = True
                self.step4_git_local = True
                self.step5_git_remote = True
                logger.info(f"{dvc_file} is unchanged")
            else:
                self.step2_dvc_local = True
        except Exception:
            logger.exception(f"Failed to add {self.filename} to local DVC and git")
            self.step2_dvc_local = False

    def complete_dvc_remote(self, success):
        self.step3_dvc_remote = success

    def complete_git_local(self, success):
        self.step4_git_local = success

    def complete_git_remote(self, success):
        self.step5_git_remote = success

    def generate_log_html(self):
        """Generate HTML for displaying the upload progress."""
        progress_steps = [
            ("Saved to Disk", self.step1_save),
            ("Added to local DVC storage", self.step2_dvc_local),
            ("Pushed to remote DVC storage", self.step3_dvc_remote),
            ("Committed to local git repository", self.step4_git_local),
            ("Pushed to remote git repository", self.step5_git_remote),
        ]
        formatted_timestamp = self.timestamp.strftime("%Y-%m-%d at %I:%M %p %Z")
        progress_html = (
            f"<b>{escape(self.filename)}</b> (uploaded {formatted_timestamp})"
        )
        for step, completed in progress_steps:
            emoji = "✅" if completed is True else "❌" if completed is False else "⏳"
            progress_html += (
                f"<br><span style='padding-left: 20px;'>{emoji} {step}</span>"
            )
            if not self.terminal_logged and completed is False:
                logger.info(f"    {self.filename} - not {step[0].lower() + step[1:]}")
                if self.log_file_uploads:
                    with open(self.log_file_uploads, "a") as log_file:
                        log_file.write(
                            f"{self.filename} - not {step[0].lower() + step[1:]}\n"
                        )
                self.terminal_logged = True
        if not self.terminal_logged and all([step[1] for step in progress_steps]):
            logger.info(f"    {self.filename}")
            if self.log_file_uploads:
                with open(self.log_file_uploads, "a") as log_file:
                    log_file.write(f"{self.filename}\n")
            self.terminal_logged = True
        progress_html += "<p>"
        return progress_html


def push_to_dvc_remote(uploads, dvc_repo):
    """Push all files to DVC remote."""
    try:
        dvc_repo.push()
        logger.info("Pushed to DVC remote")
        success = True
    except Exception:
        logger.exception("Failed to push to DVC remote")
        success = False
    for upload in uploads:
        upload.complete_dvc_remote(success)
    return success


def commit_to_git_local(uploads, git_repo):
    """Commit staged .dvc files to git."""
    try:
        git_repo.git.commit(m="Upload files to data/raw")
        logger.info("Committed to local git repository.")
        success = True
    except GitCommandError as e:
        if "nothing to commit" in str(e):
            logger.warning("No changes to commit to local git repository.")
            success = True
        else:
            logger.exception("Failed to commit changes to local git repository.")
            success = False
    for upload in uploads:
        upload.complete_git_local(success)
    return success


def push_to_git_remote(uploads, git_repo):
    """Push commits to remote git repository with rebase retry logic."""
    try:
        git_repo.remote(name="origin").push().raise_if_error()
        logger.info("Pushed changes to the remote git repo")
        success = True
    except GitCommandError as e:
        if "failed to push some refs" in str(e):
            try:
                git_repo.remote(name="origin").fetch()
                git_repo.git.rebase(f"origin/{git_repo.active_branch.name}")
                logger.info(
                    "Attempt to push git changes failed, rebased changes from remote."
                )
                git_repo.remote(name="origin").push().raise_if_error()
                logger.info("Pushed changes to the remote git repo, after rebasing")
                success = True
            except Exception:
                logger.exception(
                    "Failed to push changes to the remote git repo after rebasing."
                )
                success = False
        else:
            logger.exception("Failed to push changes to the remote git repo.")
            success = False
    for upload in uploads:
        upload.complete_git_remote(success)
    return success


def process_uploads(uploaded_files, progress_placeholder, git_repo, dvc_repo):
    """Process all uploaded files through the 5-step pipeline."""
    uploads = []

    # Initialize FileUpload objects
    for uploaded_file in uploaded_files:
        uploads.append(FileUpload(uploaded_file, git_repo, dvc_repo))

    # Step 1: Save files to disk
    for upload in uploads:
        upload.save_to_disk()
    progress_placeholder.markdown(render_upload_log(uploads), unsafe_allow_html=True)

    # Filter to only successfully saved files
    successful_uploads = [u for u in uploads if u.step1_save]
    if not successful_uploads:
        return uploads

    # Step 2: Add to local DVC
    for upload in successful_uploads:
        upload.dvc_add()
    progress_placeholder.markdown(render_upload_log(uploads), unsafe_allow_html=True)

    # Filter to only successfully added files that need further processing
    dvc_added_uploads = [
        u
        for u in successful_uploads
        if u.step2_dvc_local and u.step3_dvc_remote is None
    ]
    if not dvc_added_uploads:
        return uploads

    # Step 3: Push to DVC remote
    if not push_to_dvc_remote(dvc_added_uploads, dvc_repo):
        progress_placeholder.markdown(
            render_upload_log(uploads), unsafe_allow_html=True
        )
        return uploads
    progress_placeholder.markdown(render_upload_log(uploads), unsafe_allow_html=True)

    # Step 4: Commit to local git
    if not commit_to_git_local(dvc_added_uploads, git_repo):
        progress_placeholder.markdown(
            render_upload_log(uploads), unsafe_allow_html=True
        )
        return uploads
    progress_placeholder.markdown(render_upload_log(uploads), unsafe_allow_html=True)

    # Step 5: Push to remote git
    push_to_git_remote(dvc_added_uploads, git_repo)
    progress_placeholder.markdown(render_upload_log(uploads), unsafe_allow_html=True)

    return uploads


def render_upload_log(uploads):
    """Render the upload log as HTML."""
    if not uploads:
        return "No files uploaded."
    return "".join([upload.generate_log_html() for upload in uploads])


def main() -> None:
    """Main Streamlit application entry point."""

    # Configure page settings (must be first Streamlit command)
    st.set_page_config(page_title="Upload Raw Data", page_icon="⬆️")

    # Ensure the data/raw directory exists
    os.makedirs("./data/raw", exist_ok=True)

    # Initialize repositories
    git_repo = get_git_repo()
    dvc_repo = get_dvc_repo()

    # Get secret key
    secret_key = get_secret_key()

    # Hide streamlit top bar
    st.markdown(
        """
        <style>
            header[data-testid="stHeader"] {
                display: none;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Authentication check
    key = st.query_params.get("key", "")
    if not secret_key:
        st.error("Server configuration error: Secret key is not configured.")
        st.stop()
    if not secrets.compare_digest(key, secret_key):
        st.error("Access Denied. You must provide the correct key to access this page.")
        st.stop()

    # Initialize session state for upload history
    if "all_uploads" not in st.session_state:
        st.session_state.all_uploads = []
    if "processing_started" not in st.session_state:
        st.session_state.processing_started = False

    # Main UI
    st.title("Upload Raw Data")

    # File uploader
    uploaded_files = st.file_uploader(
        "Upload files to add them to DVC",
        accept_multiple_files=True,
        label_visibility="hidden",
        disabled=st.session_state.processing_started,
    )

    # Process button
    def on_upload_click():
        st.session_state.processing_started = True

    button_disabled = not uploaded_files or st.session_state.processing_started
    if st.button(
        "Upload Files",
        type="primary",
        disabled=button_disabled,
        on_click=on_upload_click,
    ):
        if uploaded_files:
            st.text(
                "After processing is complete, refresh the page to upload more files."
            )
            st.title("Upload Progress...")

            progress_placeholder = st.empty()
            progress_placeholder.markdown(
                "Processing uploads...", unsafe_allow_html=True
            )

            new_uploads = process_uploads(
                uploaded_files, progress_placeholder, git_repo, dvc_repo
            )
            st.session_state.all_uploads.extend(new_uploads)


if __name__ == "__main__":
    # Allow Streamlit to execute directly from `uv run`
    # Ref: https://github.com/streamlit/streamlit/issues/9450
    if "__streamlitmagic__" not in locals():
        # Generate secret key and log URL before Streamlit launches
        secret_key = secrets.token_urlsafe(64)
        os.environ["_UPLOAD_SECRET_KEY"] = secret_key
        log_server_url(secret_key)

        # Suppress Streamlit's startup messages by redirecting stdout/stderr
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = StringIO()

        # Launch Streamlit server (re-executes this script in Streamlit context)
        from streamlit.web.bootstrap import run

        run(__file__, False, [], {})

    main()
