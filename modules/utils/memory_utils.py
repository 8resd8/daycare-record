"""메모리 관리 유틸리티

메모리 관리 도구.

사용법:
    from modules.utils.memory_utils import memory_cleanup, chunked_process

    # 대량 작업 후 메모리 정리
    memory_cleanup()
    
    # 청크 단위 처리
    for chunk in chunked_process(large_list, chunk_size=10):
        process(chunk)
"""

import gc
import sys
from typing import TypeVar, Iterator, List, Callable, Any
from contextlib import contextmanager

T = TypeVar('T')


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
