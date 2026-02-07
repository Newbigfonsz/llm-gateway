"""
LLM Gateway - Auth Handler
Handles API key validation and management.
"""

import json
import os
import boto3
import secrets
import logging
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal serialization for DynamoDB."""
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
API_KEYS_TABLE = os.environ.get('API_KEYS_TABLE')


def lambda_handler(event, context):
    """Lambda handler for auth operations."""
    
    path = event.get('rawPath', event.get('path', ''))
    method = event.get('requestContext', {}).get('http', {}).get('method',
             event.get('httpMethod', 'GET'))
    
    # This handler is primarily for internal/admin use
    # In production, you'd add admin authentication here
    
    if path == '/admin/keys' and method == 'POST':
        body = json.loads(event.get('body', '{}'))
        return create_api_key(body)
    elif path == '/admin/keys' and method == 'GET':
        return list_api_keys()
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Not found'})
        }


def create_api_key(body):
    """Create a new API key for a team."""
    
    team_id = body.get('team_id')
    team_name = body.get('team_name', team_id)
    rate_limit_rpm = body.get('rate_limit_rpm', 60)
    
    if not team_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'team_id is required'})
        }
    
    # Generate secure API key
    api_key = f"llm-{secrets.token_hex(16)}"
    
    try:
        table = dynamodb.Table(API_KEYS_TABLE)
        table.put_item(Item={
            'api_key': api_key,
            'team_id': team_id,
            'team_name': team_name,
            'rate_limit_rpm': rate_limit_rpm,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'is_active': True
        })
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'api_key': api_key,
                'team_id': team_id,
                'team_name': team_name,
                'rate_limit_rpm': rate_limit_rpm,
                'message': 'API key created successfully. Store this key securely - it cannot be retrieved again.'
            })
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error creating API key: {e.response['Error']['Code']}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create API key'})
        }


def list_api_keys():
    """List all API keys (without revealing the full key)."""
    
    try:
        table = dynamodb.Table(API_KEYS_TABLE)
        response = table.scan()
        
        keys = []
        for item in response.get('Items', []):
            api_key = item.get('api_key', '')
            keys.append({
                'api_key_prefix': api_key[:12] + '...' if len(api_key) > 12 else api_key,
                'team_id': item.get('team_id'),
                'team_name': item.get('team_name'),
                'rate_limit_rpm': item.get('rate_limit_rpm'),
                'is_active': item.get('is_active', True),
                'created_at': item.get('created_at')
            })
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'keys': keys,
                'count': len(keys)
            }, cls=DecimalEncoder)
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error listing API keys: {e.response['Error']['Code']}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to list API keys'})
        }
