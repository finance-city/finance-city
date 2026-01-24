# collector_main.py

import logging
import sys
from orchestrator import CollectorOrchestrator
from config import AppConfig


def main():
    """메인 함수: CollectorOrchestrator를 사용하여 실시간 주식 수집기 실행"""
    try:
        # 설정 로드 (환경변수에서)
        config = AppConfig.from_environment()
        
        # 오케스트레이터 생성
        orchestrator = CollectorOrchestrator(config)
        
        # 1. 초기화
        if not orchestrator.initialize():
            logging.error("❌ 오케스트레이터 초기화 실패")
            return 1
        
        # 2. 검증
        if not orchestrator.validate():
            logging.error("❌ 종목 및 시장 검증 실패")
            return 1
        
        # 3. 구독 설정
        if not orchestrator.setup_subscriptions():
            logging.error("❌ 구독 설정 실패")
            return 1
        
        # 4. 실행 (blocking)
        orchestrator.run()
        
        return 0
        
    except Exception as e:
        logging.error(f"❌ 예기치 않은 오류: {e}")
        return 1
    
    finally:
        # 5. 정리 (오케스트레이터가 자체 정리)
        logging.info("프로그램 종료")

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
