"""메모리 유틸리티 테스트

memory_utils 모듈의 모든 함수/클래스 커버리지 확보.
FastAPI 분리 시 백엔드 서비스에서도 동일하게 사용될 유틸리티입니다.
"""

import gc
import pytest
from modules.utils.memory_utils import (
    memory_cleanup,
    chunked_process,
    memory_scope,
    get_memory_usage,
    clear_large_objects,
    ChunkedProcessor,
)


class TestMemoryCleanup:
    """memory_cleanup 함수 테스트"""

    def test_cleanup_default_calls_gc(self):
        """기본 호출 시 gc.collect 실행 (예외 없음)"""
        memory_cleanup()  # 예외 없이 실행되면 OK

    def test_cleanup_full_collects_all_generations(self):
        """full=True 시 3세대 모두 수집"""
        memory_cleanup(full=True)  # 예외 없이 실행되면 OK

    def test_cleanup_full_false_is_default(self):
        """full=False가 기본값"""
        memory_cleanup(full=False)  # 예외 없이 실행되면 OK


class TestChunkedProcess:
    """chunked_process 제너레이터 테스트"""

    def test_basic_chunking(self):
        """리스트를 청크로 분할"""
        items = list(range(10))
        chunks = list(chunked_process(items, chunk_size=3))

        assert len(chunks) == 4  # 3,3,3,1
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_exact_multiple(self):
        """청크 크기의 정확한 배수"""
        items = list(range(6))
        chunks = list(chunked_process(items, chunk_size=2))

        assert len(chunks) == 3
        assert chunks[0] == [0, 1]
        assert chunks[2] == [4, 5]

    def test_empty_list(self):
        """빈 리스트 처리"""
        chunks = list(chunked_process([], chunk_size=5))
        assert chunks == []

    def test_chunk_size_larger_than_list(self):
        """청크 크기가 리스트보다 클 때"""
        items = [1, 2, 3]
        chunks = list(chunked_process(items, chunk_size=10))

        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_default_chunk_size(self):
        """기본 청크 크기(10) 동작"""
        items = list(range(25))
        chunks = list(chunked_process(items))

        assert len(chunks) == 3  # 10,10,5
        assert len(chunks[0]) == 10
        assert len(chunks[2]) == 5

    def test_returns_generator(self):
        """제너레이터를 반환"""
        import types
        result = chunked_process([1, 2, 3], chunk_size=2)
        assert isinstance(result, types.GeneratorType)


class TestMemoryScope:
    """memory_scope 컨텍스트 매니저 테스트"""

    def test_basic_usage(self):
        """정상 사용 시 예외 없이 실행"""
        with memory_scope():
            data = list(range(100))
        # 블록 종료 후 GC 완료

    def test_exception_propagates(self):
        """예외는 그대로 전파"""
        with pytest.raises(ValueError):
            with memory_scope():
                raise ValueError("테스트 예외")

    def test_gc_runs_on_exception(self):
        """예외 발생 시에도 GC 수행 (finally 블록)"""
        try:
            with memory_scope():
                raise RuntimeError("강제 에러")
        except RuntimeError:
            pass
        # 예외 이후에도 문제 없음


class TestGetMemoryUsage:
    """get_memory_usage 함수 테스트"""

    def test_returns_dict(self):
        """딕셔너리 반환"""
        result = get_memory_usage()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """필수 키 존재"""
        result = get_memory_usage()
        assert 'gc_counts' in result
        assert 'gc_threshold' in result
        assert 'objects_tracked' in result

    def test_objects_tracked_is_int(self):
        """objects_tracked는 정수"""
        result = get_memory_usage()
        assert isinstance(result['objects_tracked'], int)
        assert result['objects_tracked'] > 0

    def test_gc_counts_is_tuple(self):
        """gc_counts는 튜플"""
        result = get_memory_usage()
        assert isinstance(result['gc_counts'], tuple)


class TestClearLargeObjects:
    """clear_large_objects 함수 테스트"""

    def test_clears_list(self):
        """리스트 객체 해제 (clear 호출)"""
        large_list = list(range(1000))
        clear_large_objects(large_list)  # 예외 없이 실행

    def test_clears_dict(self):
        """딕셔너리 객체 해제"""
        large_dict = {i: i * 2 for i in range(100)}
        clear_large_objects(large_dict)  # 예외 없이 실행

    def test_clears_multiple_objects(self):
        """여러 객체 동시 해제"""
        a = [1, 2, 3]
        b = {'key': 'val'}
        c = list(range(50))
        clear_large_objects(a, b, c)  # 예외 없이 실행

    def test_clears_object_without_clear_method(self):
        """clear 메서드 없는 객체도 처리"""
        obj = object()
        clear_large_objects(obj)  # 예외 없이 실행


class TestChunkedProcessor:
    """ChunkedProcessor 클래스 테스트"""

    def test_basic_process(self):
        """청크 단위 처리 기본 동작"""
        processor = ChunkedProcessor(chunk_size=3, gc_interval=2)
        items = list(range(9))

        results = list(processor.process(items, lambda chunk: sum(chunk)))

        assert results == [3, 12, 21]  # 0+1+2, 3+4+5, 6+7+8

    def test_gc_interval(self):
        """gc_interval마다 GC 수행 (예외 없이 실행)"""
        processor = ChunkedProcessor(chunk_size=2, gc_interval=2)
        items = list(range(8))

        results = list(processor.process(items, lambda chunk: len(chunk)))

        assert len(results) == 4

    def test_empty_items(self):
        """빈 리스트 처리"""
        processor = ChunkedProcessor(chunk_size=5)
        results = list(processor.process([], lambda chunk: chunk))
        assert results == []

    def test_processed_chunks_reset_after_completion(self):
        """처리 완료 후 카운터 초기화"""
        processor = ChunkedProcessor(chunk_size=2, gc_interval=5)
        list(processor.process([1, 2, 3, 4], lambda c: c))

        assert processor._processed_chunks == 0

    def test_processor_func_receives_correct_chunks(self):
        """processor_func에 올바른 청크 전달"""
        received_chunks = []
        processor = ChunkedProcessor(chunk_size=2)
        items = [10, 20, 30, 40, 50]

        list(processor.process(items, lambda c: received_chunks.append(c) or len(c)))

        assert received_chunks[0] == [10, 20]
        assert received_chunks[1] == [30, 40]
        assert received_chunks[2] == [50]
