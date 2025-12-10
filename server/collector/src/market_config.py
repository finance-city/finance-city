# market_config.py

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import time
from enum import Enum


class MarketType(Enum):
    KRX_REGULAR = "krx_regular"
    KRX_AFTER = "krx_after"
    US_REGULAR = "us_regular"
    US_AFTER = "us_after"


class DataType(Enum):
    EXECUTION = "execution"  # 체결가
    ORDERBOOK = "orderbook"  # 호가


@dataclass
class MarketSession:
    """시장 세션 정보"""
    start_time: time
    end_time: time
    market_type: MarketType
    tr_id: str
    data_type: DataType


@dataclass
class FieldMapping:
    """필드 매핑 정보"""
    tr_id: str
    columns: List[str]
    essential_fields: Dict[str, str]  # 내부 필드명 -> 외부 필드명 매핑


# KRX 시장 세션 정의
KRX_SESSIONS = [
    MarketSession(
        start_time=time(9, 0),
        end_time=time(15, 30),
        market_type=MarketType.KRX_REGULAR,
        tr_id="H0STCNT0",
        data_type=DataType.EXECUTION
    ),
    MarketSession(
        start_time=time(16, 0),
        end_time=time(18, 0),
        market_type=MarketType.KRX_AFTER,
        tr_id="H0NXCNT0", 
        data_type=DataType.EXECUTION
    )
]

# 미국 시장 세션 정의 - 24시간 활성화
US_SESSIONS = [
    MarketSession(
        start_time=time(0, 0),    # 24시간 활성화 (00:00)
        end_time=time(23, 59),    # 24시간 활성화 (23:59)
        market_type=MarketType.US_REGULAR,
        tr_id="HDFSCNT0",  # 해외주식 실시간 지연체결가
        data_type=DataType.EXECUTION
    )
]

# 필드 매핑 정의
FIELD_MAPPINGS = {
    # 국내 주식 정규장 실시간 체결가(KRX)
    "H0STCNT0": FieldMapping(
        tr_id="H0STCNT0",
        columns=[
            "MKSC_SHRN_ISCD", "STCK_CNTG_HOUR", "STCK_PRPR", "PRDY_VRSS_SIGN",
            "PRDY_VRSS", "PRDY_CTRT", "WGHN_AVRG_STCK_PRC", "STCK_OPRC",
            "STCK_HGPR", "STCK_LWPR", "ASKP1", "BIDP1", "CNTG_VOL", "ACML_VOL",
            "ACML_TR_PBMN", "SELN_CNTG_CSNU", "SHNU_CNTG_CSNU", "NTBY_CNTG_CSNU",
            "CTTR", "SELN_CNTG_SMTN", "SHNU_CNTG_SMTN", "CCLD_DVSN", "SHNU_RATE",
            "PRDY_VOL_VRSS_ACML_VOL_RATE", "OPRC_HOUR", "OPRC_VRSS_PRPR_SIGN",
            "OPRC_VRSS_PRPR", "HGPR_HOUR", "HGPR_VRSS_PRPR_SIGN", "HGPR_VRSS_PRPR",
            "LWPR_HOUR", "LWPR_VRSS_PRPR_SIGN", "LWPR_VRSS_PRPR", "BSOP_DATE",
            "NEW_MKOP_CLS_CODE", "TRHT_YN", "ASKP_RSQN1", "BIDP_RSQN1",
            "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "VOL_TNRT",
            "PRDY_SMNS_HOUR_ACML_VOL", "PRDY_SMNS_HOUR_ACML_VOL_RATE",
            "HOUR_CLS_CODE", "MRKT_TRTM_CLS_CODE", "VI_STND_PRC"
        ],
        essential_fields={
            "stock_code": "MKSC_SHRN_ISCD",
            "price": "STCK_PRPR", 
            "time": "STCK_CNTG_HOUR",
            "volume": "CNTG_VOL",
            "acc_volume": "ACML_VOL"
        }
    ),
    # 국내 주식 애프터마켓 실시간 체결가(NXT)
    "H0NXCNT0": FieldMapping(
        tr_id="H0NXCNT0", 
        columns=[
            "MKSC_SHRN_ISCD", "STCK_CNTG_HOUR", "STCK_PRPR", "PRDY_VRSS_SIGN",
            "PRDY_VRSS", "PRDY_CTRT", "WGHN_AVRG_STCK_PRC", "STCK_OPRC",
            "STCK_HGPR", "STCK_LWPR", "ASKP1", "BIDP1", "CNTG_VOL", "ACML_VOL",
            "ACML_TR_PBMN", "SELN_CNTG_CSNU", "SHNU_CNTG_CSNU", "NTBY_CNTG_CSNU",
            "CTTR", "SELN_CNTG_SMTN", "SHNU_CNTG_SMTN", "CCLD_DVSN", "SHNU_RATE",
            "PRDY_VOL_VRSS_ACML_VOL_RATE", "OPRC_HOUR", "OPRC_VRSS_PRPR_SIGN",
            "OPRC_VRSS_PRPR", "HGPR_HOUR", "HGPR_VRSS_PRPR_SIGN", "HGPR_VRSS_PRPR",
            "LWPR_HOUR", "LWPR_VRSS_PRPR_SIGN", "LWPR_VRSS_PRPR", "BSOP_DATE",
            "NEW_MKOP_CLS_CODE", "TRHT_YN", "ASKP_RSQN1", "BIDP_RSQN1",
            "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "VOL_TNRT",
            "PRDY_SMNS_HOUR_ACML_VOL", "PRDY_SMNS_HOUR_ACML_VOL_RATE",
            "HOUR_CLS_CODE", "MRKT_TRTM_CLS_CODE", "VI_STND_PRC"
        ],
        essential_fields={
            "stock_code": "MKSC_SHRN_ISCD",
            "price": "STCK_PRPR",
            "time": "STCK_CNTG_HOUR", 
            "volume": "CNTG_VOL",
            "acc_volume": "ACML_VOL"
        }
    ),
    # 해외 주식 실시간 지연 체결가
    "HDFSCNT0": FieldMapping(
        tr_id="HDFSCNT0",
        columns=[
            "RSYM", "SYMB", "ZDIV", "TYMD", "XYMD", "XHMS", "KYMD", "KHMS",
            "OPEN", "HIGH", "LOW", "LAST", "SIGN", "DIFF", "RATE", "PBID", 
            "PASK", "VBID", "VASK", "EVOL", "TVOL", "TAMT", "BIVL", "ASVL",
            "STRN", "MTYP"
        ],
        essential_fields={
            "stock_code": "SYMB",
            "price": "LAST",
            "time": "XHMS",
            "volume": "EVOL",
            "acc_volume": "TVOL",
            "open": "OPEN",
            "high": "HIGH", 
            "low": "LOW",
            "market_status": "MTYP"
        }
    )
}
