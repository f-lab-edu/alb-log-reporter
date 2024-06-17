# AWS ALB Log Reporter

이 도구는 CLI 형태로 제공되며, AWS Application Load Balancer(ALB) 로그를 S3 버킷에서 다운로드하고, 압축을 해제하고, 파싱하여 분석한 후, 분석 결과를 Excel 파일로 저장합니다.

## 기능

- S3 버킷에서 ELB 로그 다운로드
- 로그 압축 해제 및 파싱
- 상태 코드 및 응답 시간을 포함한 로그 데이터 분석
- 분석 결과를 Excel 보고서로 생성
- AWS SSO 프로파일 및 표준 AWS 자격 증명 지원

## 요구 사항

- Python 3.6+

### 필요한 Python 패키지:

- boto3
- pandas
- openpyxl
- xlsxwriter
- pytz
- tqdm
- prettytable
- requests

필요한 패키지를 설치하려면 다음 명령을 사용하세요:

```sh
pip install -r requirements.txt
```

## 사용 방법

```text
usage: main.py [-h] [-p PROFILE] -t {access_key,sso-session} -b BUCKET -s START [-e END] [-z TIMEZONE]

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

options:
  -h, --help            show this help message and exit
  -p PROFILE, --profile PROFILE
                        AWS profile name (default: default)
  -t {access_key,sso-session}, --profile-type {access_key,sso-session}
                        The type of AWS profile to use: "sso-session" for SSO session profiles, or "access_key" for access key profiles.
  -b BUCKET, --bucket BUCKET
                        S3 URI of the ELB logs, e.g., s3://{your-bucket-name}/AWSLogs/{account_id}/elasticloadbalancing/{region}/
  -s START, --start START
                        Start datetime in YYYY-MM-DD HH:MM format
  -e END, --end END     End datetime in YYYY-MM-DD HH:MM format (default: now)
  -z TIMEZONE, --timezone TIMEZONE
                        Timezone for log timestamps (default: UTC)

```

### 명령어 옵션

- `-p, --profile`: (선택) AWS 프로파일 이름 (기본값: `default`)
  - SSO 세션을 사용할 경우: `aws configure sso-session` 명령어로 설정하거나, `~/.aws/config` 파일에 SSO 세션 정보를 입력하세요.
    - 아래 AWS SSO Profile 설정 예제 참조
  - 액세스 키를 사용할 경우: `~/.aws/credentials` 파일에 access key와 secret key를 설정하세요.
    - 아래 Standard AWS Credentials Profile 설정 예제 참조
- `-t, --profile-type`: (필수) AWS profile 타입, 선택 값: `access_key`, `sso-session`
  - `access_key`: 액세스 키를 사용하는 경우
  - `sso-session`: SSO 세션 프로파일을 사용하는 경우
- `-b, --bucket`: (필수) ALB 로그가 저장된 S3 폴더 경로
  - 로그 경로는 `s3://{your-bucket-name}/AWSLogs/{account_id}/elasticloadbalancing/{region}/{year}/{month}/{day}/`입니다.
- `-s, --start`: (필수) 시작 날짜 및 시간 `YYYY-MM-DD HH:MM` 형식
  - 예: "2024-06-01 00:00"
- `-e, --end`: (선택) 종료 날짜 및 시간 `YYYY-MM-DD HH:MM` 형식 (기본값: 현재 시간)
  - 예: "2024-06-07 23:59"
- `-z, --timezone`: (선택) 보고서 생성 시 사용할 타임존 (기본값: `UTC`)
  - 예: `Asia/Seoul`, `America/New_York`, `Europe/London`

### 예시

다음은 핵심 예시 3개와 각 예시의 설명입니다.

#### 예시 1: sso-session 프로필 사용

```sh
python main.py -t sso-session -b s3://my-bucket/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/ -s "2024-06-01 00:00" -e "2024-06-07 23:59" -z "Asia/Seoul"
```

**설명:**
- **프로필 유형(-t)**: `sso-session`으로 설정하여 SSO 세션 프로필을 사용
- **S3 버킷 경로(-b)**: `s3://my-bucket/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/` 경로의 로그를 분석
- **시작 시간(-s)**: 로그 분석의 시작 시간은 `2024-06-01 00:00`
- **종료 시간(-e)**: 로그 분석의 종료 시간은 `2024-06-07 23:59`
- **시간대(-z)**: `Asia/Seoul` 시간대로 설정

#### 예시 2: access key 프로필 사용

```sh
python main.py -t access_key -b s3://another-bucket/AWSLogs/987654321098/elasticloadbalancing/us-west-1/ -s "2024-05-15 00:00" -e "2024-05-21 23:59"
```

**설명:**
- **프로필 유형(-t)**: `access_key`로 설정하여 액세스 키 프로필을 사용
- **S3 버킷 경로(-b)**: `s3://another-bucket/AWSLogs/987654321098/elasticloadbalancing/us-west-1/` 경로의 로그를 분석
- **시작 시간(-s)**: 로그 분석의 시작 시간은 `2024-05-15 00:00`
- **종료 시간(-e)**: 로그 분석의 종료 시간은 `2024-05-21 23:59`
- **시간대(-z)**: 기본값인 `UTC`를 사용하므로 옵션을 생략

#### 예시 3: 특정 프로필과 시간대를 사용

```sh
python main.py -p production -t sso-session -b s3://logs-bucket/AWSLogs/111111111111/elasticloadbalancing/eu-central-1/ -s "2024-04-01 00:00" -e "2024-04-07 23:59" -z "Europe/Berlin"
```

