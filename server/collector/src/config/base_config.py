# config/base_config.py

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class AppConfig:
    """애플리케이션 기본 설정"""
    # KIS API 설정
    kis_app_key: str
    kis_app_secret: str
    kis_ws_url: str
    kis_api_base_url: str
    
    # Redis 설정
    redis_host: str
    redis_port: int
    redis_channel: str
    
    # 애플리케이션 설정
    environment: str
    revoke_token_on_exit: bool
    debug_mode: bool
    
    # 파일 경로
    stocks_csv_path: str
    
    @classmethod
    def from_environment(cls, env_file: Optional[str] = None) -> 'AppConfig':
        """환경변수에서 설정 로드"""
        if env_file:
            load_dotenv(env_file)
        else:
            # 기본 .env 파일 위치
            base_dir = Path(__file__).parent.parent.parent
            load_dotenv(base_dir / ".env")
        
        return cls(
            # KIS API
            kis_app_key=os.getenv("KIS_APP_KEY", ""),
            kis_app_secret=os.getenv("KIS_APP_SECRET", ""),
            kis_ws_url=os.getenv("KIS_WS_URL", "ws://ops.koreainvestment.com:21000"),
            kis_api_base_url=os.getenv("KIS_API_BASE_URL", "https://openapi.koreainvestment.com:9443"),
            
            # Redis
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_channel=os.getenv("REDIS_CHANNEL", "stock:realtime"),
            
            # 애플리케이션
            environment=os.getenv("ENVIRONMENT", "development"),
            revoke_token_on_exit=os.getenv("REVOKE_TOKEN_ON_EXIT", "false").lower() == "true",
            debug_mode=os.getenv("DEBUG", "false").lower() == "true",
            
            # 파일 경로
            stocks_csv_path=cls._get_stocks_csv_path()
        )
    
    @staticmethod
    def _get_stocks_csv_path() -> str:
        """stocks.csv 파일 경로 계산"""
        base_dir = Path(__file__).parent.parent.parent
        return str(base_dir / "stocks.csv")
    
    def validate(self) -> None:
        """설정 검증"""
        required_fields = [
            ("kis_app_key", self.kis_app_key),
            ("kis_app_secret", self.kis_app_secret),
        ]
        
        missing_fields = [name for name, value in required_fields if not value]
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
        
        # URL 유효성 검증
        if not self.kis_ws_url.startswith(("ws://", "wss://")):
            raise ValueError(f"Invalid WebSocket URL: {self.kis_ws_url}")
        
        if not self.kis_api_base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid API base URL: {self.kis_api_base_url}")
        
        # 포트 범위 검증
        if not (1 <= self.redis_port <= 65535):
            raise ValueError(f"Invalid Redis port: {self.redis_port}")
        
        # 환경 검증
        valid_environments = {"development", "staging", "production"}
        if self.environment not in valid_environments:
            raise ValueError(f"Invalid environment: {self.environment}. Must be one of {valid_environments}")
    
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment == "development"
    
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment == "production"


# 전역 설정 인스턴스 (싱글톤)
_app_config: Optional[AppConfig] = None


def get_app_config(env_file: Optional[str] = None) -> AppConfig:
    """애플리케이션 설정 인스턴스 반환 (싱글톤)"""
    global _app_config
    if _app_config is None:
        _app_config = AppConfig.from_environment(env_file)
        _app_config.validate()
    return _app_config


def reload_config(env_file: Optional[str] = None) -> AppConfig:
    """설정 강제 재로드"""
    global _app_config
    _app_config = None
    return get_app_config(env_file)
