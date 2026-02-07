"""
Tests for the Gateway Lambda handler.
"""

import json
import time

import boto3
from moto import mock_aws
from unittest.mock import patch, MagicMock

from helpers import make_api_gateway_event, load_handler_module


class TestHealthCheck:
    """Tests for /health endpoint."""

    @mock_aws
    def test_health_check_returns_healthy(self, dynamodb_tables):
        """Health check should return healthy status without auth."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event('/health', 'GET')
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['service'] == 'llm-gateway'
        assert 'timestamp' in body
        assert body['version'] == '1.0.0'


class TestAuthentication:
    """Tests for API key authentication."""

    @mock_aws
    def test_missing_api_key_returns_401(self, dynamodb_tables):
        """Requests without API key should return 401."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event('/v1/models', 'GET')
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Missing API key' in body['error']['message']

    @mock_aws
    def test_invalid_api_key_returns_401(self, dynamodb_tables):
        """Invalid API key should return 401."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'x-api-key': 'invalid-key-12345'}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid API key' in body['error']['message']

    @mock_aws
    def test_inactive_api_key_returns_401(self, dynamodb_tables, inactive_api_key):
        """Inactive API key should return 401."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'x-api-key': inactive_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid API key' in body['error']['message']

    @mock_aws
    def test_expired_api_key_returns_401(self, dynamodb_tables, expired_api_key):
        """Expired API key should return 401."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'x-api-key': expired_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid API key' in body['error']['message']

    @mock_aws
    def test_valid_api_key_with_uppercase_header(self, dynamodb_tables, valid_api_key):
        """API key in X-Api-Key header should work."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'X-Api-Key': valid_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200