**설명:**
- **프로필 이름(-p)**: `production` 프로필을 사용
- **프로필 유형(-t)**: `sso-session`으로 설정하여 SSO 세션 프로필을 사용
- **S3 버킷 경로(-b)**: `s3://logs-bucket/AWSLogs/111111111111/elasticloadbalancing/eu-central-1/` 경로의 로그를 분석
- **시작 시간(-s)**: 로그 분석의 시작 시간은 `2024-04-01 00:00`
- **종료 시간(-e)**: 로그 분석의 종료 시간은 `2024-04-07 23:59`
- **시간대(-z)**: `Europe/Berlin` 시간대로 설정

### AWS SSO Profile 설정 예제

다음은 AWS SSO 프로파일을 설정하기 위한 `~/.aws/config` 파일의 예제입니다:
`aws configure sso` 명령을 사용하여 설정할 수도 있습니다.

```ini
[sso-session example1]
sso_start_url = https://example1.awsapps.com/start/#/
sso_region = ap-northeast-2
sso_registration_scopes =

 sso:account:access

[profile readonly-sso-role-117630110551]
sso_start_url = https://example1.awsapps.com/start/#/
sso_session = eunch
sso_account_id = 123456789012
sso_role_name = readonly-sso-role
sso_region = ap-northeast-2
```

### Standard AWS Credentials Profile 설정 예제

다음은 표준 AWS 자격 증명을 설정하기 위한 `~/.aws/credentials` 파일의 예제입니다:
`aws configure` 명령을 사용하여 설정할 수도 있습니다.

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[my-aws-profile]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[my-another-profile]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR SECRET_ACCESS_KEY
aws_session_token = YOUR_SESSION_TOKEN
```

Region을 설정하려면 `~/.aws/config` 파일에 다음과 같이 추가하세요:

```ini
[default]
region = ap-northeast-2
```

### 추가 자료

- [AWS CLI SSO 프로파일 구성 가이드](https://docs.aws.amazon.com/cli/latest/userguide/sso-configure-profile-token.html#sso-configure-profile-token-auto-sso-session)
- [AWS CLI 인증 사용자 가이드](https://docs.aws.amazon.com/cli/latest/userguide/cli-authentication-user.html#cli-authentication-user-configure.title)

## 제공하는 보고서 양식

보고서는 다음과 같은 필드를 포함하여 Excel 형식으로 제공됩니다:

### 보고서 예시

1. **Top 100 Client IP**: 가장 많이 요청을 보낸 상위 100개의 클라이언트 IP와 Abuse 여부 표시
    - Count | Client IP | Abuse
    - Abuse IP DB 출처: [AbuseIPDB](https://raw.githubusercontent.com/borestad/blocklist-abuseipdb/main/abuseipdb-s100-30d.ipv4)
    - Abuse IP와 Client IP를 매칭시켜 abuse IP 여부를 확인합니다. Abuse IP는 신고일 기준 30일 이내의 목록이며, 매일 두 번 업데이트됩니다. Abuse IP는 모든 시트에 강조 처리되어 공격성 여부를 판단할 수 있는 지표로 제공됩니다.
2. **Top 100 Request URL**: 가장 많이 요청된 상위 100개의 URL
    - Count | Request URL
3. **Top 100 User Agents**: 가장 많이 사용된 상위 100개의 사용자 에이전트
    - Count | User Agent
4. **Top 100 Response Time**: 응답 시간이 가장 긴 상위 100개의 요청
    - Response time | Timestamp | Client IP | Target IP | Request | ELB Status Code | Backend Status Code
    - 1초 이상의 응답 시간을 가진 요청을 표시
5. **ELB 2xx Count**: ELB 2xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | ELB Status Code | Backend Status Code
6. **ELB 3xx Count**: ELB 3xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | Redirect URL | ELB Status Code | Backend Status Code
7. **ELB 4xx Count**: ELB 4xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | ELB Status Code | Backend Status Code
8. **ELB 4xx Timestamp**: ELB 4xx 상태 코드를 반환한 요청의 타임스탬프
    - Timestamp | Client IP | Target IP | Request | ELB Status Code | Backend Status Code
9. **ELB 5xx Count**: ELB 5xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | ELB Status Code | Backend Status Code
10. **ELB 5xx Timestamp**: ELB 5xx 상태 코드를 반환한 요청의 타임스탬프
    - Timestamp | Client IP | Target IP | Request | ELB Status Code | Backend Status Code
11. **Backend 4xx Count**: Backend 4xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | ELB Status Code | Backend Status Code
12. **Backend 4xx Timestamp**: Backend 4xx 상태 코드를 반환한 요청의 타임스탬프
    - Timestamp | Client IP | Target IP | Request | ELB Status Code | Backend Status Code
13. **Backend 5xx Count**: Backend 5xx 상태 코드를 반환한 요청 수
    - Count | Client IP | Request | ELB Status Code | Backend Status Code
14. **Backend 5xx Timestamp**: Backend 5xx 상태 코드를 반환한 요청의 타임스탬프
    - Timestamp | Client IP | Target IP | Request | ELB Status Code | Backend Status Code

## 데이터 디렉토리 구조

로그 파일과 보고서 파일은 다음과 같은 디렉토리 구조에 저장됩니다:

- `./data/log`: 다운로드된 원본 로그 파일 (.gz 형식)
- `./data/parsed`: 압축 해제된 로그 파일 (.log 형식)
- `./data/output/{timestamp}`: 생성된 Excel 보고서 파일 (.xlsx 형식)

## 참고 사항

- `xlsxwriter` 모듈의 제한 사항으로 보고서는 최대 1,048,576 행까지 표시되며, 초과되는 데이터는 추가 시트에 저장됩니다.
- 보고서 생성 시간은 로그 파일 크기에 따라 달라집니다. 100만 라인 기준 전체 실행 시간은 평균 약 2분 내외입니다.