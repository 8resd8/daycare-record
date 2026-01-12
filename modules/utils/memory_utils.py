"""메모리 관리 유틸리티

메모리 관리 도구 및 성능 모드 설정.

사용법:
    from modules.utils.memory_utils import memory_cleanup, chunked_process
    
    # 대량 작업 후 메모리 정리
    memory_cleanup()
    
    # 청크 단위 처리
    for chunk in chunked_process(large_list, chunk_size=10):
        process(chunk)
    
    # 성능 모드 확인
    from modules.utils.memory_utils import is_low_memory_mode, get_performance_config
    if is_low_memory_mode():
        print("저사양 모드")
"""

import gc
import sys
import os
from typing import TypeVar, Iterator, List, Callable, Any, Dict
from contextlib import contextmanager

# ============================================================================
# 성능 모드 설정 (개발/테스트용)
# ============================================================================
# OPTIMIZE_MODE 값으로 성능 최적화 모드 제어:
#   0 = 기본 모드 (최적화 없음, 고사양)
#   1 = 최적화 모드 (저사양 최적화 적용)
#   None = 자동 감지 (시스템 메모리 기반, 4GB 미만이면 최적화)
# ============================================================================
OPTIMIZE_MODE = None  # 개발시 0 또는 1로 변경하여 테스트

# 전역 변수
_memory_mode = None
_memory_info = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

T = TypeVar('T')


def get_system_memory_info() -> Dict[str, Any]:
    """시스템 메모리 정보를 반환합니다."""
    global _memory_info
    
    if _memory_info is not None:
        return _memory_info
    
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        _memory_info = {
            "total_gb": vm.total / (1024**3),
            "available_gb": vm.available / (1024**3),
            "percent_used": vm.percent,
            "has_psutil": True
        }
    else:
        # psutil이 없는 경우 환경변수나 기본값 사용
        total_gb = float(os.environ.get("SYSTEM_MEMORY_GB", "4.0"))
        _memory_info = {
            "total_gb": total_gb,
            "available_gb": total_gb * 0.3,
            "percent_used": 70.0,
            "has_psutil": False
        }
    
    return _memory_info


def is_low_memory_mode() -> bool:
    """저사양 모드인지 확인합니다.
    
    우선순위:
    1. OPTIMIZE_MODE 변수 (0=고사양, 1=저사양, None=자동)
    2. 환경변수 LOW_MEMORY_MODE (true/false)
    3. 시스템 메모리 자동 감지 (4GB 미만)
    """
    global _memory_mode
    
    # 이미 결정된 모드가 있으면 반환
    if _memory_mode is not None:
        return _memory_mode == "low"
    
    # 1. 코드 변수 확인 (개발/테스트용)
    if OPTIMIZE_MODE is not None:
        _memory_mode = "low" if OPTIMIZE_MODE == 1 else "high"
        return _memory_mode == "low"
    
    # 2. 환경변수 확인
    env_mode = os.environ.get("LOW_MEMORY_MODE", "").lower()
    if env_mode in ("true", "1", "yes"):
        _memory_mode = "low"
        return True
    elif env_mode in ("false", "0", "no"):
        _memory_mode = "high"
        return False
    
    # 3. 시스템 메모리 자동 감지
    memory_info = get_system_memory_info()
    if memory_info["total_gb"] < 4.0:
        _memory_mode = "low"
        return True
    else:
        _memory_mode = "high"
        return False


def get_performance_config() -> Dict[str, Any]:
    """현재 메모리 모드에 맞는 성능 설정을 반환합니다."""
    if is_low_memory_mode():
        return {
            # 저사양 모드 (4GB 미만 또는 OPTIMIZE_MODE=1)
            "mode": "low_memory",
            "db_pool_size": 3,
            "thread_max_workers": 2,
            "cache_max_entries": 5,
            "cache_ttl": 300,  # 5분
            "batch_size_small": 3,
            "batch_size_medium": 5,
            "batch_size_large": 10,
            "gc_threshold": (200, 5, 5),
            "enable_aggressive_gc": True,
        }
    else:
        return {
            # 고사양 모드 (4GB 이상 또는 OPTIMIZE_MODE=0)
            "mode": "high_performance",
            "db_pool_size": 5,
            "thread_max_workers": 4,
            "cache_max_entries": 20,
            "cache_ttl": 600,  # 10분
            "batch_size_small": 10,
            "batch_size_medium": 20,
            "batch_size_large": 50,
            "gc_threshold": (700, 10, 10),
            "enable_aggressive_gc": False,
        }


