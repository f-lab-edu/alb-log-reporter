import argparse
import configparser
import logging
import os
from datetime import datetime, timezone as dt_timezone

import boto3
import pytz
from botocore.exceptions import NoRegionError, NoCredentialsError, ClientError

from src.aws_sso_helper import AWSSSOHelper
from src.elb_log_analyzer import ELBLogAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

MAX_RETRIES = 3


def is_sso_profile(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    session_section = f"sso-session {profile_name}"
    return config.has_section(session_section)


def get_sso_profile_info(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    session_section = f"sso-session {profile_name}"
    if config.has_section(session_section):
        sso_start_url = config.get(session_section, 'sso_start_url')
        sso_region = config.get(session_section, 'sso_region')
        return sso_start_url, sso_region
    raise ValueError(f"SSO profile {profile_name} is missing required fields.")


def create_aws_session(profile_name):
    try:
        if is_sso_profile(profile_name):
            logger.info(f"Using AWS SSO profile: {profile_name}")
            sso_start_url, sso_region = get_sso_profile_info(profile_name)
            sso_helper = AWSSSOHelper(start_url=sso_start_url, session_name=profile_name, region_name=sso_region)
            return sso_helper
        else:
            logger.info(f"Using AWS profile: {profile_name}")
            return boto3.Session(profile_name=profile_name)
    except NoCredentialsError:
        logger.error(f"No credentials found for profile: {profile_name}")
        raise
    except NoRegionError:
        logger.error(f"No region specified in profile: {profile_name}")
        raise
    except Exception as error:
        logger.error(f"An error occurred while creating AWS session: {error}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(description="AWS ELB Log Reporter")
    parser.add_argument('-p', '--profile', default='default', help='AWS profile name (default: default)')
    parser.add_argument('-b', '--s3-uri', required=True,
                        help='S3 URI of the ELB logs, e.g., s3://your-bucket-name/prefix')
    parser.add_argument('-s', '--start', required=True, help='Start datetime in YYYY-MM-DD HH:MM format')
    parser.add_argument('-e', '--end', default=datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M'),
                        help='End datetime in YYYY-MM-DD HH:MM format (default: now)')
    parser.add_argument('-z', '--timezone', default='UTC', help='Timezone for log timestamps (default: UTC)')
    return parser.parse_args()


def process_logs(s3_client, bucket_name, prefix, start_datetime, end_datetime, timezone):
    try:
        analyzer = ELBLogAnalyzer(s3_client=s3_client, bucket_name=bucket_name, prefix=prefix,
                                  start_datetime=start_datetime.strftime('%Y-%m-%d %H:%M'),
                                  end_datetime=end_datetime.strftime('%Y-%m-%d %H:%M'),
                                  timezone=timezone)

        script_start_time = datetime.now(dt_timezone.utc)
        gz_directory = analyzer.download_logs()
        log_directory = analyzer.decompress_logs(gz_directory)
        parsed_logs = analyzer.parse_logs(log_directory)
        if parsed_logs:
            analysis_data = analyzer.analyze_logs(parsed_logs)
            analyzer.save_to_excel(analysis_data, prefix, script_start_time)
        analyzer.clean_up([gz_directory, log_directory])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ExpiredToken':
            logger.error("Token expired. Please run the program again to reauthenticate.")
        else:
            logger.error(f"Client error occurred: {e}")
    except NoRegionError:
        logger.error("No region specified in profile. Please provide a region in the AWS profile configuration.")
    except Exception as error:
        logger.error(f"An error occurred: {error}")
        try:
            analyzer.clean_up([gz_directory, log_directory])
        except NameError:
            pass


def main():
    args = parse_args()

    try:
        start_datetime = datetime.strptime(args.start, '%Y-%m-%d %H:%M')
        end_datetime = datetime.strptime(args.end, '%Y-%m-%d %H:%M')
    except ValueError:
        logger.error("Invalid datetime format. Expected format: YYYY-MM-DD HH:MM")
        return

    try:
        timezone = pytz.timezone(args.timezone)
    except pytz.UnknownTimeZoneError:
        logger.error(f"Invalid timezone: {args.timezone}")
        return

    aws_session = create_aws_session(args.profile)

    # Get and display accounts for user selection
    accounts = aws_session.get_token_accounts()
    account_ids = sorted(accounts.keys())
    print("Available accounts:")
    for i, account_id in enumerate(account_ids):
        print(f"{i + 1}. {accounts[account_id]['accountName']} ({account_id})")

    selected_account_index = int(input("Select an account by number: ")) - 1
    selected_account_id = account_ids[selected_account_index]
    print(f"Selected account: {accounts[selected_account_id]['accountName']} ({selected_account_id})")

    # Get and display roles for user selection
    roles = accounts[selected_account_id]['roles']
    print("Available roles:")
    for i, role in enumerate(roles):
        print(f"{i + 1}. {role}")

    selected_role_index = int(input("Select a role by number: ")) - 1
    selected_role_name = roles[selected_role_index]
    print(f"Selected role: {selected_role_name}")

    # Get SSO session with selected account and role
    aws_session = aws_session.get_sso_session(selected_account_id, selected_role_name)

    retries = 0
    while retries < MAX_RETRIES:
        try:
            bucket_name, prefix = args.s3_uri.replace("s3://", "").split("/", 1)
            process_logs(aws_session.client('s3'), bucket_name, prefix, start_datetime, end_datetime, args.timezone)
            break
        except ClientError as e:
            if e.response['Error']['Code'] == 'ExpiredToken':
                retries += 1
                logger.error(f"Token expired. Attempting to refresh token... (Attempt {retries}/{MAX_RETRIES})")
                aws_session._refresh_token()
            else:
                logger.error(f"Client error occurred: {e}")
                break
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            break


if __name__ == '__main__':
    main()
