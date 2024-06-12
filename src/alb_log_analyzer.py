import concurrent.futures
import gzip
import logging
import os
import re
import shutil
from collections import defaultdict, Counter
from datetime import datetime

import pandas as pd
import pytz
from tqdm import tqdm

from src.utils import create_directory, clean_directory, download_abuseipdb

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


class ELBLogAnalyzer:
    def __init__(self, s3_client, bucket_name, prefix, start_datetime, end_datetime, timezone='UTC'):
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.prefix = prefix.strip('/')
        self.timezone = pytz.timezone(timezone)
        self.start_datetime = self.timezone.localize(datetime.strptime(start_datetime, '%Y-%m-%d %H:%M'))
        current_time = datetime.now(self.timezone)
        self.end_datetime = self.timezone.localize(
            datetime.strptime(end_datetime, '%Y-%m-%d %H:%M')) if end_datetime else current_time
        if self.end_datetime < self.start_datetime:
            self.end_datetime = current_time
        # UTC 변환
        self.start_datetime_utc = self.start_datetime.astimezone(pytz.utc)
        self.end_datetime_utc = self.end_datetime.astimezone(pytz.utc)

    def download_logs(self):
        gz_directory = create_directory('./data/log')
        clean_directory(gz_directory)  # Clear existing log files
        logger.info(f"Searching logs from S3 bucket from {self.start_datetime_utc} to {self.end_datetime_utc}...")

        paginator = self.s3_client.get_paginator('list_objects_v2')
        files_to_download = []

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
            if 'Contents' not in page:
                logger.warning(f"No logs found in the specified prefix: s3://{self.bucket_name}/{self.prefix}")
                continue
            for obj in page['Contents']:
                last_modified = obj['LastModified'].replace(tzinfo=pytz.utc)
                if self.start_datetime_utc <= last_modified <= self.end_datetime_utc:
                    files_to_download.append(obj['Key'])

        total_files = len(files_to_download)
        if total_files == 0:
            logger.warning(f"No logs found in the specified time range: {self.start_datetime} to {self.end_datetime}")
            return gz_directory

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._download_log_file, file_key, gz_directory) for file_key in
                       files_to_download]
            for future in tqdm(concurrent.futures.as_completed(futures), total=total_files, desc="Downloading",
                               unit="file", ncols=100,
                               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {percentage:3.0f}%"):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Exception during log download: {e}")

        logger.info("Download complete.")
        return gz_directory

    def _download_log_file(self, file_key, gz_directory):
        local_filename = os.path.join(gz_directory, os.path.basename(file_key))
        try:
            self.s3_client.download_file(self.bucket_name, file_key, local_filename)
        except self.s3_client.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '403':
                logger.error(f"Download failed for s3://{self.bucket_name}/{file_key}. Check permissions. Reason: {e}")
            else:
                logger.error(f"Download failed for s3://{self.bucket_name}/{file_key}. Reason: {e}")

    def decompress_logs(self, gz_directory):
        log_directory = create_directory('./data/parsed')
        clean_directory(log_directory)
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
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(log_files), desc="Parsing",
                               unit="file", ncols=100,
                               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {percentage:3.0f}%"):
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

        request_parts = re.match(r'(?P<method>\S+)\s+(?P<url>\S+)\s+(?P<version>\S+)', data['request'])
        if not request_parts:
            logger.warning(f"Invalid request format: {data['request']}")
            return None

        url = request_parts.group('url')

        request_processing_time = self._parse_time_field(data['request_processing_time'])
        target_processing_time = self._parse_time_field(data['target_processing_time'])
        response_processing_time = self._parse_time_field(data['response_processing_time'])

        if None in [request_processing_time, target_processing_time, response_processing_time]:
            return None

        total_response_time = request_processing_time + target_processing_time + response_processing_time
        timestamp = self._convert_to_timezone(self._parse_timestamp(data['timestamp']))

        if data['user_agent'] == '-':
            return None

        return {
            'timestamp': self._remove_timezone(timestamp),
            'client_ip': data['client_ip'].split(':')[0],
            'target_ip': data['target_ip'].split(':')[0] if data['target_ip'] != '-' else None,
            'request_processing_time': request_processing_time,
            'target_processing_time': target_processing_time,
            'response_processing_time': response_processing_time,
            'elb_status_code': data['elb_status_code'],
            'target_status_code': data['target_status_code'],
            'received_bytes': data['received_bytes'],
            'sent_bytes': data['sent_bytes'],
            'request': url,  # Only store the URL part
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

    def _convert_to_timezone(self, timestamp):
        return timestamp.astimezone(self.timezone)

    def _remove_timezone(self, timestamp):
        return timestamp.replace(tzinfo=None)

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
        abuse_ip_set = download_abuseipdb()
        top_user_agents = user_agent_counter.most_common(100)

        return {
            'Top 100 Client IP': self._create_top_client_ips_dataframe(top_client_ips, abuse_ip_set),
            'Top 100 User Agents': self._create_top_user_agents_dataframe(top_user_agents),
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
            'Top 100 Total time': self._create_long_response_times_dataframe(long_response_times)
        }

    def _categorize_log_entry(self, log, elb_2xx_counts, elb_3xx_counts, elb_4xx_counts, elb_5xx_counts,
                              target_4xx_counts, target_5xx_counts, long_response_times):
        if log['elb_status_code'].startswith('2'):
            elb_2xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code'])] += 1
        elif log['elb_status_code'].startswith('3'):
            elb_3xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['redirect_url'],
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
                log['target_status_code'])] += 1
        elif log['target_status_code'].startswith('5'):
            target_5xx_counts[(
                log['timestamp'], log['client_ip'], log['target_ip'], log['request'], log['elb_status_code'],
                log['target_status_code'])] += 1

        if log['total_response_time'] >= 1.0:
            long_response_times.append(log)

    def _create_status_code_dataframe(self, status_code_counts):
        df = pd.DataFrame(
            [(val, key[1], key[3], key[4], key[5]) for key, val in status_code_counts.items()],
            columns=['Count', 'Client IP', 'Request', 'ELB Status Code', 'Backend Status Code']
        )
        grouped_df = df.groupby(['Client IP', 'Request', 'ELB Status Code', 'Backend Status Code']).sum().reset_index()
        sorted_df = grouped_df.sort_values('Count', ascending=False)
        columns = ['Count'] + [col for col in sorted_df.columns if col != 'Count']
        sorted_df = sorted_df[columns]
        return sorted_df

    def _create_3xx_status_code_dataframe(self, status_3xx_code_counts):
        df = pd.DataFrame(
            [(val, key[1], key[3], key[4], key[5], key[6]) for key, val in status_3xx_code_counts.items()],
            columns=['Count', 'Client IP', 'Request', 'Redirect URL', 'ELB Status Code', 'Backend Status Code']
        )
        grouped_df = df.groupby(
            ['Client IP', 'Request', 'Redirect URL', 'ELB Status Code', 'Backend Status Code']).sum().reset_index()
        sorted_df = grouped_df.sort_values('Count', ascending=False)
        columns = ['Count'] + [col for col in sorted_df.columns if col != 'Count']
        sorted_df = sorted_df[columns]
        return sorted_df

    def _create_timestamp_dataframe(self, status_code_counts):
        df = pd.DataFrame(
            [(key[0], key[1], key[3], key[4], key[5]) for key, val in status_code_counts.items()],
            columns=['Timestamp', 'Client IP', 'Request URL', 'ELB Status Code', 'Backend Status Code']
        ).sort_values('Timestamp')
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize(None)  # Timezone 제거(UTC -> Local)
        return df[['Timestamp', 'Client IP', 'Request URL', 'ELB Status Code', 'Backend Status Code']]

    def _create_long_response_times_dataframe(self, long_response_times):
        df = pd.DataFrame(long_response_times)
        df.sort_values(by='total_response_time', ascending=False, inplace=True)
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        return df.head(100)[['total_response_time', 'timestamp', 'client_ip', 'target_ip', 'request']]

    def _create_top_client_ips_dataframe(self, top_client_ips, abuse_ip_set):
        df = pd.DataFrame(top_client_ips, columns=['Client IP', 'Count'])
        df['Abuse'] = df['Client IP'].apply(lambda ip: 'Yes' if ip in abuse_ip_set else 'No')
        return df[['Count', 'Client IP', 'Abuse']]

    def _create_top_user_agents_dataframe(self, top_user_agents):
        df = pd.DataFrame(top_user_agents, columns=['User Agent', 'Count'])
        return df[['Count', 'User Agent']]

    def save_to_excel(self, data, prefix, script_start_time):
        timestamp = script_start_time.strftime('%Y%m%d_%H%M%S')
        output_directory = create_directory(f'./data/output/{timestamp}')
        output_path = os.path.join(output_directory, f'{prefix.replace("/", "_")}_report.xlsx')

        max_rows_per_sheet = 1048576
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            workbook.strings_to_urls = False  # URL 변환 방지

            cell_format = workbook.add_format({'text_wrap': True})  # 텍스트 줄 바꿈

            for sheet_name, df in data.items():
                if df.shape[0] > max_rows_per_sheet:
                    df = df.iloc[:max_rows_per_sheet]
                    logger.warning(
                        f"Data for sheet '{sheet_name}' exceeds {max_rows_per_sheet} rows and has been truncated.")

                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

                # 자동 열 너비 조정
                for column in df:
                    column_length = max(df[column].astype(str).map(len).max(), len(column))
                    col_idx = df.columns.get_loc(column)
                    writer.sheets[sheet_name].set_column(col_idx, col_idx, column_length, cell_format)

        logger.info(f"Report saved to {output_path}")

    def clean_up(self, directories):
        for directory in directories:
            clean_directory(directory)