def configure_gc_for_mode():
    """현재 모드에 맞게 GC를 설정합니다."""
    config = get_performance_config()
    gc.set_threshold(*config["gc_threshold"])
    if config["enable_aggressive_gc"]:
        gc.collect()


def get_cache_params() -> Dict[str, Any]:
    """캐시 파라미터를 반환합니다."""
    config = get_performance_config()
    return {
        "max_entries": config["cache_max_entries"],
        "ttl": config["cache_ttl"]
    }


def get_batch_size(record_count: int) -> int:
    """레코드 수에 따른 동적 배치 크기를 반환합니다."""
    config = get_performance_config()
    
    if record_count < 50:
        return config["batch_size_small"]
    elif record_count < 200:
        return config["batch_size_medium"]
    else:
        return config["batch_size_large"]


def get_thread_max_workers() -> int:
    """ThreadPoolExecutor 최대 워커 수를 반환합니다."""
    return get_performance_config()["thread_max_workers"]


def get_db_pool_size() -> int:
    """DB 커넥션 풀 크기를 반환합니다."""
    return get_performance_config()["db_pool_size"]


# 앱 시작 시 GC 설정
configure_gc_for_mode()


def memory_cleanup(full: bool = False) -> None:
    """메모리 정리 수행
    
    Args:
        full: True면 3세대 모두 수집 (더 철저하지만 느림)
    """
    if full:
        # 3세대 모두 수집
        gc.collect(0)
        gc.collect(1)
        gc.collect(2)
    else:
        # 기본 수집
        gc.collect()


def chunked_process(items: List[T], chunk_size: int = 10) -> Iterator[List[T]]:
    """리스트를 청크 단위로 나누어 반환 (Generator)
    
    메모리 효율적인 대량 데이터 처리를 위해 사용.
    
    Args:
        items: 처리할 전체 리스트
        chunk_size: 청크 크기 (기본값: 10, 1GB RAM 최적화)
        
    Yields:
        청크 단위 리스트
        
    Example:
        for chunk in chunked_process(records, 10):
            save_batch(chunk)
            gc.collect()  # 배치마다 메모리 정리
    """
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


@contextmanager
def memory_scope():
    """메모리 스코프 컨텍스트 매니저
    
    블록 종료 시 자동으로 GC 수행.
    
    Usage:
        with memory_scope():
            large_data = process_large_file()
            # 블록 끝에서 자동 GC
    """
    try:
        yield
    finally:
        gc.collect()


def get_memory_usage() -> dict:
    """현재 메모리 사용량 정보 반환 (디버깅용)"""
    return {
        'gc_counts': gc.get_count(),
        'gc_threshold': gc.get_threshold(),
        'objects_tracked': len(gc.get_objects()),
    }


def optimize_gc_for_low_memory():
    """저메모리 환경을 위한 GC 최적화 설정
    
    1GB RAM 환경에서 더 자주 GC를 수행하도록 설정.
    """
    # 기본값: (700, 10, 10) -> (400, 5, 5)
    gc.set_threshold(400, 5, 5)


def clear_large_objects(*objects):
    """대용량 객체 명시적 해제
    
    Args:
        *objects: 해제할 객체들
        
    Usage:
        clear_large_objects(large_df, parsed_data, temp_list)
    """
    for obj in objects:
        try:
            if hasattr(obj, 'clear'):
                obj.clear()
            del obj
        except:
            pass
    gc.collect()


class ChunkedProcessor:
    """청크 단위 처리기 클래스
    
    대량 데이터를 메모리 효율적으로 처리하기 위한 헬퍼.
    
    Usage:
        processor = ChunkedProcessor(chunk_size=10, gc_interval=5)
        for result in processor.process(records, save_record):
            total += result
    """
    
    def __init__(self, chunk_size: int = 10, gc_interval: int = 5):
        """
        Args:
            chunk_size: 청크 크기
            gc_interval: GC 수행 간격 (청크 단위)
        """
        self.chunk_size = chunk_size
        self.gc_interval = gc_interval
        self._processed_chunks = 0
    
    def process(self, items: List[T], processor_func: Callable[[List[T]], Any]) -> Iterator[Any]:
        """청크 단위로 처리하며 결과 반환
        
        Args:
            items: 처리할 전체 리스트
            processor_func: 청크를 처리할 함수
            
        Yields:
            각 청크 처리 결과
        """
        for chunk in chunked_process(items, self.chunk_size):
            result = processor_func(chunk)
            self._processed_chunks += 1
            
            # GC 간격마다 메모리 정리
            if self._processed_chunks % self.gc_interval == 0:
                gc.collect()
            
            yield result
        
        # 마지막 정리
        gc.collect()
        self._processed_chunks = 0
