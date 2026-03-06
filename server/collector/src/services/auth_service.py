"""
KIS API용 인증 서비스.

이 서비스는 한국투자증권 API를 위한 토큰 관리, 인증 및 권한 부여를 
처리합니다.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, cast
import requests
import json
import redis

from core import IAuthManager, AuthCredentials, APIError, AuthenticationError
from config import TradingConfig


class AuthService(IAuthManager):
    """KIS API 인증 관리 서비스."""
    
    def __init__(self, config: TradingConfig, redis_client: Optional[redis.Redis] = None):
        """인증 서비스를 초기화합니다.
        
        Args:
            config: API 인증정보가 포함된 거래 설정
            redis_client: 토큰 캐싱을 위한 선택적 Redis 클라이언트
        """
        self._config = config
        self._redis = redis_client
        self._credentials = AuthCredentials(
            app_key=config.kis_app_key,
            app_secret=config.kis_app_secret
        )
        self._token_cache_prefix = "kis:auth:"
        self._approval_cache_prefix = "kis:auth:approval:"
    
    def get_access_token(self) -> str:
        """현재 액세스 토큰을 가져옵니다. 필요한 경우 갱신합니다.
        
        Returns:
            유효한 액세스 토큰
            
        Raises:
            AuthenticationError: 토큰을 얻을 수 없는 경우
        """
        # 먼저 캐시된 토큰을 가져오려고 시도
        cached_token = self._get_cached_token()
        if cached_token and self._is_token_valid_cached(cached_token):
            self._credentials.access_token = cached_token["token"]
            self._credentials.access_token_expired = cached_token["expires_at"]
            return self._credentials.access_token
        
        # 새 토큰 요청
        try:
            token_data = self._request_new_token()
            
            # 새 토큰 캐시
            self._cache_token(token_data)
            
            # 인증정보 업데이트
            self._credentials.access_token = token_data["access_token"]
            self._credentials.access_token_expired = token_data["access_token_expired"]
            
            return self._credentials.access_token
            
        except Exception as e:
            raise AuthenticationError(f"Failed to obtain access token: {e}", auth_type="token")
    
    def get_approval_key(self, force_refresh: bool = False) -> str:
        """WebSocket 연결을 위한 승인 키를 가져옵니다.
        
        Args:
            force_refresh: True이면 캐시를 무시하고 새로운 키를 요청
        
        Returns:
            유효한 승인 키
            
        Raises:
            AuthenticationError: 승인 키를 얻을 수 없는 경우
        """
        import logging
        
        # 유효한 액세스 토큰이 있는지 확인
        access_token = self.get_access_token()
        
        # Try to get cached approval key (force_refresh가 False일 때만)
        if not force_refresh:
            cached_approval = self._get_cached_approval_key()
            if cached_approval:
                logging.info(f"✅ 캐시된 승인 키 사용: {cached_approval[:8]}...")
                self._credentials.approval_key = cached_approval
                return self._credentials.approval_key
        
        # Request new approval key
        try:
            logging.info("🔑 새로운 승인 키 요청 중...")
            approval_key = self._request_new_approval_key(access_token)
            
            # Cache the approval key
            self._cache_approval_key(approval_key)
            
            # Update credentials
            self._credentials.approval_key = approval_key
            
            logging.info(f"✅ 새로운 승인 키 발급: {approval_key[:8]}...")
            return self._credentials.approval_key
            
        except Exception as e:
            raise AuthenticationError(f"Failed to obtain approval key: {e}", auth_type="approval")
    
    def refresh_token_if_needed(self) -> bool:
        """토큰이 만료에 가까우면 갱신합니다.
        
        Returns:
            토큰이 갱신된 경우 True, 여전히 유효한 경우 False
        """
        try:
            if not self.is_token_valid():
                self.get_access_token()  # 이것은 토큰을 갱신합니다
                return True
            return False
        except AuthenticationError:
            return False
    
    def is_token_valid(self) -> bool:
        """현재 토큰이 유효한지 확인합니다.
        
        Returns:
            토큰이 유효하고 만료되지 않은 경우 True
        """
        if not self._credentials.access_token or not self._credentials.access_token_expired:
            return False
        
        try:
            expired_time = datetime.fromisoformat(self._credentials.access_token_expired)
            # 5분 이내에 만료되는 토큰은 유효하지 않은 것으로 간주
            buffer_time = datetime.now() + timedelta(minutes=5)
            return expired_time > buffer_time
        except (ValueError, TypeError):
            return False
    
    def _request_new_token(self) -> Dict[str, str]:
        """KIS API에서 새로운 액세스 토큰을 요청합니다.
        
        Returns:
            토큰 데이터를 포함하는 딕셔너리
            
        Raises:
            APIError: 토큰 요청이 실패한 경우
        """
        url = f"{self._config.kis_api_base_url}/oauth2/tokenP"
        
        headers = {
            "Content-Type": "application/json"  # backup 버전과 동일하게 수정
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self._credentials.app_key,
            "appsecret": self._credentials.app_secret
        }
        
        try:
            import logging
            logging.info(f"🔑 Requesting token from: {url}")
            logging.debug(f"Request data: {data}")
            
            # backup 버전과 동일하게 json=data 사용
            response = requests.post(url, headers=headers, json=data)
            
            # 응답 상세 로깅
            logging.info(f"Response status: {response.status_code}")
            logging.info(f"Response text: {response.text[:500]}")
            
            response.raise_for_status()
            
            result = response.json()
            logging.debug(f"Response: {result}")
            
            # OAuth2 토큰 응답의 경우 rt_cd 필드가 없으므로 access_token 존재 여부로 성공 판단
            if "access_token" not in result:
                error_msg = result.get("msg1", result.get("error_description", "Token not found in response"))
                error_code = result.get("rt_cd", result.get("error", "UNKNOWN"))
                logging.error(f"❌ KIS API 에러 - 코드: {error_code}, 메시지: {error_msg}")
                logging.error(f"❌ Full response: {result}")
                raise APIError(f"Token request failed: {error_msg}", api_endpoint=url, status_code=response.status_code)
            
            logging.info("✅ 토큰 발급 성공")
            return {
                "access_token": result["access_token"],
                "access_token_expired": result["access_token_token_expired"]
            }
            
        except requests.RequestException as e:
            logging.error(f"❌ HTTP 요청 실패: {e}")
            raise APIError(f"HTTP request failed: {e}", api_endpoint=url)
        except (KeyError, ValueError) as e:
            raise APIError(f"Invalid response format: {e}", api_endpoint=url, response=response.text[:200])
    
    def _request_new_approval_key(self, access_token: str) -> str:
        """KIS API에서 새로운 승인 키를 요청합니다.
        
        Args:
            access_token: 유효한 액세스 토큰
            
        Returns:
            승인 키 문자열
            
        Raises:
            APIError: 승인 키 요청이 실패한 경우
        """
        url = f"{self._config.kis_api_base_url}/oauth2/Approval"
        
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": self._credentials.app_key,
            "appsecret": self._credentials.app_secret
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self._credentials.app_key,
            "secretkey": self._credentials.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # 승인키 응답도 rt_cd 필드가 없을 수 있음, approval_key 존재 여부로 판단
            if "approval_key" not in result:
                error_msg = result.get("msg1", result.get("error_description", "Approval key not found in response"))
                error_code = result.get("rt_cd", result.get("error", "UNKNOWN"))
                raise APIError(f"Approval key request failed: {error_msg}", api_endpoint=url, status_code=response.status_code)
            
            return result["approval_key"]
            
        except requests.RequestException as e:
            raise APIError(f"HTTP request failed: {e}", api_endpoint=url)
        except (KeyError, ValueError) as e:
            raise APIError(f"Invalid response format: {e}", api_endpoint=url, response=response.text[:200])
    
    def _get_cached_token(self) -> Optional[Dict[str, str]]:
        """사용 가능한 경우 Redis에서 캐시된 토큰을 가져옵니다."""
        if not self._redis:
            return None
        
        try:
            # 단순한 캐시 키 사용 (기존 토큰과 호환)
            cache_key = "kis:auth:token"
            cached_data = self._redis.get(cache_key)
            
            if cached_data:
                # Handle both bytes and string responses from Redis
                cached_str = cached_data.decode('utf-8') if isinstance(cached_data, bytes) else cast(str, cached_data)
                token_data = json.loads(cached_str)
                
                # 형식 변환: 기존 형식을 새로운 형식으로
                if "access_token" in token_data and "expires_at" in token_data:
                    return {
                        "token": token_data["access_token"],
                        "expires_at": token_data["expires_at"]
                    }
        except Exception as e:
            print(f"Warning: Failed to get cached token: {e}")
        
        return None
    
    def _cache_token(self, token_data: Dict[str, str]) -> None:
        """토큰 데이터를 Redis에 캐시합니다."""
        if not self._redis:
            return
        
        try:
            # 기존 형식과 호환되도록 저장
            cache_key = "kis:auth:token"
            cache_data = {
                "access_token": token_data["access_token"],
                "expires_at": token_data["access_token_expired"],
                "approval_key": None  # approval_key는 별도 저장
            }
            # Cache for 23 hours (tokens are valid for 24 hours)
            self._redis.setex(cache_key, 23 * 3600, json.dumps(cache_data))
        except Exception as e:
            print(f"Warning: Failed to cache token: {e}")
    
    def _is_token_valid_cached(self, token_data: Dict[str, str]) -> bool:
        """캐시된 토큰이 여전히 유효한지 확인합니다."""
        try:
            expired_time = datetime.fromisoformat(token_data["expires_at"])
            buffer_time = datetime.now() + timedelta(minutes=5)
            return expired_time > buffer_time
        except (KeyError, ValueError, TypeError):
            return False
    
    def _get_cached_approval_key(self) -> Optional[str]:
        """사용 가능한 경우 Redis에서 캐시된 승인 키를 가져옵니다."""
        if not self._redis:
            return None

        try:
            all_keys = self._redis.keys(f"{self._approval_cache_prefix}*")
            if all_keys:
                # 첫 번째 키의 값을 반환 (기존 캐시된 approval key 사용)
                first_key = all_keys[0]
                cached_key = self._redis.get(first_key)
                if cached_key:
                    return cached_key.decode('utf-8') if isinstance(cached_key, bytes) else cast(str, cached_key)
        except Exception as e2:
            print(f"Warning: Error searching for approval keys: {e2}")
                
        return None
    
    def _cache_approval_key(self, approval_key: str) -> None:
        """승인 키를 Redis에 캐시합니다.
        
        Note: KIS 공식 문서에 따르면 approval key는:
        - 유효기간: 24시간
        - 세션 연결 시 초기 1회만 사용
        - 세션이 유지되면 재발급 불필요
        
        하지만 WebSocket 재연결 시에는 새 키가 필요할 수 있으므로
        짧은 캐시 시간(1시간)을 사용하여 재연결 시 새 키 발급 유도
        """
        if not self._redis:
            return
        
        try:
            cache_key = f"{self._approval_cache_prefix}{self._credentials.app_key}"
            # 1시간만 캐시: WebSocket 재연결 시 새 키 발급 유도
            self._redis.setex(cache_key, 3600, approval_key)
            import logging
            logging.info(f"승인 키 캐시 저장 (1시간): {cache_key}")
        except Exception as e:
            print(f"Warning: Failed to cache approval key: {e}")
    
    def revoke_token(self) -> bool:
        """현재 액세스 토큰을 취소합니다.
        
        Returns:
            토큰이 성공적으로 취소된 경우 True
        """
        if not self._credentials.access_token:
            return True
        
        url = f"{self._config.kis_api_base_url}/oauth2/revokeP"
        
        headers = {
            "content-type": "application/json; charset=utf-8"
        }
        
        data = {
            "appkey": self._credentials.app_key,
            "appsecret": self._credentials.app_secret,
            "token": self._credentials.access_token
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            response.raise_for_status()
            
            result = response.json()
            success = result.get("rt_cd") == "0"
            
            if success:
                # 캐시된 토큰들 지우기
                self._clear_cached_tokens()
                # Clear credentials
                self._credentials.access_token = ""
                self._credentials.access_token_expired = ""
                self._credentials.approval_key = ""
            
            return success
            
        except Exception as e:
            print(f"Warning: Failed to revoke token: {e}")
            return False
    
    def _clear_cached_tokens(self) -> None:
        """모든 캐시된 인증 데이터를 지웁니다."""
        if not self._redis:
            return
        
        try:
            token_key = f"{self._token_cache_prefix}{self._credentials.app_key}"
            approval_key = f"{self._approval_cache_prefix}{self._credentials.app_key}"
            
            self._redis.delete(token_key, approval_key)
        except Exception as e:
            print(f"Warning: Failed to clear cached tokens: {e}")
    
    def get_credentials(self) -> AuthCredentials:
        """현재 인증 정보를 가져옵니다.
        
        Returns:
            현재 인증정보의 복사본
        """
        return AuthCredentials(
            app_key=self._credentials.app_key,
            app_secret=self._credentials.app_secret,
            access_token=self._credentials.access_token,
            access_token_expired=self._credentials.access_token_expired,
            approval_key=self._credentials.approval_key
        )
