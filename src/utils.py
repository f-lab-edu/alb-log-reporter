import logging
import os
import shutil

logger = logging.getLogger()


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
