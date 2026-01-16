import json
import boto3
import logging

logger = logging.getLogger()
bedrock = boto3.client("bedrock-runtime")

def invoke_bedrock(model_id, request_data):
    messages = request_data.get("messages", [])
    max_tokens = request_data.get("max_tokens", 1024)
    temperature = request_data.get("temperature", 1.0)
    system = request_data.get("system", "")
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if temperature != 1.0:
        body["temperature"] = temperature
    if system:
        body["system"] = system
    
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        response_body = json.loads(response["body"].read())
        usage = response_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        formatted = {
            "id": response.get("ResponseMetadata", {}).get("RequestId", ""),
            "model": model_id,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_body.get("content", [{}])[0].get("text", "")
                },
                "finish_reason": response_body.get("stop_reason", "end_turn")
            }],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        }
        return {"success": True, "response": formatted, "input_tokens": input_tokens, "output_tokens": output_tokens}
    except Exception as e:
        logger.error(f"Bedrock error: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "status_code": 502}
