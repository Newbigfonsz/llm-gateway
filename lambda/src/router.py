import logging
from providers.bedrock import invoke_bedrock

logger = logging.getLogger()

MODEL_MAPPING = {
    "claude-3-sonnet": {"provider": "bedrock", "model_id": "anthropic.claude-3-sonnet-20240229-v1:0"},
    "claude-3-haiku": {"provider": "bedrock", "model_id": "anthropic.claude-3-haiku-20240307-v1:0"},
    "claude-3-opus": {"provider": "bedrock", "model_id": "anthropic.claude-3-opus-20240229-v1:0"},
    "claude-3.5-sonnet": {"provider": "bedrock", "model_id": "anthropic.claude-3-5-sonnet-20240620-v1:0"},
}

MODEL_COSTS = {
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
}

def route_request(model, request_data, team_settings):
    if model not in MODEL_MAPPING:
        return {"success": False, "error": f"Unknown model: {model}", "status_code": 400}
    
    model_config = MODEL_MAPPING[model]
    try:
        if model_config["provider"] == "bedrock":
            return invoke_bedrock(model_config["model_id"], request_data)
        return {"success": False, "error": "Unknown provider", "status_code": 500}
    except Exception as e:
        logger.error(f"Router error: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e), "status_code": 502}

def get_model_cost(model):
    return MODEL_COSTS.get(model, {"input": 0, "output": 0})
