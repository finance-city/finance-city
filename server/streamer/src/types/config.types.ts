// types/config.types.ts - 설정 관련 타입 정의

export interface AppConfig {
    redis: {
        host: string;
        port: number;
        channels: string[];
        // 호환성을 위해 단일 채널도 지원
        channel?: string;
    };
    websocket: {
        port: number;
        maxConnections: number;
    };
    throttler: {
        flushIntervalMs: number;
    };
    logging: {
        level: 'debug' | 'info' | 'warn' | 'error';
    };
}
