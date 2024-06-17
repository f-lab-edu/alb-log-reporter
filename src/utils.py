import logging
import os
import shutil

import requests

logger = logging.getLogger()


def get_intro_text():
    intro_text = """
 _______  ___      _______    ___      _______  _______                  
|   _   ||   |    |  _    |  |   |    |       ||       |                 
|  |_|  ||   |    | |_|   |  |   |    |   _   ||    ___|                 
|       ||   |    |       |  |   |    |  | |  ||   | __                  
|       ||   |___ |  _   |   |   |___ |  |_|  ||   ||  |                 
|   _   ||       || |_|   |  |       ||       ||   |_| |                 
|__| |__||_______||_______|  |_______||_______||_______|                 
 ______    _______  _______  _______  ______  _______  _______  ______   
|    _ |  |       ||       ||       ||    _ ||       ||       ||    _ |  
|   | ||  |    ___||    _  ||   _   ||   | |||_     _||    ___||   | ||  
|   |_||_ |   |___ |   |_| ||  | |  ||   |_||_ |   |  |   |___ |   |_||_ 
|    __  ||    ___||    ___||  |_|  ||    __  ||   |  |    ___||    __  |
|   |  | ||   |___ |   |    |       ||   |  | ||   |  |   |___ |   |  | |
|___|  |_||_______||___|    |_______||___|  |_||___|  |_______||___|  |_|

Author: @eunch
email: manatee569@anglernook.com
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
    logger.info("🌐 Starting update Abuse IP.")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to updated Abuse IP data. Reason: {e}")
        return None
    logger.info("✅ Updated Abuse IP.")
    return set(response.text.splitlines())