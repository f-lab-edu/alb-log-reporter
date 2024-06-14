# AWS ELB Log Reporter

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

필요한 패키지를 설치하려면 다음 명령을 사용하세요:

```sh
pip install -r requirements.txt
```

## 사용 방법

```text
python main.py --help
usage: main.py [-h] [-p PROFILE] -b BUCKET -s START [-e END] [-z TIMEZONE]

  ____  _      ____       _       ___    ____      ____     ___  ____   ___   ____  ______    ___  ____  
 /    || |    |    \     | |     /   \  /    |    |    \   /  _]|    \ /   \ |    \|      |  /  _]|    \ 
|  o  || |    |  o  )    | |    |     ||   __|    |  D  ) /  [_ |  o  )     ||  D  )      | /  [_ |  D  )
|     || |___ |     |    | |___ |  O  ||  |  |    |    / |    _]|   _/|  O  ||    /|_|  |_||    _]|    / 
|  _  ||     ||  O  |    |     ||     ||  |_ |    |    \ |   [_ |  |  |     ||    \  |  |  |   [_ |    \ 
|  |  ||     ||     |    |     ||     ||     |    |  .  \|     ||  |  |     ||  .  \ |  |  |     ||  .  \ 
|__|__||_____||_____|    |_____| \___/ |___,_|    |__|\_||_____||__|   \___/ |__|\_| |__|  |_____||__|\_|

AWS ALB Log Reporter

This tool automates the analysis of AWS Application Load Balancer (ALB) logs 
by downloading, decompressing, parsing, and generating a detailed report.

Usage:
python main.py -p PROFILE_NAME -b S3_URI -s "START_DATETIME" -e "END_DATETIME" -z "TIMEZONE"

Options:
  -h, --help              Show this help message and exit
  -p, --profile  PROFILE  AWS profile name (default: default)
  -b, --bucket   BUCKET   S3 URI of the ELB logs, e.g., s3://{your-bucket-name}/prefix
  -s, --start    START    Start datetime in YYYY-MM-DD HH:MM format
  -e, --end      END      End datetime in YYYY-MM-DD HH:MM format (default: now)
  -z, --timezone TIMEZONE Timezone for log timestamps (default: UTC)
```

### 명령어 옵션

- `-p, --profile`: (선택) AWS 프로파일 이름 (기본값: `default`)
    - SSO 세션을 사용할 경우: SSO 프로파일을 설정하고 `~/.aws/config` 파일에 SSO 세션 정보를 포함하세요.
        - 아래 AWS SSO Profile 설정 예제 참조
        - SSO Session name만 입력하면 해당 세션을 사용합니다. ex) -p example1
    - 액세스 키를 사용할 경우: `~/.aws/credentials` 파일에 액세스 키와 시크릿 키를 설정하세요.
        - 아래 Standard AWS Credentials Profile 설정 예제 참조
- `-b, --s3-uri`: (필수) ELB 로그의 S3 URI, 예: `s3://your-bucket-name/prefix`
    - 기본 ALB 로그 저장 경로는 `s3://{your-bucket-name}/AWSLogs/{account_id}/elasticloadbalancing/{region}/{year}/{month}/{day}/`입니다.
      여기서 `{region}`까지 복사하여 사용하세요.
- `-s, --start`: (필수) 시작 날짜 및 시간 `YYYY-MM-DD HH:MM` 형식 (기본값: 현재 UTC 시간)
    - ex) "2023-06-01 00:00"
- `-e, --end`: (선택) 종료 날짜 및 시간 `YYYY-MM-DD HH:MM` 형식 (기본값: 현재 UTC 시간)
    - ex) "2023-06-07 23:59"
    - end 시간을 설정하지 않으면 현재 시간으로 end 시간을 설정합니다.
- `-z, --timezone`: (선택) ALB 로그 Timestamp 필드의 기준 타임존 (기본값: `UTC`)
    - 이 옵션을 설정하면 `start` 및 `end` 시간도 해당 타임존으로 변환됩니다.
    - `pytz` 라이브러리에서 지원하는 타임존 형식을 사용하세요.
        - 예: `Asia/Seoul`, `America/New_York`, `Europe/London`

#### 예시

```sh
python main.py -p my-aws-profile -b s3://my-bucket/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/ -s "2023-06-01 00:00" -e "2023-06-07 23:59" -z "Asia/Seoul"
```

### AWS SSO Profile 설정 예제

다음은 AWS SSO 프로파일을 설정하기 위한 `~/.aws/config` 파일의 예제입니다:
aws configure sso 명령을 사용하여 설정할 수도 있습니다.

```ini
[sso-session example1]
sso_start_url = https://example1.awsapps.com/start/#/
sso_region = ap-northeast-2
sso_registration_scopes = sso:account:access
```

### Standard AWS Credentials Profile 설정 예제

다음은 표준 AWS 자격 증명을 설정하기 위한 `~/.aws/credentials` 파일의 예제입니다:
aws configure 명령을 사용하여 설정할 수도 있습니다.

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[my-aws-profile]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY

[my-another-profile]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
aws_session_token = YOUR_SESSION_TOKEN
```

Region을 설정하려면 `~/.aws/config` 파일에 다음과 같이 추가하세요:

```ini
[default]
region = ap-northeast-2
```

#### 추가 자료

- [AWS CLI SSO 프로파일 구성 가이드](https://docs.aws.amazon.com/cli/latest/userguide/sso-configure-profile-token.html#sso-configure-profile-token-auto-sso-session)
- [AWS CLI 인증 사용자 가이드](https://docs.aws.amazon.com/cli/latest/userguide/cli-authentication-user.html#cli-authentication-user-configure.title)
- [pytz 타임존 목록 및 사용법](https://pythonhosted.org/pytz/)

전체 타임존 목록은 `pytz` 라이브러리에서 확인할 수 있습니다.

## 제공하는 보고서 양식

보고서는 다음과 같은 필드를 포함하여 Excel 형식으로 제공됩니다:

- **Timestamp**: 요청이 발생한 시간
- **Client IP**: 요청을 보낸 클라이언트의 IP 주소
- **Request**: 클라이언트가 요청한 URL
- **Status Code**: HTTP 상태 코드 (예: 200, 404, 500)
    - **4xx**: 클라이언트 오류 (예: 404 Not Found)
    - **5xx**: 서버 오류 (예: 500 Internal Server Error)
- **Total time**: 요청 처리에 걸린 총 시간 (밀리초 단위)
- **User agent**: 요청을 보낸 클라이언트의 사용자 에이전트 문자열

이 보고서는 다음과 같은 정보를 제공합니다:

- **요청 분포**: 특정 시간대에 요청이 집중되는 패턴을 파악
- **오류 분석**: 4xx 및 5xx 오류 비율을 분석하여 문제 발생 원인을 파악
- **응답 시간 분석**: 응답 시간이 긴 요청을 식별하여 성능 개선의 기초 자료로 활용

## 참고 사항

- xlsxwriter 모듈 제한 사항으로 보고서는 최대 1048576 행까지 표시되며, 이후 초과되는 데이터는 표시되지 않습니다. 
