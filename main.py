import argparse
import configparser
import logging
import os
from datetime import datetime, timezone as dt_timezone

import boto3
import pytz
from botocore.config import Config
from botocore.exceptions import NoRegionError, NoCredentialsError, ClientError
from prettytable import PrettyTable

from src.alb_log_analyzer import ELBLogAnalyzer
from src.aws_sso_helper import AWSSSOHelper
from src.utils import get_intro_text

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

MAX_RETRIES = 3  # Maximum number of retries for token refresh


def is_sso_profile(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    profile_section = f"profile {profile_name}"
    return config.has_section(profile_section) and 'sso_start_url' in config[profile_section]


def is_sso_session_profile(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    session_section = f"sso-session {profile_name}"
    return config.has_section(session_section)


def get_sso_profile_info(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    profile_section = f"profile {profile_name}"
    if config.has_section(profile_section):
        sso_start_url = config.get(profile_section, 'sso_start_url')
        sso_region = config.get(profile_section, 'sso_region')
        sso_account_id = config.get(profile_section, 'sso_account_id', fallback=None)
        sso_role_name = config.get(profile_section, 'sso_role_name', fallback=None)
        sso_session = config.get(profile_section, 'sso_session')
        return sso_start_url, sso_region, sso_account_id, sso_role_name, sso_session
    raise ValueError(f"❌ SSO profile {profile_name} is missing required fields.")


def get_sso_session_profile_info(profile_name):
    config = configparser.ConfigParser()
    config_path = os.path.expanduser("~/.aws/config")
    config.read(config_path)
    session_section = f"sso-session {profile_name}"
    if config.has_section(session_section):
        sso_start_url = config.get(session_section, 'sso_start_url')
        sso_region = config.get(session_section, 'sso_region')
        return sso_start_url, sso_region
    raise ValueError(f"❌ SSO session profile {profile_name} is missing required fields.")


def is_access_key_profile(profile_name):
    credentials_config = configparser.ConfigParser()
    credentials_path = os.path.expanduser("~/.aws/credentials")
    credentials_config.read(credentials_path)
    return profile_name in credentials_config


def create_aws_session(profile_name, profile_type):
    try:
        if profile_type == 'profile':
            if is_sso_profile(profile_name):
                logger.info(f"✔️ Using AWS SSO profile: {profile_name}")
                sso_start_url, sso_region, sso_account_id, sso_role_name, sso_session = get_sso_profile_info(
                    profile_name)
                sso_helper = AWSSSOHelper(start_url=sso_start_url, session_name=sso_session, region_name=sso_region)
                if not sso_helper.token_cache:
                    logger.info(
                        f"🔒 Profile {profile_name} is not device authenticated. ⏳ Starting device authorization flow...")
                    sso_helper._start_device_authorization_flow()
                return sso_helper, sso_account_id, sso_role_name
            else:
                raise ValueError(f"❌ Profile {profile_name} not found or not configured correctly for SSO.")
        elif profile_type == 'sso-session':
            if is_sso_session_profile(profile_name):
                logger.info(f"✔️ Using AWS SSO session profile: {profile_name}")
                sso_start_url, sso_region = get_sso_session_profile_info(profile_name)
                sso_helper = AWSSSOHelper(start_url=sso_start_url, session_name=profile_name, region_name=sso_region)
                if not sso_helper.token_cache:
                    logger.info(
                        f"🔒 Profile {profile_name} is not device authenticated. ⏳ Starting device authorization flow...")
                    sso_helper._start_device_authorization_flow()
                return sso_helper, None, None
            else:
                raise ValueError(f"❌ SSO session profile {profile_name} not found or not configured correctly.")
        elif profile_type == 'access_key':
            if is_access_key_profile(profile_name):
                logger.info(f"✔️ Using AWS access key profile: {profile_name}")
                return boto3.Session(profile_name=profile_name), None, None
            else:
                raise ValueError(f"❌ Profile {profile_name} not found in credentials file.")
        else:
            raise ValueError(f"❌ Invalid profile type: {profile_type}")
    except NoCredentialsError:
        logger.error(f"❌ No credentials found for profile: {profile_name}")
        raise
    except NoRegionError:
        logger.error(f"❌ No region specified in profile: {profile_name}")
        raise
    except Exception as error:
        logger.error(f"❌ An error occurred while creating AWS session: {error}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description=get_intro_text(),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-p', '--profile', default='default', help='AWS profile name (default: default)')
    parser.add_argument('-t', '--profile-type', choices=['access_key', 'profile', 'sso-session'], required=True,
                        help='The type of AWS profile to use: "profile" for SSO profiles, "sso-session" for SSO session profiles, or "access_key" for access key profiles.')
    parser.add_argument('-b', '--bucket', required=True,
                        help='S3 URI of the ELB logs, e.g., s3://{your-bucket-name}/AWSLogs/{account_id}/elasticloadbalancing/{region}/')
    parser.add_argument('-s', '--start', required=True, help='Start datetime in YYYY-MM-DD HH:MM format')
    parser.add_argument('-e', '--end', default=datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M'),
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
            logger.error("❌ Token expired. Please run the program again to reauthenticate.")
        else:
            logger.error(f"❌ Client error occurred: {e}")
    except NoRegionError:
        logger.error("❌ No region specified in profile. Please provide a region in the AWS profile configuration.")
    except Exception as error:
        logger.error(f"❌ An error occurred: {error}")
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
        logger.error("❌ Invalid datetime format. Expected format: YYYY-MM-DD HH:MM")
        return

    try:
        timezone = pytz.timezone(args.timezone)
    except pytz.UnknownTimeZoneError:
        logger.error(f"❌ Invalid timezone: {args.timezone}")
        return

    aws_session, sso_account_id, sso_role_name = create_aws_session(args.profile, args.profile_type)

    if args.profile_type == 'profile' or args.profile_type == 'sso-session':
        if not sso_account_id or not sso_role_name:
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    accounts = aws_session.get_token_accounts()
                    break
                except Exception as e:
                    logger.error(f"❌ Failed to retrieve SSO accounts: {e}")
                    retries += 1
                    if retries < MAX_RETRIES:
                        logger.warning("⚠️ Retrying to retrieve SSO accounts...")
                    else:
                        logger.error("❌ Max retries reached. Exiting...")
                        return

            if not accounts:
                logger.error("❌ Failed to retrieve SSO accounts after multiple attempts.")
                return

            sorted_accounts = sorted(accounts.items(), key=lambda item: item[1]['accountName'])

            account_table = PrettyTable()
            account_table.field_names = ["📍", "💼 Account Name", "🆔 Account ID"]
            for i, (account_id, account_info) in enumerate(sorted_accounts):
                account_table.add_row([i + 1, account_info['accountName'], account_id])
            print(account_table)

            selected_account_index = int(input("\n➡️ Select an account by number: ")) - 1
            selected_account_id = sorted_accounts[selected_account_index][0]
            print(
                f"\n✔️ Selected account: {sorted_accounts[selected_account_index][1]['accountName']} ({selected_account_id})\n")

            roles = sorted(sorted_accounts[selected_account_index][1]['roles'])

            role_table = PrettyTable()
            role_table.field_names = ["📍", "⭐ Role Name"]
            for i, role in enumerate(roles):
                role_table.add_row([i + 1, role])
            print(role_table)

            selected_role_index = int(input("\n➡️ Select a role by number: ")) - 1
            selected_role_name = roles[selected_role_index]
            print(f"\n✔️ Selected role: {selected_role_name}\n")

            boto3_session = aws_session.get_sso_session(selected_account_id, selected_role_name)
        else:
            boto3_session = aws_session.get_sso_session(sso_account_id, sso_role_name)
    else:
        boto3_session = aws_session

    s3_client = boto3_session.client('s3', config=Config(max_pool_connections=50))

    retries = 0
    while retries < MAX_RETRIES:
        try:
            bucket_name, prefix = args.bucket.replace("s3://", "").split("/", 1)
            process_logs(s3_client, bucket_name, prefix, start_datetime, end_datetime, args.timezone)
            break
        except ClientError as e:
            if e.response['Error']['Code'] == 'ExpiredToken':
                retries += 1
                logger.error(f"❌ Token expired. Attempting to refresh token... (Attempt {retries}/{MAX_RETRIES})")
                aws_session._refresh_token()
            else:
                logger.error(f"❌ Client error occurred: {e}")
                break
        except Exception as e:
            logger.error(f"❌ An error occurred: {e}")
            break


if __name__ == '__main__':
    main()
