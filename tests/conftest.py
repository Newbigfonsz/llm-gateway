"""
Pytest fixtures for LLM Gateway tests.
Uses moto to mock AWS services.
"""

import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone
from decimal import Decimal


# Set environment variables before importing handlers
@pytest.fixture(autouse=True)
def aws_env_vars(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('API_KEYS_TABLE', 'test-api-keys')
    monkeypatch.setenv('USAGE_TABLE', 'test-usage')
    monkeypatch.setenv('RATE_LIMITS_TABLE', 'test-rate-limits')
    monkeypatch.setenv('RATE_LIMIT_RPM', '60')


@pytest.fixture
def dynamodb_tables():
    """Create mocked DynamoDB tables."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # API Keys table
        dynamodb.create_table(
            TableName='test-api-keys',
            KeySchema=[{'AttributeName': 'api_key', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'api_key', 'AttributeType': 'S'},
                {'AttributeName': 'team_id', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'team-index',
                'KeySchema': [{'AttributeName': 'team_id', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )

        # Usage table
        dynamodb.create_table(
            TableName='test-usage',
            KeySchema=[
                {'AttributeName': 'team_id', 'KeyType': 'HASH'},
                {'AttributeName': 'date', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'team_id', 'AttributeType': 'S'},
                {'AttributeName': 'date', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Rate limits table
        dynamodb.create_table(
            TableName='test-rate-limits',
            KeySchema=[{'AttributeName': 'key', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'key', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )

        yield dynamodb


@pytest.fixture
def valid_api_key(dynamodb_tables):
    """Create a valid API key in the mocked table."""
    table = dynamodb_tables.Table('test-api-keys')
    api_key = 'llm-test-valid-key-12345678'

    table.put_item(Item={
        'api_key': api_key,
        'team_id': 'test-team',
        'team_name': 'Test Team',
        'rate_limit_rpm': 60,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': True
    })

    return api_key


@pytest.fixture
def inactive_api_key(dynamodb_tables):
    """Create an inactive API key."""
    table = dynamodb_tables.Table('test-api-keys')
    api_key = 'llm-test-inactive-key-1234'

    table.put_item(Item={
        'api_key': api_key,
        'team_id': 'inactive-team',
        'team_name': 'Inactive Team',
        'rate_limit_rpm': 60,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'is_active': False
    })

    return api_key


@pytest.fixture
def expired_api_key(dynamodb_tables):
    """Create an expired API key."""
    table = dynamodb_tables.Table('test-api-keys')
    api_key = 'llm-test-expired-key-1234'

    table.put_item(Item={
        'api_key': api_key,
        'team_id': 'expired-team',
        'team_name': 'Expired Team',
        'rate_limit_rpm': 60,
        'created_at': '2020-01-01T00:00:00+00:00',
        'expires_at': '2020-12-31T00:00:00+00:00',  # Expired date
        'is_active': True
    })

    return api_key


@pytest.fixture
def usage_data(dynamodb_tables):
    """Create sample usage data."""
    table = dynamodb_tables.Table('test-usage')
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    table.put_item(Item={
        'team_id': 'test-team',
        'date': today,
        'requests': 10,
        'input_tokens': 1000,
        'output_tokens': 500,
        'total_cost': Decimal('0.005'),
        'models': {'claude-3-haiku': 8, 'nova-micro': 2},
        'updated_at': datetime.now(timezone.utc).isoformat()
    })

    return {'team_id': 'test-team', 'date': today}
