# data_fetch.py

from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple, List
import json
from auth import get_access_token, get_approval_key


@dataclass
class RequestHeader:
    approval_key: str
    custtype: str
    tr_type: str
    content_type: str = "utf-8"

@dataclass
class RequestInput:
    tr_id: str
    tr_key: str

@dataclass
class RequestBody:
    input: RequestInput

@dataclass
class RequestPacket:
    header: RequestHeader
    body: RequestBody

    def to_json_packet(self) -> str:
        """
        KIS가 요구하는 정확한 중첩 구조의 JSON 문자열을 생성하고
        'content_type'을 'content-type'으로 변경한 후 줄바꿈 문자(\n)를 추가하여 반환합니다.
        """
        data_dict: Dict[str, Any] = asdict(self)
        
        header_dict = data_dict['header']
        if 'content_type' in header_dict:
            content_value = header_dict.pop('content_type')
            header_dict['content-type'] = content_value
            
        return json.dumps(data_dict) + '\n'

def get_realtime_request(tr_type: str, tr_key: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    NXT 애프터마켓 체결가 구독 요청 메시지(H0NXCNT0)를 생성합니다.
    """
    token = get_access_token()
    approval_key = get_approval_key(token)
    
    header = RequestHeader(
        approval_key=approval_key,
        custtype="P",
        tr_type=tr_type,
    )
    request_input = RequestInput(
        tr_id="H0NXCNT0",
        tr_key=tr_key
    )
    body = RequestBody(input=request_input)
    
    packet = RequestPacket(header=header, body=body)
    
    msg_dict = asdict(packet) 
    
    # H0NXCNT0 필드 리스트 (NXT 애프터마켓 체결 정보)
    columns = [
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
    ]
    
    return msg_dict, columns