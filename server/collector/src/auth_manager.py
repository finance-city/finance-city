# auth_manager.py

import os
import json
import logging
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import redis
import requests
from dataclasses import dataclass


@dataclass
class TokenData:
    """토큰 정보를 담는 데이터클래스"""
    access_token: str
    expires_at: datetime
    approval_key: Optional[str] = None
    
    def is_expired(self) -> bool:
        """토큰이 만료되었는지 확인 (5분 여유시간 포함)"""
        return datetime.now() >= (self.expires_at - timedelta(minutes=5))
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장을 위한 딕셔너리 변환"""
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at.isoformat(),
            "approval_key": self.approval_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenData':
        """Redis 데이터로부터 TokenData 생성"""
        return cls(
            access_token=data["access_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            approval_key=data.get("approval_key")
        )


class AuthManager:
    """KIS API 인증 토큰을 관리하는 클래스"""
    
    def __init__(self, redis_client: redis.Redis, app_key: str, app_secret: str):
        """
        Args:
            redis_client: 동기 Redis 클라이언트
            app_key: KIS API 앱 키
            app_secret: KIS API 앱 시크릿
        """
        self.redis = redis_client
        self.app_key = app_key
        self.app_secret = app_secret
        self.token_key = "kis:auth:token"
        self.approval_key_prefix = "kis:auth:approval"
        self._shutdown_handlers = []
        
        # Graceful shutdown을 위한 시그널 핸들러 등록
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def get_valid_access_token(self) -> str:
        """유효한 Access Token 반환 (캐시된 토큰 우선 사용)"""
        try:
            cached_token = self._get_cached_token()
            if cached_token and not cached_token.is_expired():
                logging.info("Using cached access token")
                return cached_token.access_token
            
            logging.info("Issuing new access token...")
            token_data = await self._issue_new_token()
            self._cache_token(token_data)
            
            return token_data.access_token
            
        except Exception as e:
            logging.error(f"Failed to get access token: {e}")
            raise
    
    async def get_valid_approval_key(self, access_token: str) -> str:
        """유효한 Approval Key 반환 (캐시된 키 우선 사용)"""
        try:
            approval_key = f"{self.approval_key_prefix}:{access_token[:20]}"
            
            cached_key = self.redis.get(approval_key)
            if cached_key:
                logging.info("Using cached approval key")
                if isinstance(cached_key, bytes):
                    return cached_key.decode('utf-8')
                return str(cached_key)
            
            logging.info("Issuing new approval key...")
            new_approval_key = await self._issue_approval_key(access_token)
            
            self.redis.setex(approval_key, 24 * 3600, new_approval_key)
            
            return new_approval_key
            
        except Exception as e:
            logging.error(f"Failed to get approval key: {e}")
            raise
    
    def _get_cached_token(self) -> Optional[TokenData]:
        """Redis에서 캐시된 토큰 데이터 조회"""
        try:
            cached_data = self.redis.get(self.token_key)
            if cached_data:
                if isinstance(cached_data, bytes):
                    data = json.loads(cached_data.decode('utf-8'))
                else:
                    data = json.loads(str(cached_data))
                return TokenData.from_dict(data)
        except Exception as e:
            logging.warning(f"Failed to get cached token: {e}")
        return None
    
    def _cache_token(self, token_data: TokenData) -> None:
        """토큰 데이터를 Redis에 캐시"""
        try:
            # 만료시간까지의 TTL 계산
            ttl_seconds = int((token_data.expires_at - datetime.now()).total_seconds())
            if ttl_seconds > 0:
                self.redis.setex(
                    self.token_key, 
                    ttl_seconds, 
                    json.dumps(token_data.to_dict())
                )
                logging.info(f"Token cached with TTL: {ttl_seconds} seconds")
        except Exception as e:
            logging.warning(f"Failed to cache token: {e}")
    
    async def _issue_new_token(self) -> TokenData:
        """새로운 Access Token 발급"""
        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        headers = {"Content-Type": "application/json"}
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            access_token = result["access_token"]
            expires_in = result["expires_in"]
            
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logging.info(f"Access token issued, expires at: {expires_at}")
            
            return TokenData(
                access_token=access_token,
                expires_at=expires_at
            )
        else:
            error_msg = f"Failed to get access token: {response.status_code} - {response.text}"
            logging.error(error_msg)
            raise Exception(error_msg)
    
    async def _issue_approval_key(self, access_token: str) -> str:
        """새로운 Approval Key 발급"""
        url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}"
        }
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            approval_key = result["approval_key"]
            
            logging.info("Approval key issued successfully")
            return approval_key
        else:
            error_msg = f"Failed to get approval key: {response.status_code} - {response.text}"
            logging.error(error_msg)
            raise Exception(error_msg)
    
    async def revoke_token(self, force: bool = False) -> None:
        """토큰 파기 (종료시 호출)"""
        if not force:
            revoke_on_exit = os.getenv("REVOKE_TOKEN_ON_EXIT", "false").lower() == "true"
            environment = os.getenv("ENVIRONMENT", "development")
            
            if not revoke_on_exit and environment == "development":
                logging.info("Development mode - keeping token for reuse")
                return
        
        try:
            cached_token = self._get_cached_token()
            if cached_token:
                url = "https://openapi.koreainvestment.com:9443/oauth2/revokeP"
                headers = {
                    "Content-Type": "application/json",
                    "authorization": f"Bearer {cached_token.access_token}"
                }
                data = {
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                    "token": cached_token.access_token
                }
                
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    logging.info("Token revoked successfully")
                else:
                    logging.warning(f"Token revocation failed: {response.status_code}")
            
            self.redis.delete(self.token_key)
            
            try:
                pattern = f"{self.approval_key_prefix}:*"
                for key in self.redis.scan_iter(match=pattern):
                    self.redis.delete(key)
            except Exception as e:
                logging.warning(f"Failed to delete approval keys: {e}")
                
            logging.info("Redis cache cleared")
            
        except Exception as e:
            logging.error(f"Token revocation error: {e}")
    
    async def shutdown(self, revoke_token: Optional[bool] = None) -> None:
        """Graceful shutdown 수행"""
        logging.info("AuthManager shutdown started...")
        
        try:
            if revoke_token is None:
                await self.revoke_token(force=False)
            elif revoke_token:
                await self.revoke_token(force=True)
            else:
                logging.info("Token kept for reuse")
            
            for handler in self._shutdown_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as e:
                    logging.error(f"Shutdown handler error: {e}")
            
            logging.info("AuthManager shutdown completed")
            
        except Exception as e:
            logging.error(f"Shutdown error: {e}")
        
        finally:
            os._exit(0)
    
    def add_shutdown_handler(self, handler):
        """Shutdown 시 실행할 핸들러 등록"""
        self._shutdown_handlers.append(handler)
