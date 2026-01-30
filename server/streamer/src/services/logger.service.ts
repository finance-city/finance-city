// services/logger.service.ts - 구조화된 로깅 서비스

export enum LogLevel {
    ERROR = 0,
    WARN = 1,
    INFO = 2,
    DEBUG = 3
}

export interface LogEntry {
    timestamp: string;
    level: LogLevel;
    message: string;
    context?: string;
    metadata?: Record<string, any>;
}

export class LoggerService {
    private readonly logLevel: LogLevel;
    private readonly context: string;

    constructor(context: string = 'App', logLevel: LogLevel = LogLevel.INFO) {
        this.context = context;
        this.logLevel = logLevel;
    }

    /**
     * 로거 인스턴스 생성 (컨텍스트별)
     */
    static create(context: string, logLevel?: LogLevel): LoggerService {
        return new LoggerService(context, logLevel);
    }

    error(message: string, error?: Error, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.ERROR) {
            this.log(LogLevel.ERROR, message, { error: error?.message, stack: error?.stack, ...metadata });
        }
    }

    warn(message: string, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.WARN) {
            this.log(LogLevel.WARN, message, metadata);
        }
    }

    info(message: string, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.INFO) {
            this.log(LogLevel.INFO, message, metadata);
        }
    }

    debug(message: string, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.DEBUG) {
            this.log(LogLevel.DEBUG, message, metadata);
        }
    }

    /**
     * 주식 데이터 전용 로깅 (성능 최적화)
     */
    stock(action: 'received' | 'processed' | 'broadcast', stockCode: string, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.DEBUG) {
            this.log(LogLevel.DEBUG, `Stock ${action}`, {
                stock_code: stockCode,
                action,
                ...metadata
            });
        }
    }

    /**
     * 성능 측정 로깅
     */
    performance(operation: string, duration: number, metadata?: Record<string, any>): void {
        if (this.logLevel >= LogLevel.INFO) {
            this.log(LogLevel.INFO, `Performance: ${operation}`, {
                operation,
                duration_ms: duration,
                ...metadata
            });
        }
    }

    /**
     * 헬스체크 로깅
     */
    health(component: string, status: 'healthy' | 'unhealthy', metadata?: Record<string, any>): void {
        const level = status === 'healthy' ? LogLevel.INFO : LogLevel.ERROR;
        if (this.logLevel >= level) {
            this.log(level, `Health: ${component} is ${status}`, {
                component,
                status,
                ...metadata
            });
        }
    }

    private log(level: LogLevel, message: string, metadata?: Record<string, any>): void {
        const entry: LogEntry = {
            timestamp: new Date().toISOString(),
            level,
            message,
            context: this.context,
            ...(metadata && { metadata })
        };

        // 개발 환경에서는 예쁘게 출력
        if (process.env.NODE_ENV !== 'production') {
            this.prettyPrint(entry);
        } else {
            // 프로덕션에서는 JSON으로 출력 (로그 수집 시스템용)
            console.log(JSON.stringify(entry));
        }
    }

    private prettyPrint(entry: LogEntry): void {
        const levelEmoji = {
            [LogLevel.ERROR]: '❌',
            [LogLevel.WARN]: '⚠️',
            [LogLevel.INFO]: '✅',
            [LogLevel.DEBUG]: '🔍'
        };

        const levelName = LogLevel[entry.level];
        const emoji = levelEmoji[entry.level];
        const timestamp = entry.timestamp.split('T')[1]?.split('.')[0] || entry.timestamp; // HH:MM:SS만

        let output = `${emoji} [${timestamp}] ${entry.context}: ${entry.message}`;
        
        if (entry.metadata && Object.keys(entry.metadata).length > 0) {
            // 중요한 필드들은 한 줄에 표시
            const { stock_code, action, duration_ms, status, error, ...rest } = entry.metadata;
            
            if (stock_code) output += ` | ${stock_code}`;
            if (action) output += ` | ${action}`;
            if (duration_ms) output += ` | ${duration_ms}ms`;
            if (status) output += ` | ${status}`;
            if (error) output += ` | ${error}`;
            
            // 나머지는 다음 줄에
            if (Object.keys(rest).length > 0) {
                output += `\n    ${JSON.stringify(rest, null, 2).replace(/\n/g, '\n    ')}`;
            }
        }

        console.log(output);
    }
}
