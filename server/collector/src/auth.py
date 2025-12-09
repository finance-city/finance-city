# auth.py (AuthManager 호환성 래퍼)

import os
import asyncio
import redis
from typing import Optional
from dotenv import load_dotenv
from auth_manager import AuthManager

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if not APP_KEY or not APP_SECRET or APP_KEY == "YOUR_KIS_APP_KEY" or APP_SECRET == "YOUR_KIS_APP_SECRET":
    raise ValueError("`.env` 파일에 KIS_APP_KEY와 KIS_APP_SECRET이 올바르게 설정되지 않았습니다.")

_auth_manager = None

def _get_auth_manager() -> AuthManager:
    """AuthManager 싱글톤 인스턴스 반환"""
    global _auth_manager
    if _auth_manager is None:
        if not APP_KEY or not APP_SECRET:
            raise ValueError("KIS_APP_KEY 또는 KIS_APP_SECRET이 설정되지 않았습니다.")
            
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        _auth_manager = AuthManager(redis_client, APP_KEY, APP_SECRET)
    return _auth_manager

def get_access_token() -> str:
    """KIS Access Token을 발급받거나 캐시된 유효한 토큰을 반환합니다."""
    auth_manager = _get_auth_manager()
    
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, auth_manager.get_valid_access_token())
            return future.result()
    else:
        return loop.run_until_complete(auth_manager.get_valid_access_token())

def get_approval_key(token: str) -> str:
    """WebSocket 연결에 필요한 Approval Key를 발급받아 반환합니다."""
    auth_manager = _get_auth_manager()
    
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, auth_manager.get_valid_approval_key(token))
            return future.result()
    else:
        return loop.run_until_complete(auth_manager.get_valid_approval_key(token))

def get_auth_manager() -> AuthManager:
    """AuthManager 인스턴스를 직접 반환"""
    return _get_auth_manager()

async def shutdown_auth(revoke_token: Optional[bool] = None):
    """인증 매니저 종료"""
    global _auth_manager
    if _auth_manager:
        await _auth_manager.shutdown(revoke_token=revoke_token)

if __name__ == '__main__':
    try:
        token = get_access_token()
        approval_key = get_approval_key(token)
        print(f"✅ 인증 테스트 성공:")
        print(f" - Access Token: {token[:10]}...")
        print(f" - Approval Key: {approval_key[:10]}...")
    except Exception as e:
        print(f"❌ 인증 테스트 실패: {e}")