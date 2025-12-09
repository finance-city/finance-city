import json
from collections import namedtuple
from typing import Callable, Dict, Any, List, Optional, Union

open_map: Dict[str, Any] = {}
data_map: Dict[str, Any] = {}

def add_open_map(
        name: str,
        request: Callable,
        data: Union[str, List[str]],
        kwargs: Optional[Dict[str, Any]] = None,
):
    """웹소켓 연결 전에 구독할 요청(TRID) 정보를 등록합니다."""
    if open_map.get(name) is None:
        open_map[name] = {
            "func": request,
            "items": [],
            "kwargs": kwargs,
        }

    if isinstance(data, list):
        open_map[name]["items"].extend(data)
    elif isinstance(data, str):
        open_map[name]["items"].append(data)


def add_data_map(
        tr_id: str,
        columns: Optional[List[str]] = None,
        encrypt: Optional[str] = None,
        key: Optional[str] = None,
        iv: Optional[str] = None,
):
    """TR ID별 데이터 컬럼 정보 및 복호화 키를 저장합니다."""
    if data_map.get(tr_id) is None:
        data_map[tr_id] = {"columns": [], "encrypt": "N", "key": None, "iv": None}

    if columns is not None:
        data_map[tr_id]["columns"] = columns

    if encrypt is not None:
        data_map[tr_id]["encrypt"] = encrypt

    if key is not None:
        data_map[tr_id]["key"] = key

    if iv is not None:
        data_map[tr_id]["iv"] = iv


# --- System Response Parser ---

def system_resp(data: str) -> Any:
    """
    서버 시스템 응답(SUBSCRIBE SUCCESS, PINGPONG 등)을 파싱하고
    복호화 키(iv, key)를 추출합니다.
    """
    isPingPong = False
    isUnSub = False
    isOk = False
    tr_msg = None
    tr_key = None
    encrypt, iv, ekey = None, None, None

    try:
        rdic = json.loads(data)
    except json.JSONDecodeError:
        return namedtuple('SysMsg', [])()

    tr_id = rdic["header"].get("tr_id")
    if tr_id != "PINGPONG":
        tr_key = rdic["header"].get("tr_key")
        encrypt = rdic["header"].get("encrypt")
    
    if rdic.get("body") is not None:
        isOk = True if rdic["body"].get("rt_cd") == "0" else False
        tr_msg = rdic["body"].get("msg1")
        
        if "output" in rdic["body"]:
            iv = rdic["body"]["output"].get("iv")
            ekey = rdic["body"]["output"].get("key")
            
        isUnSub = True if tr_msg and tr_msg.startswith("UNSUB") else False
        
    else:
        isPingPong = True if tr_id == "PINGPONG" else False

    nt2 = namedtuple(
        "SysMsg",
        ["isOk", "tr_id", "tr_key", "isUnSub", "isPingPong", "tr_msg", "iv", "ekey", "encrypt"],
    )
    d = {
        "isOk": isOk,
        "tr_id": tr_id,
        "tr_key": tr_key,
        "tr_msg": tr_msg,
        "isUnSub": isUnSub,
        "isPingPong": isPingPong,
        "iv": iv,
        "ekey": ekey,
        "encrypt": encrypt,
    }

    return nt2(**d)