"""
LLM Gateway - Main Handler
Routes AI requests to AWS Bedrock with authentication, rate limiting, and usage tracking.
"""

import json
import os
import boto3
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize clients (reused across Lambda invocations)
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')

# Environment variables
API_KEYS_TABLE = os.environ.get('API_KEYS_TABLE')
USAGE_TABLE = os.environ.get('USAGE_TABLE')
RATE_LIMITS_TABLE = os.environ.get('RATE_LIMITS_TABLE')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', 'anthropic.claude-3-haiku-20240307-v1:0')
RATE_LIMIT_RPM = int(os.environ.get('RATE_LIMIT_RPM', 60))

# Model mapping (friendly name -> Bedrock model ID)
MODEL_MAPPING = {
    'claude-3-haiku': 'anthropic.claude-3-haiku-20240307-v1:0',
    'claude-3-sonnet': 'anthropic.claude-3-sonnet-20240229-v1:0',
    'claude-3.5-sonnet': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
    'claude-3-5-sonnet': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
    'titan-text-express': 'amazon.titan-text-express-v1',
    'nova-micro': 'amazon.nova-micro-v1:0',
    'nova-lite': 'amazon.nova-lite-v1:0',
}

# Model pricing (per 1K tokens)
MODEL_PRICING = {
    'anthropic.claude-3-haiku-20240307-v1:0': {'input': 0.00025, 'output': 0.00125},
    'anthropic.claude-3-sonnet-20240229-v1:0': {'input': 0.003, 'output': 0.015},
    'anthropic.claude-3-5-sonnet-20240620-v1:0': {'input': 0.003, 'output': 0.015},
    'amazon.titan-text-express-v1': {'input': 0.0002, 'output': 0.0006},
    'amazon.nova-micro-v1:0': {'input': 0.000035, 'output': 0.00014},
    'amazon.nova-lite-v1:0': {'input': 0.00006, 'output': 0.00024},
}

# Available models for /v1/models endpoint
AVAILABLE_MODELS = [
    {
        'id': 'claude-3-haiku',
        'object': 'model',
        'provider': 'anthropic',
        'description': 'Fast and efficient for simple tasks',
        'pricing': {'input_per_1k': 0.00025, 'output_per_1k': 0.00125}
    },
    {
        'id': 'claude-3-sonnet',
        'object': 'model', 
        'provider': 'anthropic',
        'description': 'Balanced performance and capability',
        'pricing': {'input_per_1k': 0.003, 'output_per_1k': 0.015}
    },
    {
        'id': 'claude-3.5-sonnet',
        'object': 'model',
        'provider': 'anthropic', 
        'description': 'Most capable model for complex tasks',
        'pricing': {'input_per_1k': 0.003, 'output_per_1k': 0.015}
    },
    {
        'id': 'titan-text-express',
        'object': 'model',
        'provider': 'amazon',
        'description': 'Amazon Titan for general text generation',
        'pricing': {'input_per_1k': 0.0002, 'output_per_1k': 0.0006}
    }
]


def lambda_handler(event, context):
    """Main Lambda handler - routes requests to appropriate handlers."""
    
    path = event.get('rawPath', event.get('path', ''))
    
    # Strip stage prefix if present (e.g., /dev/health -> /health)
    for stage in ['/dev', '/staging', '/prod']:
        if path.startswith(stage):
            path = path[len(stage):] or '/'
            break
    
    method = event.get('requestContext', {}).get('http', {}).get('method', 
             event.get('httpMethod', 'GET'))
    
    # Health check - no auth required
    if path == '/health':
        return health_check()
    
    # All other endpoints require authentication
    headers = event.get('headers', {})
    api_key = headers.get('x-api-key') or headers.get('X-Api-Key')
    
    if not api_key:
        return error_response(401, 'Missing API key. Include x-api-key header.')
    
    # Validate API key
    team_info = validate_api_key(api_key)
    if not team_info:
        return error_response(401, 'Invalid API key.')
    
    # Check rate limit
    if not check_rate_limit(team_info['team_id'], team_info.get('rate_limit_rpm', RATE_LIMIT_RPM)):
        return error_response(429, 'Rate limit exceeded. Please slow down.')
    
    # Route to appropriate handler
    if path == '/v1/models' and method == 'GET':
        return list_models()
    elif path == '/v1/chat' and method == 'POST':
        body = json.loads(event.get('body', '{}'))
        return chat_completion(body, team_info)
    else:
        return error_response(404, f'Not found: {method} {path}')


def health_check():
    """Health check endpoint for monitoring."""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'status': 'healthy',
            'service': 'llm-gateway',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '1.0.0'
        })
    }


def list_models():
    """List available models."""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'object': 'list',
            'data': AVAILABLE_MODELS
        })
    }


