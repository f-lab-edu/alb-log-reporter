import configparser
import hashlib
import json
import logging
import os
import signal
import webbrowser
from datetime import datetime, timezone
from time import sleep

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("입력 시간이 초과되었습니다.")


class TokenCacheManager:
    def __init__(self, start_url, session_name, home_dir):
        self.start_url = start_url
        self.session_name = session_name
        self.home_dir = home_dir

    def generate_cache_key(self):
        input_str = self.session_name or self.start_url
        return hashlib.sha1(input_str.encode('utf-8')).hexdigest()

    def load_token_cache(self):
        try:
            logger.info("토큰 캐시를 로드 중...")
            cache_key = self.generate_cache_key()
            cache_path = os.path.join(self.home_dir, ".aws", "sso", "cache", f"{cache_key}.json")

            if os.path.exists(cache_path):
                with open(cache_path, 'r') as file:
                    cache = json.loads(file.read())
                    logger.info("토큰 캐시가 성공적으로 로드되었습니다.")
                    return cache
            logger.error("토큰 캐시 파일을 찾을 수 없습니다. 새로 고침이 필요합니다.")
            return None
        except Exception as e:
            logger.error(f"토큰 캐시 로드 오류: {e}")

    def save_token_cache(self, token_cache):
        try:
            cache_key = self.generate_cache_key()
            cache_dir = os.path.join(self.home_dir, ".aws", "sso", "cache")
            os.makedirs(cache_dir, exist_ok=True)  # 디렉토리 존재 여부 확인
            cache_path = os.path.join(cache_dir, f"{cache_key}.json")

            with open(cache_path, 'w') as file:
                file.write(json.dumps(token_cache))
            logger.info("토큰 캐시가 성공적으로 저장되었습니다.")
        except Exception as e:
            logger.error(f"토큰 캐시 저장 오류: {e}")


