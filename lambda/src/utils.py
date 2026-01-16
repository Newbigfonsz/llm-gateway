import json
import uuid

def create_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid.uuid4())
        },
        "body": json.dumps(body, default=str)
    }

def log_request_to_s3(team_id, model, request, response, duration_ms):
    pass  # Optional: implement S3 logging