class TestListModels:
    """Tests for /v1/models endpoint."""

    @mock_aws
    def test_list_models_returns_available_models(self, dynamodb_tables, valid_api_key):
        """List models should return available models."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['object'] == 'list'
        assert 'data' in body
        assert len(body['data']) > 0

        # Check model structure
        model = body['data'][0]
        assert 'id' in model
        assert 'provider' in model
        assert 'pricing' in model


class TestChatCompletion:
    """Tests for /v1/chat endpoint."""

    @mock_aws
    def test_chat_missing_messages_returns_400(self, dynamodb_tables, valid_api_key):
        """Chat request without messages should return 400."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'POST',
            headers={'x-api-key': valid_api_key},
            body={'model': 'claude-3-haiku'}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Messages' in body['error']['message']

    @mock_aws
    def test_chat_empty_messages_returns_400(self, dynamodb_tables, valid_api_key):
        """Chat request with empty messages should return 400."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'POST',
            headers={'x-api-key': valid_api_key},
            body={'model': 'claude-3-haiku', 'messages': []}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 400

    @mock_aws
    def test_chat_invalid_message_structure_returns_400(self, dynamodb_tables, valid_api_key):
        """Chat request with invalid message structure should return 400."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'POST',
            headers={'x-api-key': valid_api_key},
            body={'model': 'claude-3-haiku', 'messages': [{'invalid': 'structure'}]}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'role' in body['error']['message']

    @mock_aws
    def test_chat_invalid_role_returns_400(self, dynamodb_tables, valid_api_key):
        """Chat request with invalid role should return 400."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'POST',
            headers={'x-api-key': valid_api_key},
            body={
                'model': 'claude-3-haiku',
                'messages': [{'role': 'invalid_role', 'content': 'Hello'}]
            }
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid role' in body['error']['message']

    @mock_aws
    def test_chat_unknown_model_returns_400(self, dynamodb_tables, valid_api_key):
        """Chat request with unknown model should return 400."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'POST',
            headers={'x-api-key': valid_api_key},
            body={
                'model': 'unknown-model',
                'messages': [{'role': 'user', 'content': 'Hello'}]
            }
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Unknown model' in body['error']['message']

    @mock_aws
    def test_chat_anthropic_model_success(self, dynamodb_tables, valid_api_key):
        """Chat completion with Anthropic model should succeed."""
        gateway = load_handler_module("gateway")

        # Mock Bedrock response
        mock_response_body = {
            'content': [{'text': 'Hello! How can I help you?'}],
            'usage': {'input_tokens': 10, 'output_tokens': 8}
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response_body).encode()

        with patch.object(gateway, 'bedrock') as mock_bedrock:
            mock_bedrock.invoke_model.return_value = {'body': mock_body}

            event = make_api_gateway_event(
                '/v1/chat', 'POST',
                headers={'x-api-key': valid_api_key},
                body={
                    'model': 'claude-3-haiku',
                    'messages': [{'role': 'user', 'content': 'Hello'}]
                }
            )
            response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['object'] == 'chat.completion'
        assert body['model'] == 'claude-3-haiku'
        assert 'choices' in body
        assert body['choices'][0]['message']['content'] == 'Hello! How can I help you?'
        assert 'usage' in body
        assert body['usage']['prompt_tokens'] == 10
        assert body['usage']['completion_tokens'] == 8
        assert 'gateway_metadata' in body
        assert body['gateway_metadata']['team_id'] == 'test-team'

    @mock_aws
    def test_chat_nova_model_success(self, dynamodb_tables, valid_api_key):
        """Chat completion with Nova model should succeed."""
        gateway = load_handler_module("gateway")

        # Mock Bedrock response for Nova
        mock_response_body = {
            'output': {'message': {'content': [{'text': 'Nova response'}]}},
            'usage': {'inputTokens': 5, 'outputTokens': 3}
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response_body).encode()

        with patch.object(gateway, 'bedrock') as mock_bedrock:
            mock_bedrock.invoke_model.return_value = {'body': mock_body}

            event = make_api_gateway_event(
                '/v1/chat', 'POST',
                headers={'x-api-key': valid_api_key},
                body={
                    'model': 'nova-micro',
                    'messages': [{'role': 'user', 'content': 'Hello'}]
                }
            )
            response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['model'] == 'nova-micro'
        assert body['choices'][0]['message']['content'] == 'Nova response'

    @mock_aws
    def test_chat_titan_model_success(self, dynamodb_tables, valid_api_key):
        """Chat completion with Titan model should succeed."""
        gateway = load_handler_module("gateway")

        # Mock Bedrock response for Titan
        mock_response_body = {
            'results': [{'outputText': 'Titan response', 'tokenCount': 10}]
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response_body).encode()

        with patch.object(gateway, 'bedrock') as mock_bedrock:
            mock_bedrock.invoke_model.return_value = {'body': mock_body}

            event = make_api_gateway_event(
                '/v1/chat', 'POST',
                headers={'x-api-key': valid_api_key},
                body={
                    'model': 'titan-text-express',
                    'messages': [{'role': 'user', 'content': 'Hello'}]
                }
            )
            response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['model'] == 'titan-text-express'
        assert body['choices'][0]['message']['content'] == 'Titan response'

    @mock_aws
    def test_chat_with_system_message(self, dynamodb_tables, valid_api_key):
        """Chat with system message should be handled correctly."""
        gateway = load_handler_module("gateway")

        mock_response_body = {
            'content': [{'text': 'I am a helpful assistant.'}],
            'usage': {'input_tokens': 20, 'output_tokens': 6}
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(mock_response_body).encode()

        with patch.object(gateway, 'bedrock') as mock_bedrock:
            mock_bedrock.invoke_model.return_value = {'body': mock_body}

            event = make_api_gateway_event(
                '/v1/chat', 'POST',
                headers={'x-api-key': valid_api_key},
                body={
                    'model': 'claude-3-haiku',
                    'messages': [
                        {'role': 'system', 'content': 'You are a helpful assistant.'},
                        {'role': 'user', 'content': 'Who are you?'}
                    ]
                }
            )
            response = gateway.lambda_handler(event, None)

            assert response['statusCode'] == 200
            # Verify system message was passed to Bedrock
            call_args = mock_bedrock.invoke_model.call_args
            request_body = json.loads(call_args.kwargs['body'])
            assert 'system' in request_body
            assert request_body['system'] == 'You are a helpful assistant.'


class TestRateLimiting:
    """Tests for rate limiting."""

    @mock_aws
    def test_rate_limit_exceeded_returns_429(self, dynamodb_tables, valid_api_key):
        """Exceeding rate limit should return 429."""
        gateway = load_handler_module("gateway")

        # Pre-fill rate limit counter to exceed limit
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table('test-rate-limits')
        minute_key = f"test-team:{int(time.time()) // 60}"
        table.put_item(Item={
            'key': minute_key,
            'request_count': 100,  # Exceeds default 60 RPM
            'expires_at': int(time.time()) + 120
        })

        event = make_api_gateway_event(
            '/v1/models', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 429
        body = json.loads(response['body'])
        assert 'Rate limit exceeded' in body['error']['message']


class TestNotFound:
    """Tests for unknown endpoints."""

    @mock_aws
    def test_unknown_path_returns_404(self, dynamodb_tables, valid_api_key):
        """Unknown path should return 404."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/unknown', 'GET',
            headers={'x-api-key': valid_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'Not found' in body['error']['message']

    @mock_aws
    def test_wrong_method_returns_404(self, dynamodb_tables, valid_api_key):
        """Wrong HTTP method should return 404."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event(
            '/v1/chat', 'GET',  # Should be POST
            headers={'x-api-key': valid_api_key}
        )
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 404


class TestStagePrefix:
    """Tests for stage prefix handling."""

    @mock_aws
    def test_dev_stage_prefix_stripped(self, dynamodb_tables):
        """Dev stage prefix should be stripped from path."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event('/dev/health', 'GET')
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'

    @mock_aws
    def test_prod_stage_prefix_stripped(self, dynamodb_tables):
        """Prod stage prefix should be stripped from path."""
        gateway = load_handler_module("gateway")

        event = make_api_gateway_event('/prod/health', 'GET')
        response = gateway.lambda_handler(event, None)

        assert response['statusCode'] == 200
