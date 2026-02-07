"""
Tests for the Usage Lambda handler.
"""

import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from moto import mock_aws

from helpers import make_api_gateway_event, load_handler_module


class TestUsageAuthentication:
    """Tests for usage endpoint authentication."""

    @mock_aws
    def test_missing_api_key_returns_401(self, dynamodb_tables):
        """Usage request without API key should return 401."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event('/v1/usage', 'GET')
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Missing API key' in body['error']['message']

    @mock_aws
    def test_invalid_api_key_returns_401(self, dynamodb_tables):
        """Usage request with invalid API key should return 401."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': 'invalid-key'}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid API key' in body['error']['message']

    @mock_aws
    def test_uppercase_header_works(self, dynamodb_tables, valid_api_key):
        """Usage request with X-Api-Key header should work."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'X-Api-Key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200


class TestUsageRetrieval:
    """Tests for usage data retrieval."""

    @mock_aws
    def test_get_usage_empty(self, dynamodb_tables, valid_api_key):
        """Getting usage with no data should return zeros."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        assert body['team_id'] == 'test-team'
        assert body['team_name'] == 'Test Team'
        assert 'period' in body
        assert body['period']['days'] == 30
        assert 'summary' in body
        assert body['summary']['total_requests'] == 0
        assert body['summary']['total_cost_usd'] == 0
        assert body['daily'] == []
        assert body['by_model'] == []

    @mock_aws
    def test_get_usage_with_data(self, dynamodb_tables, valid_api_key, usage_data):
        """Getting usage with existing data should return aggregated stats."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        assert body['summary']['total_requests'] == 10
        assert body['summary']['total_input_tokens'] == 1000
        assert body['summary']['total_output_tokens'] == 500
        assert body['summary']['total_tokens'] == 1500
        assert body['summary']['total_cost_usd'] == 0.005

        # Check daily breakdown
        assert len(body['daily']) == 1
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        assert body['daily'][0]['date'] == today
        assert body['daily'][0]['requests'] == 10

        # Check model breakdown
        assert len(body['by_model']) == 2
        # Should be sorted by request count descending
        assert body['by_model'][0]['model'] == 'claude-3-haiku'
        assert body['by_model'][0]['requests'] == 8

    @mock_aws
    def test_get_usage_custom_days(self, dynamodb_tables, valid_api_key):
        """Getting usage with custom days parameter should use that period."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key},
            query_params={'days': '7'}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        assert body['period']['days'] == 7

    @mock_aws
    def test_get_usage_response_structure(self, dynamodb_tables, valid_api_key):
        """Usage response should have correct structure."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        # Check all required fields
        assert 'team_id' in body
        assert 'team_name' in body
        assert 'period' in body
        assert 'days' in body['period']
        assert 'start' in body['period']
        assert 'end' in body['period']
        assert 'summary' in body
        assert 'total_requests' in body['summary']
        assert 'total_input_tokens' in body['summary']
        assert 'total_output_tokens' in body['summary']
        assert 'total_tokens' in body['summary']
        assert 'total_cost_usd' in body['summary']
        assert 'avg_daily_cost_usd' in body['summary']
        assert 'avg_tokens_per_request' in body['summary']
        assert 'daily' in body
        assert 'by_model' in body


class TestUsageMultipleDays:
    """Tests for multi-day usage aggregation."""

    @mock_aws
    def test_aggregates_multiple_days(self, dynamodb_tables, valid_api_key):
        """Usage should aggregate data across multiple days."""
        usage = load_handler_module("usage")

        # Add usage data for multiple days
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-usage')

        today = datetime.now(timezone.utc)
        for i in range(3):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            table.put_item(Item={
                'team_id': 'test-team',
                'date': date,
                'requests': 10,
                'input_tokens': 100,
                'output_tokens': 50,
                'total_cost': Decimal('0.001'),
                'models': {'claude-3-haiku': 10}
            })

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        assert body['summary']['total_requests'] == 30  # 10 * 3 days
        assert body['summary']['total_input_tokens'] == 300
        assert body['summary']['total_output_tokens'] == 150
        assert len(body['daily']) == 3

    @mock_aws
    def test_daily_sorted_by_date(self, dynamodb_tables, valid_api_key):
        """Daily breakdown should be sorted by date ascending."""
        usage = load_handler_module("usage")

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-usage')

        today = datetime.now(timezone.utc)
        # Insert in random order
        for i in [2, 0, 1]:
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            table.put_item(Item={
                'team_id': 'test-team',
                'date': date,
                'requests': 1,
                'input_tokens': 10,
                'output_tokens': 5,
                'total_cost': Decimal('0.0001'),
                'models': {}
            })

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        body = json.loads(response['body'])
        dates = [d['date'] for d in body['daily']]

        # Check dates are sorted ascending
        assert dates == sorted(dates)


class TestUsageModelBreakdown:
    """Tests for model usage breakdown."""

    @mock_aws
    def test_model_breakdown_sorted_by_requests(self, dynamodb_tables, valid_api_key, usage_data):
        """Model breakdown should be sorted by request count descending."""
        usage = load_handler_module("usage")

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        body = json.loads(response['body'])

        # From fixture: claude-3-haiku: 8, nova-micro: 2
        assert body['by_model'][0]['model'] == 'claude-3-haiku'
        assert body['by_model'][0]['requests'] == 8
        assert body['by_model'][1]['model'] == 'nova-micro'
        assert body['by_model'][1]['requests'] == 2

    @mock_aws
    def test_model_breakdown_aggregates_across_days(self, dynamodb_tables, valid_api_key):
        """Model breakdown should aggregate across multiple days."""
        usage = load_handler_module("usage")

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-usage')

        today = datetime.now(timezone.utc)
        for i in range(2):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            table.put_item(Item={
                'team_id': 'test-team',
                'date': date,
                'requests': 10,
                'input_tokens': 100,
                'output_tokens': 50,
                'total_cost': Decimal('0.001'),
                'models': {'claude-3-haiku': 5, 'nova-micro': 5}
            })

        event = make_api_gateway_event(
            '/v1/usage', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = usage.lambda_handler(event, None)

        body = json.loads(response['body'])

        # Should have aggregated: 5*2 = 10 for each model
        model_dict = {m['model']: m['requests'] for m in body['by_model']}
        assert model_dict['claude-3-haiku'] == 10
        assert model_dict['nova-micro'] == 10
