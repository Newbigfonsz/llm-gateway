"""
Tests for the Auth Lambda handler.
"""

import json

import boto3
from moto import mock_aws

from helpers import make_api_gateway_event, load_handler_module


class TestCreateApiKey:
    """Tests for POST /admin/keys endpoint."""

    @mock_aws
    def test_create_api_key_success(self, dynamodb_tables):
        """Creating an API key should succeed with valid input."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event(
            '/admin/keys', 'POST',
            body={
                'team_id': 'new-team',
                'team_name': 'New Team',
                'rate_limit_rpm': 100
            }
        )
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert 'api_key' in body
        assert body['api_key'].startswith('llm-')
        assert len(body['api_key']) == 36  # 'llm-' + 32 hex chars
        assert body['team_id'] == 'new-team'
        assert body['team_name'] == 'New Team'
        assert body['rate_limit_rpm'] == 100
        assert 'Store this key securely' in body['message']

    @mock_aws
    def test_create_api_key_default_values(self, dynamodb_tables):
        """Creating an API key should use defaults for optional fields."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event(
            '/admin/keys', 'POST',
            body={'team_id': 'minimal-team'}
        )
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        assert body['team_name'] == 'minimal-team'  # Defaults to team_id
        assert body['rate_limit_rpm'] == 60  # Default rate limit

    @mock_aws
    def test_create_api_key_missing_team_id_returns_400(self, dynamodb_tables):
        """Creating an API key without team_id should return 400."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event(
            '/admin/keys', 'POST',
            body={'team_name': 'No ID Team'}
        )
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'team_id is required' in body['error']

    @mock_aws
    def test_create_api_key_empty_body_returns_400(self, dynamodb_tables):
        """Creating an API key with empty body should return 400."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'POST', body={})
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 400

    @mock_aws
    def test_created_key_is_stored_in_dynamodb(self, dynamodb_tables):
        """Created API key should be stored in DynamoDB."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event(
            '/admin/keys', 'POST',
            body={'team_id': 'stored-team', 'team_name': 'Stored Team'}
        )
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 201
        body = json.loads(response['body'])
        api_key = body['api_key']

        # Verify key is in DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-api-keys')
        item = table.get_item(Key={'api_key': api_key})

        assert 'Item' in item
        assert item['Item']['team_id'] == 'stored-team'
        assert item['Item']['team_name'] == 'Stored Team'
        assert item['Item']['is_active'] is True
        assert 'created_at' in item['Item']


class TestListApiKeys:
    """Tests for GET /admin/keys endpoint."""

    @mock_aws
    def test_list_api_keys_empty(self, dynamodb_tables):
        """Listing API keys when none exist should return empty list."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'GET')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['keys'] == []
        assert body['count'] == 0

    @mock_aws
    def test_list_api_keys_returns_keys(self, dynamodb_tables, valid_api_key):
        """Listing API keys should return existing keys."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'GET')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['count'] == 1
        assert len(body['keys']) == 1

        key_info = body['keys'][0]
        assert key_info['team_id'] == 'test-team'
        assert key_info['team_name'] == 'Test Team'
        assert key_info['is_active'] is True

    @mock_aws
    def test_list_api_keys_masks_full_key(self, dynamodb_tables, valid_api_key):
        """Listed API keys should only show prefix, not full key."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'GET')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        key_info = body['keys'][0]
        assert 'api_key_prefix' in key_info
        assert key_info['api_key_prefix'].endswith('...')
        assert len(key_info['api_key_prefix']) == 15  # 12 chars + '...'

    @mock_aws
    def test_list_multiple_api_keys(self, dynamodb_tables, valid_api_key, inactive_api_key):
        """Listing should return all API keys."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'GET')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['count'] == 2


class TestNotFound:
    """Tests for unknown admin endpoints."""

    @mock_aws
    def test_unknown_admin_path_returns_404(self, dynamodb_tables):
        """Unknown admin path should return 404."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/unknown', 'GET')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'Not found' in body['error']

    @mock_aws
    def test_wrong_method_on_keys_returns_404(self, dynamodb_tables):
        """Wrong HTTP method on /admin/keys should return 404."""
        auth = load_handler_module("auth")

        event = make_api_gateway_event('/admin/keys', 'DELETE')
        response = auth.lambda_handler(event, None)

        assert response['statusCode'] == 404
