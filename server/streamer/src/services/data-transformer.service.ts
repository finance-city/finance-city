// services/data-transformer.service.ts - 데이터 변환 로직 분리

import type { RedisStockMessage, ClientStockData } from '../types/index.js';
import { LoggerService } from './logger.service.js';

export class DataTransformerService {
    private readonly logger = LoggerService.create('DataTransformer');

    /**
     * Redis 메시지를 클라이언트용 데이터로 변환
     */
    transformToClientData(message: RedisStockMessage): ClientStockData {
        try {
            const clientData = {
                c: this.extractStockCode(message),
                p: this.safeNumber(message.data?.price || message.current_price),
                r: this.safeNumber(message.data?.rate),
                vt: this.safeNumber(message.data?.vol_tick),
                vl: this.safeNumber(message.data?.vol_total),
                t: Date.now(),
            };

            // 데이터 품질 검증
            this.validateClientData(clientData);

            this.logger.debug('Data transformed', {
                stock_code: clientData.c,
                price: clientData.p,
                volume_tick: clientData.vt
            });

            return clientData;

        } catch (error) {
            this.logger.error('Data transformation failed', error as Error, {
                stock_code: message.stock_code,
                original_message: message
            });

            // 기본값으로 폴백
            return this.createFallbackData(message);
        }
    }

    /**
     * 배치 변환 (성능 최적화)
     */
    transformBatch(messages: RedisStockMessage[]): ClientStockData[] {
        const startTime = Date.now();
        const results: ClientStockData[] = [];

        for (const message of messages) {
            try {
                results.push(this.transformToClientData(message));
            } catch (error) {
                this.logger.warn('Skipping invalid message in batch', {
                    stock_code: message.stock_code,
                    error: (error as Error).message
                });
            }
        }

        this.logger.performance('Batch transform', Date.now() - startTime, {
            input_count: messages.length,
            output_count: results.length,
            success_rate: (results.length / messages.length * 100).toFixed(1) + '%'
        });

        return results;
    }

    /**
     * 안전한 숫자 변환
     */
    private safeNumber(value: any, fallback: number = 0): number {
        if (typeof value === 'number' && !isNaN(value) && isFinite(value)) {
            return value;
        }
        
        if (typeof value === 'string') {
            const parsed = Number(value);
            if (!isNaN(parsed) && isFinite(parsed)) {
                return parsed;
            }
        }
        
        return fallback;
    }

    /**
     * 종목코드 추출
     */
    private extractStockCode(message: RedisStockMessage): string {
        const code = message.data?.code || message.stock_code;
        
        if (!code || typeof code !== 'string' || code.trim().length === 0) {
            throw new Error('Invalid or missing stock code');
        }
        
        return code.trim();
    }

    /**
     * 클라이언트 데이터 검증
     */
    private validateClientData(data: ClientStockData): void {
        const errors: string[] = [];

        if (!data.c || data.c === 'UNKNOWN') {
            errors.push('Invalid stock code');
        }

        if (data.p <= 0) {
            errors.push(`Invalid price: ${data.p}`);
        }

        if (!isFinite(data.r)) {
            errors.push(`Invalid rate: ${data.r}`);
        }

        if (data.vt < 0) {
            errors.push(`Invalid volume tick: ${data.vt}`);
        }

        if (data.vl < 0) {
            errors.push(`Invalid volume total: ${data.vl}`);
        }

        if (errors.length > 0) {
            throw new Error(`Validation failed: ${errors.join(', ')}`);
        }
    }

    /**
     * 변환 실패 시 폴백 데이터 생성
     */
    private createFallbackData(message: RedisStockMessage): ClientStockData {
        this.logger.warn('Using fallback data', {
            stock_code: message.stock_code
        });

        return {
            c: message.stock_code || 'UNKNOWN',
            p: 0,
            r: 0,
            vt: 0,
            vl: 0,
            t: Date.now(),
        };
    }

    /**
     * 데이터 품질 통계
     */
    getTransformationStats(): {
        total_processed: number;
        successful: number;
        failed: number;
        success_rate: string;
    } {
        // 실제 구현에서는 내부 카운터를 사용
        // MVP에서는 단순한 더미 데이터 반환
        return {
            total_processed: 0,
            successful: 0,
            failed: 0,
            success_rate: '100%'
        };
    }
}
