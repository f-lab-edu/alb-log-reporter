import os
import re
from datetime import datetime

import pytz


def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def clean_directory(directory):
    try:
        for file_name in os.listdir(directory):
            file_path = os.path.join(directory, file_name)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
    except FileNotFoundError:
        print(f"Directory not found: {directory}. Skipping cleanup.")
    except OSError as e:
        print(f"Failed to delete directory {directory}. Reason: {e}")


def validate_s3_uri(s3_uri):
    pattern = r'^s3:\/\/[a-zA-Z0-9.\-_\/]+$'
    if not re.match(pattern, s3_uri):
        raise ValueError("Invalid S3 URI format. Expected format: s3://bucket_name/prefix")


def validate_date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Invalid date format. Expected format: YYYY-MM-DD")


def validate_time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M')
    except ValueError:
        raise ValueError("Invalid time format. Expected format: HH:MM")


def parse_time(time_str):
    if time_str:
        return datetime.strptime(time_str, '%H:%M').time()
    return None


def get_timezone_for_region(region_name, region_timezone_map):
    return pytz.timezone(region_timezone_map.get(region_name, 'UTC'))


REGION_TIMEZONE_MAP = {
    'us-east-1': 'US/Eastern',
    'us-east-2': 'US/Eastern',
    'us-west-1': 'US/Pacific',
    'us-west-2': 'US/Pacific',
    'af-south-1': 'Africa/Johannesburg',
    'ap-east-1': 'Asia/Hong_Kong',
    'ap-south-2': 'Asia/Kolkata',
    'ap-southeast-3': 'Asia/Jakarta',
    'ap-southeast-4': 'Australia/Melbourne',
    'ap-south-1': 'Asia/Kolkata',
    'ap-northeast-3': 'Asia/Osaka',
    'ap-northeast-2': 'Asia/Seoul',
    'ap-southeast-1': 'Asia/Singapore',
    'ap-southeast-2': 'Australia/Sydney',
    'ap-northeast-1': 'Asia/Tokyo',
    'ca-central-1': 'America/Toronto',
    'ca-west-1': 'America/Edmonton',
    'eu-central-1': 'Europe/Berlin',
    'eu-west-1': 'Europe/Dublin',
    'eu-west-2': 'Europe/London',
    'eu-south-1': 'Europe/Rome',
    'eu-west-3': 'Europe/Paris',
    'eu-south-2': 'Europe/Madrid',
    'eu-north-1': 'Europe/Stockholm',
    'eu-central-2': 'Europe/Zurich',
    'il-central-1': 'Asia/Jerusalem',
    'me-south-1': 'Asia/Bahrain',
    'me-central-1': 'Asia/Dubai',
    'sa-east-1': 'America/Sao_Paulo',
}

ASCII_ART = r"""
 ▄▄▄▄▄▄▄ ▄▄▄     ▄▄▄▄▄▄▄    ▄▄▄     ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄    ▄▄▄▄▄▄   ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄   ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄   
█       █   █   █  ▄    █  █   █   █       █       █  █   ▄  █ █       █       █       █   ▄  █ █       █       █   ▄  █  
█   ▄   █   █   █ █▄█   █  █   █   █   ▄   █   ▄▄▄▄█  █  █ █ █ █    ▄▄▄█    ▄  █   ▄   █  █ █ █ █▄     ▄█    ▄▄▄█  █ █ █  
█  █▄█  █   █   █       █  █   █   █  █ █  █  █  ▄▄   █   █▄▄█▄█   █▄▄▄█   █▄█ █  █ █  █   █▄▄█▄  █   █ █   █▄▄▄█   █▄▄█▄ 
█       █   █▄▄▄█  ▄   █   █   █▄▄▄█  █▄█  █  █ █  █  █    ▄▄  █    ▄▄▄█    ▄▄▄█  █▄█  █    ▄▄  █ █   █ █    ▄▄▄█    ▄▄  █
█   ▄   █       █ █▄█   █  █       █       █  █▄▄█ █  █   █  █ █   █▄▄▄█   █   █       █   █  █ █ █   █ █   █▄▄▄█   █  █ █
█▄▄█ █▄▄█▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█  █▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█▄▄▄▄▄▄▄█  █▄▄▄█  █▄█▄▄▄▄▄▄▄█▄▄▄█   █▄▄▄▄▄▄▄█▄▄▄█  █▄█ █▄▄▄█ █▄▄▄▄▄▄▄█▄▄▄█  █▄█

"""
