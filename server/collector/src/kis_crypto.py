from base64 import b64decode
from Crypto.Cipher import AES 
from Crypto.Util.Padding import unpad 

def aes_cbc_base64_dec(key: str, iv: str, cipher_text: str) -> str:
    """KIS 실시간 데이터를 AES-256 CBC 방식으로 복호화합니다."""
    if key is None or iv is None:
        # 이 예외는 __subscriber의 복호화 키 저장 로직이 실패했을 때 발생합니다.
        raise AttributeError("복호화 키(key)와 IV(iv)가 설정되지 않았습니다.")

    # key와 iv는 UTF-8로 인코딩
    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    
    # base64 디코딩 후 복호화
    decrypted_bytes = cipher.decrypt(b64decode(cipher_text))
    
    # 패딩 제거 및 문자열 디코딩 후 반환
    return bytes.decode(unpad(decrypted_bytes, AES.block_size))