import logging
import os
import shutil

import requests

logger = logging.getLogger()


def get_intro_text():
    intro_text = """
  ____  _      ____       _       ___    ____      ____     ___  ____   ___   ____  ______    ___  ____  
 /    || |    |    \\     | |     /   \\  /    |    |    \\   /  _]|    \\ /   \\ |    \\|      |  /  _]|    \\ 
|  o  || |    |  o  )    | |    |     ||   __|    |  D  ) /  [_ |  o  )     ||  D  )      | /  [_ |  D  )
|     || |___ |     |    | |___ |  O  ||  |  |    |    / |    _]|   _/|  O  ||    /|_|  |_||    _]|    / 
|  _  ||     ||  O  |    |     ||     ||  |_ |    |    \\ |   [_ |  |  |     ||    \\  |  |  |   [_ |    \\ 
|  |  ||     ||     |    |     ||     ||     |    |  .  \\|     ||  |  |     ||  .  \\ |  |  |     ||  .  \\ 
|__|__||_____||_____|    |_____| \\___/ |___,_|    |__|\\_||_____||__|   \\___/ |__|\\_| |__|  |_____||__|\\_|
"""
    return intro_text


def create_directory(path):
    abs_path = os.path.abspath(path)
    try:
        if not os.path.exists(abs_path):
            os.makedirs(abs_path)
    except OSError as e:
        logger.error(f"❌ Failed to create directory {abs_path}. Reason: {e}")
        return None
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
                    logger.error(f"❌ Failed to delete {file_path}. Reason: {e}")
        except FileNotFoundError:
            logger.warning(f"⚠️ Directory not found: {abs_path}. Skipping cleanup.")
        except OSError as e:
            logger.error(f"❌ Failed to delete directory {abs_path}. Reason: {e}")
    else:
        os.makedirs(abs_path)


def download_abuseipdb(
        url="https://raw.githubusercontent.com/borestad/blocklist-abuseipdb/main/abuseipdb-s100-30d.ipv4"):
    logger.info("🌐 Starting update from AbuseIPDB...")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to updated data from AbuseIPDB. Reason: {e}")
        return None
    logger.info("✅ Successfully updated data from AbuseIPDB.")
    return set(response.text.splitlines())