class AWSSSOHelper:
    def __init__(self, start_url: str, session_name: str, client_name: str = 'myapp',
                 client_type: str = 'public') -> None:
        try:
            logger.info("초기화를 시작합니다...")
            self.start_url = start_url
            self.session_name = session_name
            self.client_name = client_name
            self.client_type = client_type
            self.home_dir = os.path.expanduser("~")

            # ~/.aws/config 파일 읽기
            config = configparser.ConfigParser()
            config_path = os.path.join(self.home_dir, ".aws", "config")
            config.read(config_path)

            if "default" in config and "region" in config["default"]:
                self.default_region = config.get("default", "region")
            else:
                # 타임아웃 시그널 핸들러 등록
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(60)  # 60초 (1분) 타임아웃 설정

                try:
                    # 사용자로부터 리전 입력받기
                    self.default_region = input("AWS 리전을 입력하세요 (예: us-east-1): ")

                    # 입력받은 리전이 비어있는 경우 기본값으로 us-east-1 사용
                    if not self.default_region.strip():
                        logger.warning("리전이 입력되지 않아 기본값으로 us-east-1을 사용합니다.")
                        self.default_region = "us-east-1"

                    # ~/.aws/config 파일에 리전 저장
                    if "default" not in config:
                        config["default"] = {}
                    config["default"]["region"] = self.default_region
                    with open(config_path, 'w') as f:
                        config.write(f)

                except TimeoutError:
                    logger.warning("입력 시간이 초과되어 기본값으로 us-east-1을 사용합니다.")
                    self.default_region = "us-east-1"

                finally:
                    signal.alarm(0)  # 타임아웃 시그널 해제

            self.session = boto3.Session(region_name=self.default_region)
            self.sso_client = None
            self.sso_oidc_client = self.session.client('sso-oidc')
            self.token_cache_manager = TokenCacheManager(start_url, session_name, self.home_dir)
            self.token_cache = self.token_cache_manager.load_token_cache()

            if self.token_cache:
                self.access_token = self.token_cache["accessToken"]
                self.sso_client = self.session.client('sso', region_name=self.default_region)
                if self._is_token_expired(self.token_cache["expiresAt"]):
                    self._refresh_token()
            else:
                self._start_device_authorization_flow()

            logger.info("초기화가 성공적으로 완료되었습니다.")
        except Exception as e:
            logger.error(f"초기화 오류: {e}")

    def _is_token_expired(self, expires_at):
        try:
            return datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < datetime.now(
                timezone.utc)
        except Exception as e:
            logger.error(f"토큰 만료 확인 오류: {e}")

    def _start_device_authorization_flow(self):
        try:
            logger.info("디바이스 인증 프로세스를 시작합니다...")

            client_creds = self.sso_oidc_client.register_client(
                clientName=self.client_name,
                clientType=self.client_type,
                scopes=['openid', 'profile', 'email'],
            )

            device_auth = self.sso_oidc_client.start_device_authorization(
                clientId=client_creds['clientId'],
                clientSecret=client_creds['clientSecret'],
                startUrl=self.start_url,
            )

            self._prompt_user_to_authorize(device_auth['verificationUriComplete'], device_auth['deviceCode'],
                                           device_auth['expiresIn'], device_auth['interval'], client_creds)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"디바이스 인증 오류: {e}")

    def _prompt_user_to_authorize(self, verification_url, device_code, expires_in, interval, client_creds):
        webbrowser.open(verification_url, autoraise=True)

        for _ in range(0, expires_in // interval):
            sleep(interval)
            try:
                token = self.sso_oidc_client.create_token(
                    grantType='urn:ietf:params:oauth:grant-type:device_code',
                    deviceCode=device_code,
                    clientId=client_creds['clientId'],
                    clientSecret=client_creds['clientSecret'],
                )
                self._update_token_cache(token, client_creds)
                return
            except self.sso_oidc_client.exceptions.AuthorizationPendingException:
                continue
        raise Exception("인증 실패 또는 만료되었습니다.")

    def _update_token_cache(self, token, client_creds):
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + token["expiresIn"]).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        token_cache = {
            "accessToken": token['accessToken'],
            "clientId": client_creds['clientId'],
            "clientSecret": client_creds['clientSecret'],
            "expiresAt": expires_at,
            "refreshToken": token.get('refreshToken'),
            "region": self.session.region_name,
        }
        self.token_cache_manager.save_token_cache(token_cache)
        self.token_cache = token_cache
        self.default_region = self.token_cache["region"]
        self.access_token = self.token_cache["accessToken"]
        self.sso_client = self.session.client('sso', region_name=self.default_region)
        logger.info("디바이스 인증이 성공적으로 완료되었습니다.")

    def _refresh_token(self):
        logger.info("토큰을 갱신 중...")
        if not self.token_cache.get('refreshToken'):
            logger.error("갱신 토큰이 없습니다. 디바이스 인증 프로세스를 다시 시작합니다.")
            self._start_device_authorization_flow()
            return

        try:
            response = self.sso_oidc_client.create_token(
                clientId=self.token_cache['clientId'],
                clientSecret=self.token_cache['clientSecret'],
                grantType='refresh_token',
                refreshToken=self.token_cache['refreshToken']
            )
            self._update_token_cache(response, self.token_cache)
            logger.info("토큰이 성공적으로 갱신되었습니다.")
        except (self.sso_oidc_client.exceptions.InvalidGrantException, Exception) as e:
            logger.error(f"토큰 갱신 오류: {e}")
            self._start_device_authorization_flow()

    def get_token_accounts(self):
        logger.info("SSO 계정 목록을 가져오는 중...")
        if not self.sso_client:
            self.sso_client = self.session.client('sso', region_name=self.default_region)

        try:
            account_paginator = self.sso_client.get_paginator('list_accounts')
            response_iterator = account_paginator.paginate(accessToken=self.access_token,
                                                           PaginationConfig={'MaxItems': 60, 'PageSize': 60})

            accounts = {}
            for response in response_iterator:
                for account in response['accountList']:
                    accounts[account['accountId']] = {
                        "accountId": account['accountId'],
                        "accountName": account['accountName'],
                        "emailAddress": account['emailAddress'],
                        "roles": []
                    }
                    roles = self.sso_client.list_account_roles(
                        accessToken=self.access_token, accountId=account['accountId'])['roleList']
                    for role in roles:
                        accounts[account['accountId']]['roles'].append(role['roleName'])
            logger.info("SSO 계정 목록을 성공적으로 가져왔습니다.")
            return accounts
        except (BotoCoreError, ClientError, Exception) as e:
            logger.error(f"SSO 계정 목록 가져오기 오류: {e}")

    def get_sso_session(self, account_id: str, role_name: str):
        logger.info(f"계정 {account_id}에 대한 역할 {role_name}로 SSO 세션을 생성 중...")
        try:
            credentials = self.sso_client.get_role_credentials(
                roleName=role_name, accountId=account_id, accessToken=self.access_token)['roleCredentials']

            session = boto3.Session(
                aws_access_key_id=credentials['accessKeyId'],
                aws_secret_access_key=credentials['secretAccessKey'],
                aws_session_token=credentials['sessionToken']
            )
            logger.info(f"계정 {account_id}에 대한 SSO 세션이 성공적으로 생성되었습니다.")
            return session
        except (BotoCoreError, ClientError, Exception) as e:
            logger.error(f"SSO 세션 생성 오류: {e}")
