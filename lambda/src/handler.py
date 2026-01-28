import json
import os
import logging
from datetime import datetime, timezone
from auth import validate_api_key
from router import route_request
from usage import track_usage
from utils import create_response, log_request_to_s3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    # Log request path and method only (avoid logging sensitive headers/body)
    http_context = event.get("requestContext", {}).get("http", {})
    logger.info(f"Request: {http_context.get('method', 'UNKNOWN')} {http_context.get('path', '/')}")
    
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("requestContext", {}).get("http", {}).get("path", "")
    headers = event.get("headers", {})
    body = event.get("body", "")
    
    if path == "/health":
        return create_response(200, {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})
    
    api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    if not api_key:
        return create_response(401, {"error": "Missing x-api-key header"})
    
    auth_result = validate_api_key(api_key)
    if not auth_result["valid"]:
        return create_response(401, {"error": auth_result["error"]})
    
    if auth_result.get("rate_limited"):
        return create_response(429, {"error": "Rate limit exceeded"})
    
    team_id = auth_result["team_id"]
    team_settings = auth_result["settings"]
    
    try:
        if path == "/v1/models":
            models = [
                {"id": "claude-3-sonnet", "provider": "bedrock"},
                {"id": "claude-3-haiku", "provider": "bedrock"},
            ]
            return create_response(200, {"models": models})
        
        elif path == "/v1/usage":
            from usage import get_usage_stats
            return create_response(200, get_usage_stats(team_id))
        
        elif path == "/v1/chat":
            request_data = json.loads(body) if body else {}
            model = request_data.get("model")
            messages = request_data.get("messages", [])
            
            if not model:
                return create_response(400, {"error": "Missing: model"})
            if not messages:
                return create_response(400, {"error": "Missing: messages"})
            
            start = datetime.now(timezone.utc)
            result = route_request(model, request_data, team_settings)
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            
            if result["success"]:
                track_usage(team_id, model, result.get("input_tokens", 0), result.get("output_tokens", 0), duration)
                return create_response(200, result["response"])
            else:
                return create_response(result.get("status_code", 500), {"error": result["error"]})
        
        return create_response(404, {"error": f"Unknown path: {path}"})
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return create_response(500, {"error": "Internal server error"})
