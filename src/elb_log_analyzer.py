import concurrent.futures
import gzip
import logging
import os
import re
import shutil
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import pandas as pd
import pytz
from tqdm import tqdm

from src.utils import create_directory, clean_directory, parse_time, get_timezone_for_region, REGION_TIMEZONE_MAP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


class ELBLogAnalyzer:
    def __init__(self, s3_client, bucket_name, prefix, start_date, end_date, start_time=None, end_time=None,
                 region_name='ap-northeast-2'):
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.prefix = prefix.strip('/')
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=pytz.utc)
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').replace(
            tzinfo=pytz.utc) if end_date else self.start_date
        self.start_time = parse_time(start_time)
        self.end_time = parse_time(end_time)
        self.timezone = get_timezone_for_region(region_name, REGION_TIMEZONE_MAP)

    def download_logs(self):
        gz_directory = create_directory('data/logs')
        clean_directory(gz_directory)  # Clear existing log files
        logger.info("Downloading logs from S3 bucket...")

        start_datetime = datetime.combine(self.start_date, self.start_time).replace(
            tzinfo=pytz.utc) if self.start_time else self.start_date
        end_datetime = datetime.combine(self.end_date, self.end_time).replace(
            tzinfo=pytz.utc) if self.end_time else self.end_date + timedelta(days=1)

        paginator = self.s3_client.get_paginator('list_objects_v2')
        files_to_download = []

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
            if 'Contents' not in page:
                logger.warning(f"No logs found in the specified prefix: s3://{self.bucket_name}/{self.prefix}")
                continue
            for obj in page['Contents']:
                if start_datetime <= obj['LastModified'] <= end_datetime:
                    files_to_download.append(obj['Key'])

        total_files = len(files_to_download)
        if total_files == 0:
            logger.warning(f"No logs found in the specified time range: {start_datetime} to {end_datetime}")
            return gz_directory

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._download_log_file, file_key, gz_directory) for file_key in
                       files_to_download]
            for future in tqdm(concurrent.futures.as_completed(futures), total=total_files, desc="Downloading",
                               unit="file", ncols=100,
                               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {percentage:3.0f}%"):
                future.result()  # Catch exceptions

        logger.info("Download complete.")
        return gz_directory

    def _download_log_file(self, file_key, gz_directory):
        local_filename = os.path.join(gz_directory, os.path.basename(file_key))
        create_directory(gz_directory)  # Ensure directory exists
        try:
            self.s3_client.download_file(self.bucket_name, file_key, local_filename)
        except self.s3_client.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '403':
                logger.error(f"Download failed for s3://{self.bucket_name}/{file_key}. Check permissions. Reason: {e}")
            else:
                logger.error(f"Download failed for s3://{self.bucket_name}/{file_key}. Reason: {e}")

    def decompress_logs(self, gz_directory):
        log_directory = create_directory('data/parsed')
        clean_directory(log_directory)  # Clear existing parsed files
        logger.info("Decompressing log files...")

        gz_files = [f for f in os.listdir(gz_directory) if f.endswith('.gz')]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            list(tqdm(executor.map(self._decompress_log_file, gz_files, [gz_directory] * len(gz_files),
                                   [log_directory] * len(gz_files)), total=len(gz_files), desc="Decompressing",
                      unit="file", ncols=100, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {percentage:3.0f}%"))

        logger.info("Decompression complete.")
        return log_directory

    def _decompress_log_file(self, gz_file, gz_directory, log_directory):
        gz_file_path = os.path.join(gz_directory, gz_file)
        log_file_path = os.path.join(log_directory, gz_file[:-3] + '.log')
        create_directory(log_directory)  # Ensure directory exists
        try:
            with gzip.open(gz_file_path, 'rb') as f_in:
                with open(log_file_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except Exception as e:
            logger.error(f"Failed to decompress {gz_file}. Reason: {e}")

    def parse_logs(self, log_directory):
        logger.info("Parsing log files...")
        parsed_logs = []
        log_files = [f for f in os.listdir(log_directory) if f.endswith('.log')]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._parse_log_file, log_file, log_directory) for log_file in log_files]
            for future in concurrent.futures.as_completed(futures):
                parsed_logs.extend(future.result())

        logger.info(f"Parsed {len(parsed_logs)} log entries.")
        return parsed_logs

    def _parse_log_file(self, log_file, log_directory):
        parsed_logs = []
        log_file_path = os.path.join(log_directory, log_file)
        with open(log_file_path, 'r') as file:
            for line in file:
                parsed_log_entry = self._parse_log_line(line)
                if parsed_log_entry:
                    parsed_logs.append(parsed_log_entry)
        return parsed_logs

    def _parse_log_line(self, line):
        pattern = re.compile(
            r'(?P<type>[^ ]+) (?P<timestamp>[^ ]+) (?P<elb>[^ ]+) (?P<client_ip>[^ ]+) (?P<target_ip>[^ ]+) (?P<request_processing_time>[^ ]+) (?P<target_processing_time>[^ ]+) (?P<response_processing_time>[^ ]+) (?P<elb_status_code>[^ ]+) (?P<target_status_code>[^ ]+) (?P<received_bytes>[^ ]+) (?P<sent_bytes>[^ ]+) "(?P<request>[^"]+)" "(?P<user_agent>[^"]+)" (?P<ssl_cipher>[^ ]+) (?P<ssl_protocol>[^ ]+) (?P<target_group_arn>[^ ]+) "(?P<trace_id>[^"]*)" "(?P<domain_name>[^"]*)" "(?P<chosen_cert_arn>[^"]*)" (?P<matched_rule_priority>[^ ]+) (?P<request_creation_time>[^ ]+) "(?P<actions_executed>[^"]*)" "(?P<redirect_url>[^"]*)" "(?P<error_reason>[^"]*)" "(?P<target_port_list>[^"]*)" "(?P<target_status_code_list>[^"]*)" "(?P<classification>[^"]*)" "(?P<classification_reason>[^"]*)" (?P<conn_trace_id>[^ ]+)'
        )

        match = pattern.match(line)
        if not match:
            logger.warning(f"Invalid log format: {line}")
            return None

        data = match.groupdict()

        request_processing_time = self._parse_time_field(data['request_processing_time'])
        target_processing_time = self._parse_time_field(data['target_processing_time'])
        response_processing_time = self._parse_time_field(data['response_processing_time'])

        if None in [request_processing_time, target_processing_time, response_processing_time]:
            return None

        total_response_time = request_processing_time + target_processing_time + response_processing_time
        timestamp = self._convert_to_kst(self._parse_timestamp(data['timestamp']))

        if self.start_time and self.end_time:
            if not self._is_within_time_range(timestamp):
                return None

        if data['user_agent'] == '-':
            return None

        return {
            'timestamp': timestamp,
            'client_ip': data['client_ip'].split(':')[0],
            'target_ip': data['target_ip'].split(':')[0] if data['target_ip'] != '-' else None,
            'request_processing_time': request_processing_time,
            'target_processing_time': target_processing_time,
            'response_processing_time': response_processing_time,
            'elb_status_code': data['elb_status_code'],
            'target_status_code': data['target_status_code'],
            'received_bytes': data['received_bytes'],
            'sent_bytes': data['sent_bytes'],
            'request': data['request'],
            'total_response_time': total_response_time,
            'user_agent': data['user_agent'],
            'ssl_cipher': data['ssl_cipher'],
            'ssl_protocol': data['ssl_protocol'],
            'target_group_arn': data['target_group_arn'],
            'trace_id': data['trace_id'],
            'domain_name': data['domain_name'],
            'chosen_cert_arn': data['chosen_cert_arn'],
            'matched_rule_priority': data['matched_rule_priority'],
            'request_creation_time': data['request_creation_time'],
            'actions_executed': data['actions_executed'],
            'redirect_url': data['redirect_url'],
            'error_reason': data['error_reason'],
            'target_port_list': data['target_port_list'],
            'target_status_code_list': data['target_status_code_list'],
            'classification': data['classification'],
            'classification_reason': data['classification_reason'],
            'conn_trace_id': data['conn_trace_id']
        }

    def _parse_time_field(self, time_field):
        try:
            return float(time_field) if time_field != '-' else 0
        except ValueError:
            logger.warning(f"Invalid time field: {time_field}")
            return None

    def _parse_timestamp(self, timestamp_str):
        return datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)

    def _convert_to_kst(self, timestamp):
        if self.timezone.zone == 'Asia/Seoul':
            return timestamp.astimezone(pytz.timezone('Asia/Seoul'))
        return timestamp

    def _is_within_time_range(self, timestamp):
        start_datetime = datetime.combine(self.start_date, self.start_time).replace(
            tzinfo=pytz.utc) if self.start_time else datetime.min.replace(tzinfo=pytz.utc)
        end_datetime = datetime.combine(self.end_date, self.end_time).replace(
            tzinfo=pytz.utc) if self.end_time else datetime.max.replace(tzinfo=pytz.utc)
        return start_datetime <= timestamp <= end_datetime

    def analyze_logs(self, parsed_logs):
        elb_2xx_counts = defaultdict(int)
        elb_3xx_counts = defaultdict(int)
        elb_4xx_counts = defaultdict(int)
        elb_5xx_counts = defaultdict(int)
        target_4xx_counts = defaultdict(int)
        target_5xx_counts = defaultdict(int)
        long_response_times = []
        client_ip_counter = Counter()
        user_agent_counter = Counter()

        for log in parsed_logs:
            self._categorize_log_entry(log, elb_2xx_counts, elb_3xx_counts, elb_4xx_counts, elb_5xx_counts,
                                       target_4xx_counts, target_5xx_counts, long_response_times)
            client_ip_counter[log['client_ip']] += 1
            user_agent_counter[log['user_agent']] += 1

        top_client_ips = client_ip_counter.most_common(100)
        top_user_agents = user_agent_counter.most_common(100)

        return {
            'ELB 2xx Count': self._create_status_code_dataframe(elb_2xx_counts),
            'ELB 3xx Count': self._create_3xx_status_code_dataframe(elb_3xx_counts),
            'ELB 4xx Count': self._create_status_code_dataframe(elb_4xx_counts),
            'ELB 5xx Count': self._create_status_code_dataframe(elb_5xx_counts),
            'Backend 4xx Count': self._create_status_code_dataframe(target_4xx_counts),
            'Backend 5xx Count': self._create_status_code_dataframe(target_5xx_counts),
            'ELB 4xx Timestamp': self._create_timestamp_dataframe(elb_4xx_counts),
            'ELB 5xx Timestamp': self._create_timestamp_dataframe(elb_5xx_counts),
            'Backend 4xx Timestamp': self._create_timestamp_dataframe(target_4xx_counts),
            'Backend 5xx Timestamp': self._create_timestamp_dataframe(target_5xx_counts),
            'Top 100 Total time': self._create_long_response_times_dataframe(long_response_times),
            'Top 100 Client IP': self._create_top_client_ips_dataframe(top_client_ips),
            'Top 100 User Agents': self._create_top_user_agents_dataframe(top_user_agents)
        }

    def _categorize_log_entry(self, log, elb_2xx_counts, elb_3xx_counts, elb_4xx_counts, elb_5xx_counts,
                              target_4xx_counts, target_5xx_counts, long_response_times):
        if log['elb_status_code'].startswith('2'):
            elb_2xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code'])] += 1
        elif log['elb_status_code'].startswith('3'):
            elb_3xx_counts[(log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['redirect_url'],
                            log['elb_status_code'], log['target_status_code'])] += 1
        elif log['elb_status_code'].startswith('4'):
            elb_4xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code'])] += 1
        elif log['elb_status_code'].startswith('5'):
            elb_5xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code'])] += 1

        if log['target_status_code'].startswith('4'):
            target_4xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code_list'])] += 1
        elif log['target_status_code'].startswith('5'):
            target_5xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code_list'])] += 1

        if log['total_response_time'] >= 1.0:
            long_response_times.append(log)

    def _create_status_code_dataframe(self, status_code_counts):
        df = pd.DataFrame(
            [(val, key[1], key[3], key[4], key[5]) for key, val in status_code_counts.items()],
            columns=['Count', 'Client IP', 'Request', 'ELB Status Code', 'Backend Status Code']
        ).sort_values('Count', ascending=False)
        return df

    def _create_3xx_status_code_dataframe(self, status_code_counts):
        df = pd.DataFrame(
            [(val, key[1], key[3], key[4], key[5], key[6]) for key, val in status_code_counts.items()],
            columns=['Count', 'Client IP', 'Request', 'ELB Status Code', 'Backend Status Code']
        ).sort_values('Count', ascending=False)
        return df

    def _create_timestamp_dataframe(self, status_code_counts):
        df = pd.DataFrame(
            [(key[0], key[1], key[2], key[3], key[4], key[5], val) for key, val in status_code_counts.items()],
            columns=['Timestamp', 'Client IP', 'Target IP', 'Request URL', 'ELB Status Code', 'Backend Status Code',
                     'Count']
        ).sort_values('Timestamp')
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize(None)  # Make datetimes timezone-unaware
        return df[['Timestamp', 'Client IP', 'Target IP', 'Request URL', 'ELB Status Code', 'Backend Status Code']]

    def _create_long_response_times_dataframe(self, long_response_times):
        df = pd.DataFrame(long_response_times)
        df.sort_values(by='total_response_time', ascending=False, inplace=True)
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)  # Make datetimes timezone-unaware
        return df.head(100)[['total_response_time', 'timestamp', 'client_ip', 'target_ip', 'request']]

    def _create_top_client_ips_dataframe(self, top_client_ips):
        df = pd.DataFrame(top_client_ips, columns=['Client IP', 'Count'])
        return df

    def _create_top_user_agents_dataframe(self, top_user_agents):
        df = pd.DataFrame(top_user_agents, columns=['User Agent', 'Count'])
        return df

    def save_to_excel(self, analysis_data, prefix, start_datetime):
        output_file = self._create_output_filename(prefix, start_datetime)
        if os.path.exists(output_file):
            logger.warning(f"{output_file} already exists. It will be overwritten.")
        with pd.ExcelWriter(output_file) as writer:
            for sheet_name, df in analysis_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        logger.info(f"Analysis results saved to {output_file}.")
        print(f"Analysis results saved to {output_file}.")

    def _create_output_filename(self, prefix, start_datetime):
        current_directory = os.getcwd()
        directory = os.path.join(current_directory, "reports", "ELBLogAnalysis",
                                 start_datetime.strftime('%Y%m%d_%H%M%S'))
        create_directory(directory)
        filename = f"{prefix.replace('/', '_')}_{start_datetime.strftime('%Y%m%d_%H%M%S')}.xlsx"
        return os.path.join(directory, filename)

    def clean_up(self, directories):
        logger.info("Cleaning up temporary files...")
        for directory in directories:
            if 'report' not in directory:  # Skip the report directory
                clean_directory(directory)
        logger.info("Cleanup complete.")