def chat_completion(body, team_info):
    """Handle chat completion requests via Bedrock."""

    # Parse request
    model_name = body.get('model', 'claude-3-haiku')
    messages = body.get('messages', [])
    max_tokens = body.get('max_tokens', 1024)
    temperature = body.get('temperature', 0.7)

    # Validate messages
    if not messages:
        return error_response(400, 'Messages array is required.')

    if not isinstance(messages, list):
        return error_response(400, 'Messages must be an array.')

    # Validate each message structure
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            return error_response(400, f'Message at index {i} must be an object.')
        if 'role' not in msg:
            return error_response(400, f'Message at index {i} missing required field: role')
        if msg['role'] not in ('system', 'user', 'assistant'):
            return error_response(400, f'Invalid role at index {i}: {msg["role"]}')
        if 'content' not in msg:
            return error_response(400, f'Message at index {i} missing required field: content')
    
    # Map model name to Bedrock model ID
    model_id = MODEL_MAPPING.get(model_name, model_name)
    if model_id not in MODEL_PRICING:
        return error_response(400, f'Unknown model: {model_name}. Use /v1/models to see available models.')
    
    try:
        # Call Bedrock
        start_time = time.time()
        
        if model_id.startswith('anthropic.'):
            response = call_anthropic_model(model_id, messages, max_tokens, temperature)
        elif model_id.startswith('amazon.nova'):
            response = call_nova_model(model_id, messages, max_tokens, temperature)
        elif model_id.startswith('amazon.'):
            response = call_titan_model(model_id, messages, max_tokens, temperature)
        else:
            return error_response(400, f'Unsupported model provider for: {model_id}')
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Calculate tokens and cost
        input_tokens = response.get('input_tokens', 0)
        output_tokens = response.get('output_tokens', 0)
        pricing = MODEL_PRICING.get(model_id, {'input': 0, 'output': 0})
        cost = (input_tokens / 1000 * pricing['input']) + (output_tokens / 1000 * pricing['output'])
        
        # Track usage
        track_usage(team_info['team_id'], model_name, input_tokens, output_tokens, cost)
        
        # Return response in OpenAI-compatible format
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'id': f"chatcmpl-{context_id()}",
                'object': 'chat.completion',
                'created': int(time.time()),
                'model': model_name,
                'choices': [{
                    'index': 0,
                    'message': {
                        'role': 'assistant',
                        'content': response['content']
                    },
                    'finish_reason': 'stop'
                }],
                'usage': {
                    'prompt_tokens': input_tokens,
                    'completion_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens
                },
                'gateway_metadata': {
                    'team_id': team_info['team_id'],
                    'latency_ms': latency_ms,
                    'cost_usd': round(cost, 6),
                    'provider': 'aws-bedrock'
                }
            })
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"Bedrock API error: {error_code} - {str(e)}")
        return error_response(500, f'Model invocation failed: {error_code}')
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected response format from Bedrock: {str(e)}")
        return error_response(500, 'Unexpected response format from model')
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode Bedrock response: {str(e)}")
        return error_response(500, 'Invalid response from model')


def call_anthropic_model(model_id, messages, max_tokens, temperature):
    """Call Anthropic model via Bedrock."""
    
    # Format messages for Anthropic
    formatted_messages = []
    system_prompt = None
    
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        
        if role == 'system':
            system_prompt = content
        else:
            formatted_messages.append({
                'role': role,
                'content': content
            })
    
    # Build request body
    request_body = {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': max_tokens,
        'temperature': temperature,
        'messages': formatted_messages
    }
    
    if system_prompt:
        request_body['system'] = system_prompt
    
    # Call Bedrock
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType='application/json',
        accept='application/json',
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    
    return {
        'content': response_body['content'][0]['text'],
        'input_tokens': response_body['usage']['input_tokens'],
        'output_tokens': response_body['usage']['output_tokens']
    }




def call_nova_model(model_id, messages, max_tokens, temperature):
    """Call Amazon Nova model via Bedrock."""
    
    # Format messages for Nova
    formatted_messages = []
    system_prompt = None
    
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        
        if role == 'system':
            system_prompt = content
        else:
            formatted_messages.append({
                'role': role,
                'content': [{'text': content}]
            })
    
    request_body = {
        'messages': formatted_messages,
        'inferenceConfig': {
            'maxTokens': max_tokens,
            'temperature': temperature
        }
    }
    
    if system_prompt:
        request_body['system'] = [{'text': system_prompt}]
    
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType='application/json',
        accept='application/json',
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())
    
    return {
        'content': response_body['output']['message']['content'][0]['text'],
        'input_tokens': response_body['usage']['inputTokens'],
        'output_tokens': response_body['usage']['outputTokens']
    }

