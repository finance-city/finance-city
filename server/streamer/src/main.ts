// main.ts - 애플리케이션 진입점

import { AppService } from './services/app.service.js';
import { LoggerService, LogLevel } from './services/logger.service.js';
import { loadConfig } from './config/app.config.js';

/**
 * 애플리케이션 진입점
 * 단순하고 깔끔하게 AppService에 위임
 */
async function main(): Promise<void> {
    // 설정 로드
    const config = loadConfig();
    
    // 환경별 로그 레벨 설정
    const logLevel = process.env.NODE_ENV === 'development' ? LogLevel.DEBUG : LogLevel.INFO;
    const logger = LoggerService.create('Main', logLevel);

    logger.info('🚀 Finance City Streamer starting...');

    // AppService 생성 및 시작
    const app = new AppService(config);
    
    try {
        await app.start();
    } catch (error) {
        logger.error('Failed to start application', error as Error);
        process.exit(1);
    }
}

main().catch(console.error);