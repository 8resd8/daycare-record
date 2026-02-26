"""AnalyticsService 테스트

주간 분석 서비스 테스트 - analyzer 함수들의 래퍼 동작 및 순수 함수 로직 검증.
향후 백엔드 API(/api/analytics)로 분리 시 동일한 비즈니스 규칙이 적용됩니다.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from modules.services.analytics_service import AnalyticsService


class TestAnalyticsServiceDelegation:
    """AnalyticsService → analyzer 위임 동작 테스트"""

    @pytest.fixture
    def service(self):
        return AnalyticsService()

    def test_compute_weekly_status_delegates_to_analyzer(self, service):
        """compute_weekly_status가 analyzer.compute_weekly_status에 위임하는지 확인"""
        expected = {'scores': {}, 'ranges': (), 'data': []}

        with patch('modules.services.analytics_service.analyzer.compute_weekly_status',
                   return_value=expected) as mock_fn:
            result = service.compute_weekly_status(
                customer_name='홍길동',
                week_start_str='2024-01-08',
                customer_id=1
            )

        mock_fn.assert_called_once_with('홍길동', '2024-01-08', 1)
        assert result == expected

    def test_analyze_weekly_trend_delegates_to_analyzer(self, service):
        """analyze_weekly_trend가 analyzer.analyze_weekly_trend에 위임하는지 확인"""
        expected = {'header': {}, 'notes': {}}
        records = [{'date': date(2024, 1, 8), 'physical_note': '정상'}]

        with patch('modules.services.analytics_service.analyzer.analyze_weekly_trend',
                   return_value=expected) as mock_fn:
            result = service.analyze_weekly_trend(
                records=records,
                prev_range=(date(2024, 1, 1), date(2024, 1, 7)),
                curr_range=(date(2024, 1, 8), date(2024, 1, 14)),
                customer_id=1
            )

        mock_fn.assert_called_once()
        assert result == expected

    def test_score_text_delegates_to_analyzer(self, service):
        """score_text가 analyzer._score_text에 위임하는지 확인"""
        with patch('modules.services.analytics_service.analyzer._score_text',
                   return_value=75) as mock_fn:
            result = service.score_text('신체 상태 양호')

        mock_fn.assert_called_once_with('신체 상태 양호')
        assert result == 75

    def test_detect_meal_type_delegates_to_analyzer(self, service):
        """detect_meal_type이 analyzer._detect_meal_type에 위임하는지 확인"""
        with patch('modules.services.analytics_service.analyzer._detect_meal_type',
                   return_value='일반식') as mock_fn:
            result = service.detect_meal_type('일반식 전량 섭취')

        mock_fn.assert_called_once_with('일반식 전량 섭취')
        assert result == '일반식'

    def test_score_meal_amount_delegates_to_analyzer(self, service):
        """score_meal_amount가 analyzer._score_meal_amount에 위임하는지 확인"""
        with patch('modules.services.analytics_service.analyzer._score_meal_amount',
                   return_value=1.0) as mock_fn:
            result = service.score_meal_amount('전량 섭취')

        mock_fn.assert_called_once_with('전량 섭취')
        assert result == 1.0

    def test_meal_amount_label_delegates_to_analyzer(self, service):
        """meal_amount_label이 analyzer._meal_amount_label에 위임하는지 확인"""
        with patch('modules.services.analytics_service.analyzer._meal_amount_label',
                   return_value='전량') as mock_fn:
            result = service.meal_amount_label('전량 섭취')

        mock_fn.assert_called_once_with('전량 섭취')
        assert result == '전량'

    def test_extract_toilet_count_delegates_to_analyzer(self, service):
        """extract_toilet_count가 analyzer._extract_toilet_count에 위임하는지 확인"""
        with patch('modules.services.analytics_service.analyzer._extract_toilet_count',
                   return_value=3.0) as mock_fn:
            result = service.extract_toilet_count('소변 3회')

        mock_fn.assert_called_once_with('소변 3회')
        assert result == 3.0

    def test_parse_toilet_breakdown_delegates_to_analyzer(self, service):
        """parse_toilet_breakdown이 analyzer._parse_toilet_breakdown에 위임하는지 확인"""
        expected = {'stool': 1.0, 'urine': 3.0, 'diaper': 0.0}
        with patch('modules.services.analytics_service.analyzer._parse_toilet_breakdown',
                   return_value=expected) as mock_fn:
            result = service.parse_toilet_breakdown('소변 3회 대변 1회')

        mock_fn.assert_called_once_with('소변 3회 대변 1회')
        assert result == expected


class TestAnalyticsServiceIntegration:
    """AnalyticsService 실제 함수 통합 테스트 (순수 함수)

    DB 없이 순수 Python 로직만 검증합니다.
    """

    @pytest.fixture
    def service(self):
        return AnalyticsService()

    # ========== score_text 테스트 ==========

    def test_score_text_neutral(self, service):
        """기본 점수 50 반환"""
        result = service.score_text('')
        assert result == 50

    def test_score_text_none_returns_50(self, service):
        """None 입력 시 기본 점수 50"""
        result = service.score_text(None)
        assert result == 50

    def test_score_text_positive_keywords_increase_score(self, service):
        """긍정 키워드가 있으면 점수 증가"""
        result = service.score_text('상태 안정적이며 양호함')
        assert result > 50

    def test_score_text_negative_keywords_decrease_score(self, service):
        """부정 키워드가 있으면 점수 감소"""
        result = service.score_text('통증 호소 및 악화 경향')
        assert result < 50

    def test_score_text_capped_at_100(self, service):
        """점수는 최대 100"""
        text = ' '.join(['양호'] * 20)
        result = service.score_text(text)
        assert result <= 100

    def test_score_text_floored_at_0(self, service):
        """점수는 최소 0"""
        text = ' '.join(['악화'] * 20)
        result = service.score_text(text)
        assert result >= 0

    # ========== detect_meal_type 테스트 ==========

    def test_detect_meal_type_normal(self, service):
        """일반식 감지"""
        result = service.detect_meal_type('일반식 전량 섭취')
        assert result == '일반식'

    def test_detect_meal_type_soft(self, service):
        """죽식 감지"""
        result = service.detect_meal_type('죽식 1/2 섭취')
        assert result == '죽식'

    def test_detect_meal_type_none_input(self, service):
        """None 입력 시 None 반환"""
        result = service.detect_meal_type(None)
        assert result is None

    def test_detect_meal_type_unknown(self, service):
        """식사 유형이 없는 텍스트"""
        result = service.detect_meal_type('특별한 내용 없음')
        assert result is None

    # ========== score_meal_amount 테스트 ==========

    def test_score_meal_amount_full(self, service):
        """전량 섭취 → 1.0"""
        result = service.score_meal_amount('전량 섭취')
        assert result == 1.0

    def test_score_meal_amount_half(self, service):
        """절반 섭취 → 0.5"""
        result = service.score_meal_amount('절반 섭취')
        assert result == 0.5

    def test_score_meal_amount_refused(self, service):
        """거부 → 0.0"""
        result = service.score_meal_amount('거부')
        assert result == 0.0

    def test_score_meal_amount_none(self, service):
        """None 입력 → 기본값 0.75"""
        result = service.score_meal_amount(None)
        assert result == 0.75

    def test_score_meal_amount_unknown(self, service):
        """알 수 없는 텍스트 → 기본값 0.75"""
        result = service.score_meal_amount('알 수 없음')
        assert result == 0.75

    # ========== meal_amount_label 테스트 ==========

    def test_meal_amount_label_full(self, service):
        """전량 → '전량' 레이블"""
        result = service.meal_amount_label('전량 섭취')
        assert result == '전량'

    def test_meal_amount_label_none(self, service):
        """None → '정보없음'"""
        result = service.meal_amount_label(None)
        assert result == '정보없음'

    def test_meal_amount_label_unknown(self, service):
        """알 수 없는 텍스트 → '정보없음'"""
        result = service.meal_amount_label('특수한 식사')
        assert result == '정보없음'

    # ========== extract_toilet_count 테스트 ==========

    def test_extract_toilet_count_multiple(self, service):
        """'소변 3회 대변 1회' → 4.0"""
        result = service.extract_toilet_count('소변 3회 대변 1회')
        assert result == 4.0

    def test_extract_toilet_count_single(self, service):
        """'5회' → 5.0"""
        result = service.extract_toilet_count('5회')
        assert result == 5.0

    def test_extract_toilet_count_none(self, service):
        """None 입력 → None"""
        result = service.extract_toilet_count(None)
        assert result is None

    def test_extract_toilet_count_no_numbers(self, service):
        """숫자가 없는 텍스트 → None"""
        result = service.extract_toilet_count('정상')
        assert result is None

    # ========== parse_toilet_breakdown 테스트 ==========

    def test_parse_toilet_breakdown_full(self, service):
        """대변/소변/기저귀 모두 포함"""
        result = service.parse_toilet_breakdown('대변 2회 소변 4회 기저귀 1회')
        assert result['stool'] == 2.0
        assert result['urine'] == 4.0
        assert result['diaper'] == 1.0

    def test_parse_toilet_breakdown_none(self, service):
        """None 입력 → 빈 딕셔너리"""
        result = service.parse_toilet_breakdown(None)
        assert result == {}

    def test_parse_toilet_breakdown_no_match(self, service):
        """일치하는 패턴 없음 → 모두 0"""
        result = service.parse_toilet_breakdown('특이사항 없음')
        assert result.get('stool', 0) == 0
        assert result.get('urine', 0) == 0
        assert result.get('diaper', 0) == 0

    def test_parse_toilet_breakdown_urine_only(self, service):
        """소변만 있는 경우"""
        result = service.parse_toilet_breakdown('소변 3회')
        assert result['urine'] == 3.0
        assert result['stool'] == 0.0

    def test_parse_toilet_breakdown_stool_only(self, service):
        """대변만 있는 경우"""
        result = service.parse_toilet_breakdown('배변 2회')
        assert result['stool'] == 2.0
        assert result['urine'] == 0.0
