import logging
import os
import shutil

import requests

logger = logging.getLogger()


def get_intro_text():
    intro_text = """
  ____  _      ____       _       ___    ____      ____     ___  ____   ___   ____  ______    ___  ____  
 /    || |    |    \     | |     /   \  /    |    |    \   /  _]|    \ /   \ |    \|      |  /  _]|    \ 
|  o  || |    |  o  )    | |    |     ||   __|    |  D  ) /  [_ |  o  )     ||  D  )      | /  [_ |  D  )
|     || |___ |     |    | |___ |  O  ||  |  |    |    / |    _]|   _/|  O  ||    /|_|  |_||    _]|    / 
|  _  ||     ||  O  |    |     ||     ||  |_ |    |    \ |   [_ |  |  |     ||    \  |  |  |   [_ |    \ 
|  |  ||     ||     |    |     ||     ||     |    |  .  \|     ||  |  |     ||  .  \ |  |  |     ||  .  \ 
|__|__||_____||_____|    |_____| \___/ |___,_|    |__|\_||_____||__|   \___/ |__|\_| |__|  |_____||__|\_|

AWS ELB Log Reporter
Version: 1.0.0

This tool automates the analysis of AWS Application Load Balancer (ALB) logs 
by downloading, decompressing, parsing, and generating a detailed report.

Usage:
python main.py -p PROFILE_NAME -b S3_URI -s "START_DATETIME" -e "END_DATETIME" -z "TIMEZONE"

Options:
-p, --profile    AWS profile name (default: default)
-b, --bucket     S3 URI of the ELB logs, e.g., s3://{your-bucket-name}/prefix
-s, --start      Start datetime in YYYY-MM-DD HH:MM format
-e, --end        End datetime in YYYY-MM-DD HH:MM format (default: now)
-z, --timezone   Timezone for log timestamps (default: UTC)
"""
    return intro_text


def create_directory(path):
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        os.makedirs(abs_path)
    return abs_path


def clean_directory(directory):
    abs_path = os.path.abspath(directory)
    if os.path.exists(abs_path):
        try:
            for file_name in os.listdir(abs_path):
                file_path = os.path.join(abs_path, file_name)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}. Reason: {e}")
        except FileNotFoundError:
            logger.warning(f"Directory not found: {abs_path}. Skipping cleanup.")
        except OSError as e:
            logger.error(f"Failed to delete directory {abs_path}. Reason: {e}")
    else:
        os.makedirs(abs_path)


def download_abuseipdb(
        url="https://raw.githubusercontent.com/borestad/blocklist-abuseipdb/main/abuseipdb-s100-30d.ipv4"):
    response = requests.get(url)
    response.raise_for_status()
    return set(response.text.splitlines())
