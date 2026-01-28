import os
import boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from botocore.exceptions import ClientError
from router import get_model_cost

logger = logging.getLogger(__name__)
dynamodb = boto3.resource("dynamodb")
usage_table = dynamodb.Table(os.environ.get("USAGE_TABLE", "llm-gateway-usage-dev"))

def track_usage(team_id, model, input_tokens, output_tokens, duration_ms):
    now = datetime.now(timezone.utc)
    costs = get_model_cost(model)
    cost = (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])
    try:
        usage_table.put_item(Item={
            "team_id": team_id,
            "timestamp": now.isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": Decimal(str(round(cost, 6))),
            "duration_ms": Decimal(str(round(duration_ms, 2))),
            "date": now.strftime("%Y-%m-%d"),
            "expires_at": int((now + timedelta(days=90)).timestamp())
        })
    except ClientError as e:
        logger.warning(f"DynamoDB error tracking usage: {e.response['Error']['Code']}")
        # Don't fail the request if usage tracking fails

def get_usage_stats(team_id, days=30):
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        response = usage_table.query(
            KeyConditionExpression="team_id = :tid AND #ts >= :start",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={":tid": team_id, ":start": start_date}
        )
        items = response.get("Items", [])
        total_input = sum(int(i.get("input_tokens", 0)) for i in items)
        total_output = sum(int(i.get("output_tokens", 0)) for i in items)
        total_cost = sum(float(i.get("cost", 0)) for i in items)
        return {
            "team_id": team_id,
            "period_days": days,
            "total_requests": len(items),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": round(total_cost, 4)
        }
    except ClientError as e:
        logger.error(f"DynamoDB error getting usage stats: {e.response['Error']['Code']}")
        return {"error": "Failed to get stats"}
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid usage stats data format: {str(e)}")
        return {"error": "Failed to get stats"}