def call_titan_model(model_id, messages, max_tokens, temperature):
    """Call Amazon Titan model via Bedrock."""
    
    # Format messages for Titan (simple prompt format)
    prompt = ""
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'system':
            prompt = f"{content}\n\n{prompt}"
        elif role == 'user':
            prompt += f"User: {content}\n"
        elif role == 'assistant':
            prompt += f"Assistant: {content}\n"
    
    prompt += "Assistant:"
    
    request_body = {
        'inputText': prompt,
        'textGenerationConfig': {
            'maxTokenCount': max_tokens,
            'temperature': temperature,
            'topP': 0.9
        }
    }
    
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType='application/json',
        accept='application/json',
        body=json.dumps(request_body)
    )
    
    response_body = json.loads(response['body'].read())

    # Titan returns token counts differently
    result = response_body['results'][0]
    output_text = result['outputText']

    # Estimate tokens if not provided (cache word counts to avoid redundant splits)
    token_count = result.get('tokenCount')
    if token_count is not None:
        input_tokens = token_count
        output_tokens = token_count
    else:
        # Rough estimation: ~1.3 tokens per word on average
        input_tokens = int(len(prompt.split()) * 1.3)
        output_tokens = int(len(output_text.split()) * 1.3)

    return {
        'content': output_text,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens
    }


def validate_api_key(api_key):
    """Validate API key and return team info."""
    try:
        table = dynamodb.Table(API_KEYS_TABLE)
        response = table.get_item(Key={'api_key': api_key})

        item = response.get('Item')
        if not item:
            return None

        # Check if key is active
        if not item.get('is_active', True):
            return None

        # Check expiration
        expires_at = item.get('expires_at')
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            return None

        return {
            'team_id': item['team_id'],
            'team_name': item.get('team_name', 'Unknown'),
            'rate_limit_rpm': int(item.get('rate_limit_rpm', RATE_LIMIT_RPM))
        }

    except ClientError as e:
        logger.error(f"DynamoDB error validating API key: {e.response['Error']['Code']}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid API key data format: {str(e)}")
        return None


def check_rate_limit(team_id, limit_rpm):
    """Check and update rate limit. Returns True if within limit."""
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        now = int(time.time())
        minute_key = f"{team_id}:{now // 60}"

        # Try to increment counter
        response = table.update_item(
            Key={'key': minute_key},
            UpdateExpression='SET request_count = if_not_exists(request_count, :zero) + :inc, expires_at = :exp',
            ExpressionAttributeValues={
                ':zero': 0,
                ':inc': 1,
                ':exp': now + 120  # TTL: 2 minutes
            },
            ReturnValues='UPDATED_NEW'
        )

        count = int(response['Attributes']['request_count'])
        return count <= limit_rpm

    except ClientError as e:
        logger.warning(f"DynamoDB error in rate limiting: {e.response['Error']['Code']} - failing open")
        return True  # Allow on error (fail open for availability)
    except (KeyError, ValueError) as e:
        logger.warning(f"Unexpected rate limit response format: {str(e)} - failing open")
        return True


def track_usage(team_id, model, input_tokens, output_tokens, cost):
    """Track usage for FinOps reporting."""
    try:
        table = dynamodb.Table(USAGE_TABLE)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        table.update_item(
            Key={
                'team_id': team_id,
                'date': today
            },
            UpdateExpression='''
                SET requests = if_not_exists(requests, :zero) + :one,
                    input_tokens = if_not_exists(input_tokens, :zero) + :input,
                    output_tokens = if_not_exists(output_tokens, :zero) + :output,
                    total_cost = if_not_exists(total_cost, :zero_dec) + :cost,
                    models.#model = if_not_exists(models.#model, :zero) + :one,
                    updated_at = :now,
                    expires_at = :exp
            ''',
            ExpressionAttributeNames={
                '#model': model
            },
            ExpressionAttributeValues={
                ':zero': 0,
                ':zero_dec': Decimal('0'),
                ':one': 1,
                ':input': input_tokens,
                ':output': output_tokens,
                ':cost': Decimal(str(round(cost, 6))),
                ':now': datetime.now(timezone.utc).isoformat(),
                ':exp': int(time.time()) + (90 * 24 * 60 * 60)  # 90 days retention
            }
        )
    except ClientError as e:
        logger.warning(f"DynamoDB error tracking usage: {e.response['Error']['Code']}")
        # Don't fail the request if usage tracking fails


def context_id():
    """Generate a unique context ID."""
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))


def error_response(status_code, message):
    """Return an error response."""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'error': {
                'message': message,
                'type': 'gateway_error',
                'code': status_code
            }
        })
    }
