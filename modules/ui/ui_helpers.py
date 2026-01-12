"""UI 헬퍼 함수 모듈 - 여러 UI 모듈에서 공유 사용

성능 최적화:
- @st.cache_data로 반복 계산 방지
- 메모리 효율화
"""

import gc
import streamlit as st
from functools import lru_cache


def get_active_doc():
    """현재 선택된 문서 객체를 반환합니다."""
    if not st.session_state.active_doc_id:
        return None
    for d in st.session_state.docs:
        if d.get("id") == st.session_state.active_doc_id:
            return d
    return None


@st.cache_data(max_entries=10, ttl=600)
def get_person_keys_for_doc(doc_id: str, parsed_data_len: int) -> list:
    """문서에서 사람 키 목록을 반환합니다.
    
    캐시 파라미터:
    - max_entries=10: 최대 10개 문서 캐시
    - ttl=600: 10분 후 캐시 만료
    """
    # session_state에서 실제 doc 가져오기
    doc = next((d for d in st.session_state.docs if d.get("id") == doc_id), None)
    if not doc:
        return []
    
    seen = set()
    keys = []
    for record in doc.get("parsed_data", []):
        person = record.get("customer_name") or "미상"
        key = f"{doc['id']}::{person}"
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def iter_person_entries():
    """모든 문서의 사람 항목을 반복합니다.
    
    성능 최적화: 캐시 키 기반 메모이제이션
    """
    # 캐시 키 생성 (docs 상태 기반)
    cache_key = _get_docs_cache_key()
    
    # 캐시된 결과 확인
    if 'person_entries_cache' not in st.session_state:
        st.session_state.person_entries_cache = {}
    
    if cache_key in st.session_state.person_entries_cache:
        return st.session_state.person_entries_cache[cache_key]
    
    entries = []
    for doc in st.session_state.docs:
        counts = {}
        for record in doc.get("parsed_data", []):
            person = record.get("customer_name") or "미상"
            key = f"{doc['id']}::{person}"
            if key not in counts:
                counts[key] = {
                    "key": key,
                    "doc_id": doc["id"],
                    "doc_name": doc["name"],
                    "person_name": person,
                    "record_count": 0,
                }
            counts[key]["record_count"] += 1
        entries.extend(counts.values())
    
    # 캐시 저장 (최대 5개 캐시 유지)
    if len(st.session_state.person_entries_cache) > 5:
        st.session_state.person_entries_cache.clear()
    st.session_state.person_entries_cache[cache_key] = entries
    
    return entries


def _get_docs_cache_key() -> str:
    """문서 상태 기반 캐시 키 생성"""
    if not st.session_state.docs:
        return "empty"
    return "_".join(
        f"{d['id']}:{len(d.get('parsed_data', []))}"
        for d in st.session_state.docs
    )


def ensure_active_person():
    """활성 사람을 확인하고 설정합니다."""
    active_doc = get_active_doc()
    if not active_doc:
        st.session_state.active_person_key = None
        return None

    key = st.session_state.get("active_person_key")
    if key and key.startswith(f"{active_doc['id']}::"):
        return key

    doc_keys = get_person_keys_for_doc(active_doc['id'], len(active_doc.get('parsed_data', [])))
    if doc_keys:
        st.session_state.active_person_key = doc_keys[0]
        return doc_keys[0]

    st.session_state.active_person_key = None
    return None


def get_active_person_records():
    """활성 사람의 기록을 반환합니다."""
    person_key = ensure_active_person()
    if not person_key or "::" not in person_key:
        return None, None, []
    doc_id, person_name = person_key.split("::", 1)
    doc = next((d for d in st.session_state.docs if d["id"] == doc_id), None)
    if not doc:
        return None, None, []
    person_records = [
        r for r in doc.get("parsed_data", [])
        if (r.get("customer_name") or "미상") == person_name
    ]
    return doc, person_name, person_records


def person_checkbox_key(person_key: str) -> str:
    """사람 체크박스 키를 반환합니다."""
    import hashlib
    return f"person_cb_{hashlib.sha1(person_key.encode('utf-8')).hexdigest()[:8]}"


def select_person(person_key: str, doc_id: str):
    """사람을 선택합니다."""
    target = person_checkbox_key(person_key)
    for key in list(st.session_state.keys()):
        if key.startswith("person_cb_"):
            st.session_state[key] = (key == target)
    st.session_state.active_person_key = person_key
    st.session_state.active_doc_id = doc_id


def get_person_done(key: str) -> bool:
    """사람 완료 상태를 반환합니다."""
    return st.session_state.person_completion.get(key, False)


def set_person_done(key: str, value: bool):
    """사람 완료 상태를 설정합니다."""
    st.session_state.person_completion[key] = value


def clear_caches():
    """모든 UI 캐시 정리 (메모리 해제용)"""
    if 'person_entries_cache' in st.session_state:
        st.session_state.person_entries_cache.clear()
    gc.collect()


def invalidate_person_cache():
    """사람 목록 캐시 무효화"""
    if 'person_entries_cache' in st.session_state:
        st.session_state.person_entries_cache.clear()
