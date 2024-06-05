import logging
from datetime import datetime

import boto3
from botocore.config import Config

from src.aws_sso_helper import AWSSSOHelper
from src.elb_log_analyzer import ELBLogAnalyzer
from src.utils import ASCII_ART, validate_s3_uri, validate_date, validate_time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


def main():
    print(ASCII_ART)
    print("""
    Welcome to the AWS ALB Log Analysis Tool!

    This tool guides you through the process of creating a session by selecting an AWS account and role,
    downloading, decompressing, parsing, and analyzing ALB logs.

    Please follow the instructions to proceed.
    """)

    auth_method = input("Select authentication method (1: AWS SSO, 2: AWS Access Keys): ").strip()

    if auth_method == '1':
        start_url = input("[Required] Enter AWS SSO Start URL: ")
        if not start_url:
            raise ValueError("AWS SSO Start URL is required.")
        session_name = input("[Required] Enter AWS SSO Session Name: ")
        if not session_name:
            raise ValueError("AWS SSO Session Name is required.")

        helper = AWSSSOHelper(start_url=start_url, session_name=session_name)

        try:
            accounts = helper.get_token_accounts()
        except Exception as e:
            logger.error(f"Exception occurred: {e}. Re-authenticating...")
            helper._start_device_authorization_flow()
            accounts = helper.get_token_accounts()

        account_list = sorted(accounts.items(), key=lambda x: x[1]['accountName'])

        print("Select an account from the list below:")
        for i, (account_id, account_info) in enumerate(account_list, 1):
            print(f"{i}. {account_info['accountName']} (Account ID: {account_id})")

        account_index = int(input("[Required] Enter the number of the account to select: ")) - 1
        selected_account_id = account_list[account_index][0]

        roles = accounts[selected_account_id]['roles']
        sorted_roles = sorted(roles)

        print("Select a role from the list below:")
        for i, role in enumerate(sorted_roles, 1):
            print(f"{i}. {role}")

        role_index = int(input("[Required] Enter the number of the role to select: ")) - 1
        selected_role = sorted_roles[role_index]

        session = helper.get_sso_session(selected_account_id, selected_role)
    elif auth_method == '2':
        aws_access_key_id = input("[Required] Enter AWS Access Key ID: ")
        if not aws_access_key_id:
            raise ValueError("AWS Access Key ID is required.")
        aws_secret_access_key = input("[Required] Enter AWS Secret Access Key: ")
        if not aws_secret_access_key:
            raise ValueError("AWS Secret Access Key is required.")
        aws_session_token = input("[Optional] Enter AWS Session Token: ") or None

        session_kwargs = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,

        )
        if aws_session_token:
            session_kwargs['aws_session_token'] = aws_session_token

        session = boto3.Session(**session_kwargs)

    else:
        raise ValueError("Invalid authentication method selected.")

    s3_uri = input("[Required] Enter S3 URI (e.g., s3://bucket_name/.../region/): ").strip('/')
    if not s3_uri:
        raise ValueError("S3 URI is required.")
    if s3_uri.endswith('/'):
        s3_uri = s3_uri[:-1]
    validate_s3_uri(s3_uri)

    bucket, prefix = s3_uri.replace("s3://", "").split("/", 1)

    start_date = input("[Required] Enter start date (YYYY-MM-DD): ")
    if not start_date:
        raise ValueError("Start date is required.")
    validate_date(start_date)

    start_time = input("[Optional] Enter start time (HH:MM): ") or None
    if start_time:
        validate_time(start_time)

    end_date = input("[Optional] Enter end date (YYYY-MM-DD): ") or None
    if end_date:
        validate_date(end_date)

    end_time = input("[Optional] Enter end time (HH:MM): ") or None
    if end_time:
        validate_time(end_time)

    region_name = input("[Optional] Enter AWS region (default: ap-northeast-2): ") or 'ap-northeast-2'

    config = Config(
        region_name=region_name,
        retries={
            'max_attempts': 10,
            'mode': 'standard'
        },
        max_pool_connections=50
    )
    s3_client = session.client('s3', config=config)

    analyzer = ELBLogAnalyzer(
        s3_client=s3_client,
        bucket_name=bucket,
        prefix=prefix,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        region_name=region_name
    )

    try:
        script_start_time = datetime.now()
        gz_directory = analyzer.download_logs()
        log_directory = analyzer.decompress_logs(gz_directory)
        parsed_logs = analyzer.parse_logs(log_directory)
        if parsed_logs:
            analysis_data = analyzer.analyze_logs(parsed_logs)
            analyzer.save_to_excel(analysis_data, prefix, script_start_time)
        analyzer.clean_up([gz_directory, log_directory])
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        analyzer.clean_up(['do_not_delete/log', 'do_not_delete/parsed'])


if __name__ == '__main__':
    main()
