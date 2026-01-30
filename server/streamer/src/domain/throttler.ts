// domain/throttler.ts - 배치 처리 도메인 로직

import type { ClientStockData, IThrottler } from '../types/index.js';

export class Throttler implements IThrottler {
    // 메모리 저장소: Key(종목코드) -> Value(주식데이터)
    private readonly buffer = new Map<string, ClientStockData>();
    private readonly throttleInterval: number;

    constructor(throttleInterval: number = 1000) {
        this.throttleInterval = throttleInterval; // 기본 1초
    }

    push(stockCode: string, data: ClientStockData): void {
        // 1. 이미 버퍼에 있는 종목인지 확인
        if (this.buffer.has(stockCode)) {
            const existing = this.buffer.get(stockCode)!;

            // 2. 병합 로직 (Merge Strategy)
            existing.p = data.p;        // 가격: 최신값으로 덮어쓰기
            existing.r = data.r;        // 등락률: 최신값으로 덮어쓰기
            existing.vl = data.vl;      // 누적거래량: 최신값으로 덮어쓰기
            existing.t = data.t || Date.now(); // 타임스탬프: 최신값으로 덮어쓰기
            
            // 순간 체결량은 계속 더해준다 (파티클용)
            existing.vt += data.vt;

        } else {
            // 3. 없으면 새로 등록 (객체 복사해서 저장)
            this.buffer.set(stockCode, { 
                ...data,
                t: data.t || Date.now()
            });
        }
    }

    flush(): ClientStockData[] {
        if (this.buffer.size === 0) {
            return [];
        }

        // 1. Map을 순회하며 전송용 배열로 변환
        const updates: ClientStockData[] = Array.from(this.buffer.values());

        // 2. 버퍼 비우기 (다음 턴을 위해)
        this.buffer.clear();

        return updates;
    }

    shouldUpdate(stockCode: string, newData: ClientStockData): boolean {
        // 현재는 throttleInterval 기반으로 판단하지만,
        // 실제로는 push에서 병합되므로 항상 true 반환
        return true;
    }
}
