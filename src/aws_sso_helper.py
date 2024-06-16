import hashlib
import json
import logging
import os
import webbrowser
from datetime import datetime, timezone
from time import sleep

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()


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
            logger.info("🔄 Loading token cache...")
            cache_key = self.generate_cache_key()
            cache_path = os.path.join(self.home_dir, ".aws", "sso", "cache", f"{cache_key}.json")

            if os.path.exists(cache_path):
                with open(cache_path, 'r') as file:
                    cache = json.loads(file.read())
                    logger.info("✅ Token cache loaded successfully.")
                    return cache
            logger.error(f"❌ Token cache not found in {cache_path}.")
            return None
        except Exception as e:
            logger.error(f"⚠️ Failed to load token cache: {e}")

    def save_token_cache(self, token_cache):
        try:
            cache_key = self.generate_cache_key()
            cache_dir = os.path.join(self.home_dir, ".aws", "sso", "cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{cache_key}.json")

            with open(cache_path, 'w') as file:
                file.write(json.dumps(token_cache))
            logger.info("✅ Token cache saved successfully.")
        except Exception as e:
            logger.error(f"⚠️ Failed to save token cache: {e}")


class AWSSSOHelper:
    def __init__(self, start_url: str, session_name: str, region_name: str, client_name: str = 'myapp',
                 client_type: str = 'public') -> None:
        try:
            logger.info("🚀 Initializing AWS SSO Helper...")
            self.start_url = start_url
            self.session_name = session_name
            self.client_name = client_name
            self.client_type = client_type
            self.home_dir = os.path.expanduser("~")
            self.region_name = region_name
            self.session = boto3.Session()
            self.sso_client = None
            self.sso_oidc_client = self.session.client('sso-oidc')
            self.token_cache_manager = TokenCacheManager(start_url, session_name, self.home_dir)
            self.token_cache = self.token_cache_manager.load_token_cache()

            if self.token_cache:
                self.default_region = self.token_cache["region"]
                self.access_token = self.token_cache["accessToken"]
                self.sso_client = self.session.client('sso', region_name=self.default_region)
                if self._is_token_expired(self.token_cache["expiresAt"]):
                    self._refresh_token()
            else:
                self._start_device_authorization_flow()

            logger.info("✅ AWS SSO Helper initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS SSO Helper: {e}")

    def _is_token_expired(self, expires_at):
        try:
            return datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < datetime.now(
                timezone.utc)
        except Exception as e:
            logger.error(f"❌ Failed to check token expiry: {e}")

    def _start_device_authorization_flow(self):
        try:
            logger.info("🔑 Starting device authorization flow...")

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
            logger.error(f"❌ Failed to start device authorization")

    def _prompt_user_to_authorize(self, verification_url, device_code, expires_in, interval, client_creds):
        logger.info("🔗 Opening device verification URL in browser...")
        logger.info(f"   {verification_url}")
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
                logger.info("✅ Device authorized successfully.")
                return
            except self.sso_oidc_client.exceptions.AuthorizationPendingException:
                continue
            except self.sso_oidc_client.exceptions.SlowDownException:
                logger.error("❌ Slow down. Rate limit exceeded.")
                return
            except self.sso_oidc_client.exceptions.ExpiredTokenException:
                logger.error("❌ Device authorization expired.")
                return
        raise Exception("❌ Device authorization timeout")

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
        logger.info("✅ Token cache updated successfully.")

    def _refresh_token(self):
        logger.info("🔄 Refreshing token...")
        if not self.token_cache.get('refreshToken'):
            logger.error("❌ Refresh token not found. Starting device authorization flow...")
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
            logger.info("✅ Token refreshed successfully.")
        except (self.sso_oidc_client.exceptions.InvalidGrantException, Exception) as e:
            logger.error(f"❌ Failed to refresh token: {e}")
            self._start_device_authorization_flow()

    def get_token_accounts(self):
        logger.info("🔍 Retrieving all SSO accounts...")
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
            logger.info("✅ SSO accounts retrieved successfully.")
            return accounts
        except (BotoCoreError, ClientError, Exception) as e:
            logger.error(f"❌ Failed to retrieve SSO accounts: {e}")
            if 'UnauthorizedException' in str(e) or 'InvalidToken' in str(e):
                logger.info("🔄 Token is invalid. Refreshing token...")
                self._refresh_token()
                return self.get_token_accounts()
            else:
                raise

    def get_sso_session(self, account_id: str, role_name: str):
        logger.info(f"🔑 Creating SSO session for account {account_id} and role {role_name}...")
        try:
            credentials = self.sso_client.get_role_credentials(
                roleName=role_name, accountId=account_id, accessToken=self.access_token)['roleCredentials']

            session = boto3.Session(
                aws_access_key_id=credentials['accessKeyId'],
                aws_secret_access_key=credentials['secretAccessKey'],
                aws_session_token=credentials['sessionToken']
            )
            logger.info(f"✅ SSO session created successfully.")
            return session
        except (BotoCoreError, ClientError, Exception) as e:
            logger.error(f"❌ Failed to create SSO session: {e}")
            if 'ExpiredToken' in str(e) or 'InvalidToken' in str(e):
                logger.info("🔄 Token is invalid. Refreshing token...")
                self._refresh_token()
                return self.get_sso_session(account_id, role_name)
            else:
                raise
