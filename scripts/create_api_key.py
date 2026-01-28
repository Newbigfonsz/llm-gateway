import argparse
import boto3
import secrets
import string
from datetime import datetime, timezone

def generate_api_key(prefix="llmgw"):
    chars = string.ascii_letters + string.digits
    return f"{prefix}_{''.join(secrets.choice(chars) for _ in range(32))}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default="llm-gateway-api-keys-dev")
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--rate-limit", type=int, default=60)
    args = parser.parse_args()
    
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(args.table)
    api_key = generate_api_key()
    
    table.put_item(Item={
        "api_key": api_key,
        "team_id": args.team_id,
        "name": args.name,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rate_limit_per_min": args.rate_limit,
        "settings": {}
    })
    
    print(f"\nAPI Key created!\nTeam: {args.team_id}\nKey: {api_key}\n")

if __name__ == "__main__":
    main()
