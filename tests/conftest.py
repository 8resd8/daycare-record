"""Pytest fixtures for testing without database and external dependencies."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List, Optional, Any


class MockCursor:
    """Mock database cursor for testing."""
    
    def __init__(self):
        self._results: List[Dict] = []
        self._single_result: Optional[Dict] = None
        self.lastrowid: int = 1
        self.rowcount: int = 1
        self._executed_queries: List[tuple] = []
    
    def execute(self, query: str, params: tuple = None):
        self._executed_queries.append((query, params))
    
    def executemany(self, query: str, params_list: List[tuple]):
        for params in params_list:
            self._executed_queries.append((query, params))
    
    def fetchall(self) -> List[Dict]:
        return self._results
    
    def fetchone(self) -> Optional[Dict]:
        return self._single_result
    
    def close(self):
        pass
    
    def set_results(self, results: List[Dict]):
        """Set results for fetchall()."""
        self._results = results
    
    def set_single_result(self, result: Optional[Dict]):
        """Set result for fetchone()."""
        self._single_result = result
    
    def get_executed_queries(self) -> List[tuple]:
        """Get all executed queries for verification."""
        return self._executed_queries
    
    def clear_queries(self):
        """Clear executed queries."""
        self._executed_queries = []


class MockConnection:
    """Mock database connection for testing."""
    
    def __init__(self):
        self._cursor = MockCursor()
        self._committed = False
        self._rolled_back = False
    
    def cursor(self, dictionary: bool = True) -> MockCursor:
        return self._cursor
    
    def commit(self):
        self._committed = True
    
    def rollback(self):
        self._rolled_back = True
    
    def close(self):
        pass
    
    @property
    def mock_cursor(self) -> MockCursor:
        return self._cursor


class MockAIClient:
    """Mock AI client for testing without OpenAI API calls."""
    
    def __init__(self):
        self._response = None
    
    def set_response(self, response: str):
        """Set the mock response content."""
        self._response = response
    
    def chat_completion(self, model: str, messages: list, **kwargs) -> MagicMock:
        """Mock chat completion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = self._response or '{}'
        return mock_response


@pytest.fixture
def mock_cursor():
    """Provide a mock cursor for direct cursor testing."""
    return MockCursor()


@pytest.fixture
def mock_connection():
    """Provide a mock database connection."""
    return MockConnection()


@pytest.fixture
def mock_ai_client():
    """Provide a mock AI client."""
    return MockAIClient()


@pytest.fixture
def mock_db_query(mock_connection):
    """Patch db_query context manager."""
    from contextlib import contextmanager
    
    @contextmanager
    def _mock_db_query(dictionary: bool = True):
        yield mock_connection.mock_cursor
    
    with patch('modules.db_connection.db_query', _mock_db_query):
        yield mock_connection


@pytest.fixture
def mock_db_transaction(mock_connection):
    """Patch db_transaction context manager."""
    from contextlib import contextmanager
    
    @contextmanager
    def _mock_db_transaction(dictionary: bool = False):
        yield mock_connection.mock_cursor
    
    with patch('modules.db_connection.db_transaction', _mock_db_transaction):
        yield mock_connection


@pytest.fixture
def mock_db(mock_connection):
    """Patch both db_query and db_transaction."""
    from contextlib import contextmanager
    
    @contextmanager
    def _mock_db_query(dictionary: bool = True):
        yield mock_connection.mock_cursor
    
    @contextmanager
    def _mock_db_transaction(dictionary: bool = False):
        yield mock_connection.mock_cursor
    
    with patch('modules.db_connection.db_query', _mock_db_query):
        with patch('modules.db_connection.db_transaction', _mock_db_transaction):
            yield mock_connection


@pytest.fixture
def sample_customer_data() -> Dict:
    """Sample customer data for testing."""
    return {
        'customer_id': 1,
        'name': '홍길동',
        'birth_date': '1950-01-01',
        'gender': 'M',
        'recognition_no': 'L1234567890',
        'benefit_start_date': '2024-01-01',
        'grade': '3등급'
    }


@pytest.fixture
def sample_evaluation_data() -> Dict:
    """Sample AI evaluation data for testing."""
    return {
        'ai_eval_id': 1,
        'record_id': 100,
        'category': '신체',
        'oer_fidelity': 'O',
        'specificity_score': 'O',
        'grammar_score': 'O',
        'grade_code': '우수',
        'reason_text': '평가 사유',
        'suggestion_text': '수정 제안',
        'original_text': '원본 텍스트'
    }


@pytest.fixture
def sample_employee_evaluation_data() -> Dict:
    """Sample employee evaluation data for testing."""
    return {
        'emp_eval_id': 1,
        'record_id': 100,
        'target_user_id': 1,
        'evaluator_user_id': 2,
        'category': '신체',
        'evaluation_type': '누락',
        'score': 1,
        'comment': '테스트 코멘트',
        'evaluation_date': '2024-01-15'
    }


@pytest.fixture
def sample_daily_record() -> Dict:
    """Sample daily info record for testing."""
    return {
        'record_id': 100,
        'customer_id': 1,
        'date': '2024-01-15',
        'customer_name': '홍길동',
        'physical_note': '신체활동 특이사항 테스트',
        'cognitive_note': '인지관리 특이사항 테스트',
        'nursing_note': '간호관리 특이사항',
        'functional_note': '기능회복 특이사항'
    }


@pytest.fixture
def sample_ai_response() -> str:
    """Sample AI response JSON for testing."""
    return '''{
        "original_physical_evaluation": {
            "oer_fidelity": "O",
            "specificity": "O",
            "grammar": "O"
        },
        "original_cognitive_evaluation": {
            "oer_fidelity": "O",
            "specificity": "X",
            "grammar": "O"
        },
        "physical_candidates": [
            {"corrected_note": "수정된 신체활동 특이사항 1"},
            {"corrected_note": "수정된 신체활동 특이사항 2"},
            {"corrected_note": "수정된 신체활동 특이사항 3"}
        ],
        "cognitive_candidates": [
            {"corrected_note": "수정된 인지관리 특이사항 1"},
            {"corrected_note": "수정된 인지관리 특이사항 2"},
            {"corrected_note": "수정된 인지관리 특이사항 3"}
        ]
    }'''
