import os
import boto3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger()
dynamodb = boto3.resource("dynamodb")
api_keys_table = dynamodb.Table(os.environ.get("API_KEYS_TABLE", "llm-gateway-api-keys-dev"))
rate_limits_table = dynamodb.Table(os.environ.get("RATE_LIMITS_TABLE", "llm-gateway-rate-limits-dev"))
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "60"))

def validate_api_key(api_key):
    try:
        response = api_keys_table.get_item(Key={"api_key": api_key})
        if "Item" not in response:
            return {"valid": False, "error": "Invalid API key"}
        
        item = response["Item"]
        if not item.get("active", True):
            return {"valid": False, "error": "API key disabled"}
        
        expires_at = item.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
            return {"valid": False, "error": "API key expired"}
        
        rate_limit = item.get("rate_limit_per_min", RATE_LIMIT_PER_MIN)
        rate_limited, retry_after = check_rate_limit(api_key, rate_limit)
        
        return {
            "valid": True,
            "team_id": item["team_id"],
            "settings": item.get("settings", {}),
            "rate_limited": rate_limited,
            "retry_after": retry_after
        }
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        return {"valid": False, "error": "Authentication error"}

def check_rate_limit(api_key, limit):
    now = datetime.utcnow()
    window = now.strftime("%Y-%m-%dT%H:%M")
    try:
        response = rate_limits_table.update_item(
            Key={"api_key": api_key, "window": window},
            UpdateExpression="SET request_count = if_not_exists(request_count, :zero) + :inc, expires_at = :exp",
            ExpressionAttributeValues={
                ":zero": 0, ":inc": 1,
                ":exp": int((now + timedelta(minutes=2)).timestamp())
            },
            ReturnValues="UPDATED_NEW"
        )
        count = response["Attributes"]["request_count"]
        if count > limit:
            return True, 60 - now.second
        return False, 0
    except Exception as e:
        logger.error(f"Rate limit error: {str(e)}")
        return False, 0
