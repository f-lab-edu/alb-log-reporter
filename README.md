# AWS ALB Log Report Tool

## Overview

The AWS ALB Log Report Tool is a command-line utility designed to parse and analyze AWS Application Load Balancer (ALB) logs. It provides quick and detailed insights into request statistics, making it a valuable tool for cloud operations teams and users who need to analyze high volumes of requests or perform quick analyses during DDoS attacks.

## Features

- **Flexible Authentication**: Supports AWS SSO, AWS Access Keys, and AWS Profiles.
- **Efficient Log Handling**: Downloads, decompresses, parses, and analyzes ALB logs from an S3 bucket.
- **Comprehensive Reports**: Generates detailed reports including status codes, response times, and top client IPs.
- **User-Friendly**: Provides clear instructions and prompts for each step.

## Requirements

- Python 3.6 or higher
- Python packages: `boto3`, `botocore`, `pandas`, `pytz`, `tqdm`, `tabulate`

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Palaoom/aws-alb-log-reporter.git
    cd aws-alb-log-reporter
    ```

2. Install required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Run the script:
    ```bash
    python alb-log-reporter.py
    ```

2. Follow the prompts to select the authentication method, provide necessary credentials or profile information, and enter the S3 bucket URI and date/time range for the logs to analyze.

## Report Information

The tool generates an Excel report with multiple sheets, each providing detailed insights into different aspects of your ALB logs. The sheets include:

- **ELB 4xx Status Code**: Lists all the 4xx status codes returned by the ELB.
- **ELB 5xx Status Code**: Lists all the 5xx status codes returned by the ELB.
- **Backend 4xx Status Code**: Lists all the 4xx status codes returned by the backend servers.
- **Backend 5xx Status Code**: Lists all the 5xx status codes returned by the backend servers.
- **Top 100 Total Time**: Lists the top 100 log entries with the longest total response times.
- **Top 100 Client IP**: Lists the top 100 client IPs by the number of requests made.

## AWS SSO Helper

The `aws_sso_helper.py` script simplifies obtaining and managing temporary AWS credentials via AWS Single Sign-On (SSO). It handles token caching, token refresh, and guides the user through the device authorization process for AWS SSO.