"""Read-only AWS EC2 inventory and CloudWatch CPU metrics."""
from datetime import datetime, timedelta, timezone
import os


class AwsConfigurationError(RuntimeError):
    pass


def get_aws_inventory():
    """Return EC2 instances and recent CPU metrics using the standard AWS credential chain."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:
        raise AwsConfigurationError("boto3 is not installed. Install backend/requirements.txt.") from exc

    region = os.getenv("AWS_REGION", "us-east-1")
    tag_key = os.getenv("AWS_MANAGED_TAG_KEY", "")
    tag_value = os.getenv("AWS_MANAGED_TAG_VALUE", "")
    try:
        session = boto3.Session(region_name=region)
        ec2 = session.client("ec2")
        cloudwatch = session.client("cloudwatch")
        filters = []
        if tag_key and tag_value:
            filters.append({"Name": f"tag:{tag_key}", "Values": [tag_value]})
        pages = ec2.get_paginator("describe_instances").paginate(Filters=filters)
        instances = []
        for page in pages:
            for reservation in page.get("Reservations", []):
                for item in reservation.get("Instances", []):
                    tags = {tag["Key"]: tag["Value"] for tag in item.get("Tags", [])}
                    instance_id = item["InstanceId"]
                    state = item.get("State", {}).get("Name", "unknown")
                    cpu_pct = None
                    if state == "running":
                        result = cloudwatch.get_metric_statistics(
                            Namespace="AWS/EC2",
                            MetricName="CPUUtilization",
                            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                            StartTime=datetime.now(timezone.utc) - timedelta(hours=1),
                            EndTime=datetime.now(timezone.utc),
                            Period=300,
                            Statistics=["Average"],
                        )
                        points = result.get("Datapoints", [])
                        if points:
                            cpu_pct = round(sum(point["Average"] for point in points) / len(points), 1)
                    instance_type = item.get("InstanceType", "unknown")
                    memory_gib = item.get("MemoryInfo", {}).get("SizeInMiB")
                    memory_gib = round(memory_gib / 1024, 1) if memory_gib else None
                    if state != "running":
                        status = "off"
                    elif cpu_pct is None:
                        status = "unknown"
                    elif cpu_pct >= 90:
                        status = "overloaded"
                    elif cpu_pct >= 75:
                        status = "high"
                    else:
                        status = "healthy"
                    instances.append({
                        "id": instance_id,
                        "name": tags.get("Name", instance_id),
                        "instance_type": instance_type,
                        "state": state,
                        "status": status,
                        "cpu_pct": cpu_pct,
                        "mem_pct": None,
                        "memory_gib": memory_gib,
                        "availability_zone": item.get("Placement", {}).get("AvailabilityZone"),
                        "private_ip": item.get("PrivateIpAddress"),
                        "launch_time": item.get("LaunchTime").isoformat() if item.get("LaunchTime") else None,
                        "tags": tags,
                        "actions_enabled": False,
                    })
        return {"provider": "aws", "read_only": True, "region": region,
                "managed_tag_filter": {"key": tag_key, "value": tag_value} if tag_key and tag_value else None,
                "metric_note": "CPU is the mean of available CloudWatch 5-minute datapoints over the last hour. Memory utilization is not available from standard EC2 metrics; install/configure the CloudWatch Agent to collect it.",
                "instances": instances, "count": len(instances)}
    except (BotoCoreError, ClientError) as exc:
        raise AwsConfigurationError(f"AWS request failed in {region}: {exc}") from exc
