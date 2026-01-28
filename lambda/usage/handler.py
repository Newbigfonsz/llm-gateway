"""
LLM Gateway - Usage Handler
Provides usage statistics and cost tracking for FinOps.
"""

import json
import os
import boto3
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
USAGE_TABLE = os.environ.get('USAGE_TABLE')
API_KEYS_TABLE = os.environ.get('API_KEYS_TABLE')


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal serialization for DynamoDB."""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lambda_handler(event, context):
    """Lambda handler for usage queries."""
    
    # Get API key for team identification
    headers = event.get('headers', {})
    api_key = headers.get('x-api-key') or headers.get('X-Api-Key')
    
    if not api_key:
        return error_response(401, 'Missing API key')
    
    # Get team from API key
    team_info = get_team_from_key(api_key)
    if not team_info:
        return error_response(401, 'Invalid API key')
    
    team_id = team_info['team_id']
    
    # Parse query parameters
    params = event.get('queryStringParameters') or {}
    days = int(params.get('days', 30))
    
    # Get usage data
    usage_data = get_usage(team_id, days)
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'team_id': team_id,
            'team_name': team_info.get('team_name', 'Unknown'),
            'period': {
                'days': days,
                'start': (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d'),
                'end': datetime.now(timezone.utc).strftime('%Y-%m-%d')
            },
            'summary': usage_data['summary'],
            'daily': usage_data['daily'],
            'by_model': usage_data['by_model']
        }, cls=DecimalEncoder)
    }


def get_team_from_key(api_key):
    """Get team info from API key."""
    try:
        table = dynamodb.Table(API_KEYS_TABLE)
        response = table.get_item(Key={'api_key': api_key})
        return response.get('Item')
    except ClientError as e:
        logger.error(f"DynamoDB error getting team: {e.response['Error']['Code']}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid team data format: {str(e)}")
        return None


def get_usage(team_id, days):
    """Get usage data for a team."""
    try:
        table = dynamodb.Table(USAGE_TABLE)
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Query usage data
        response = table.query(
            KeyConditionExpression='team_id = :tid AND #date BETWEEN :start AND :end',
            ExpressionAttributeNames={'#date': 'date'},
            ExpressionAttributeValues={
                ':tid': team_id,
                ':start': start_date.strftime('%Y-%m-%d'),
                ':end': end_date.strftime('%Y-%m-%d')
            }
        )
        
        items = response.get('Items', [])

        # Single-pass aggregation for better performance
        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = Decimal('0')
        model_usage = {}
        daily = []

        for item in items:
            # Extract values once per item
            requests = int(item.get('requests', 0))
            input_tokens = int(item.get('input_tokens', 0))
            output_tokens = int(item.get('output_tokens', 0))
            cost = item.get('total_cost', Decimal('0'))

            # Accumulate totals
            total_requests += requests
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_cost += cost

            # Build daily entry
            daily.append({
                'date': item.get('date'),
                'requests': requests,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': float(cost)
            })

            # Aggregate model usage in single pass
            for model, count in item.get('models', {}).items():
                model_usage[model] = model_usage.get(model, 0) + int(count)

        # Sort daily by date
        daily.sort(key=lambda x: x['date'])
        
        return {
            'summary': {
                'total_requests': total_requests,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'total_tokens': total_input_tokens + total_output_tokens,
                'total_cost_usd': float(total_cost),
                'avg_daily_cost_usd': float(total_cost / days) if days > 0 else 0,
                'avg_tokens_per_request': (total_input_tokens + total_output_tokens) / total_requests if total_requests > 0 else 0
            },
            'daily': daily,
            'by_model': [
                {'model': model, 'requests': count}
                for model, count in sorted(model_usage.items(), key=lambda x: -x[1])
            ]
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error getting usage: {e.response['Error']['Code']}")
        return {
            'summary': {
                'total_requests': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_tokens': 0,
                'total_cost_usd': 0,
                'avg_daily_cost_usd': 0,
                'avg_tokens_per_request': 0
            },
            'daily': [],
            'by_model': []
        }
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid usage data format: {str(e)}")
        return {
            'summary': {
                'total_requests': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_tokens': 0,
                'total_cost_usd': 0,
                'avg_daily_cost_usd': 0,
                'avg_tokens_per_request': 0
            },
            'daily': [],
            'by_model': []
        }


def error_response(status_code, message):
    """Return an error response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'error': {
                'message': message,
                'code': status_code
            }
        })
    }
