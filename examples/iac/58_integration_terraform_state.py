"""Example: Terraform state drift detection.

Demonstrates detecting drift from Terraform state.
"""
from dcc.iac_observability.drift import DriftDetector

# Simulated Terraform desired state (from .tf files)
tf_desired = {
    "aws_instance.web[0]": {
        "resource_type": "aws_instance",
        "name": "web-0",
        "instance_type": "t3.micro",
        "ami": "ami-12345",
    },
    "aws_instance.web[1]": {
        "resource_type": "aws_instance",
        "name": "web-1",
        "instance_type": "t3.micro",
        "ami": "ami-12345",
    },
    "aws_db_instance.main": {
        "resource_type": "aws_db_instance",
        "name": "main",
        "instance_class": "db.t3.micro",
    },
}

# Simulated actual state (from cloud API)
tf_actual = {
    "aws_instance.web[0]": {
        "resource_type": "aws_instance",
        "name": "web-0",
        "instance_type": "t3.micro",
        "ami": "ami-12345",
    },
    "aws_instance.web[1]": {
        "resource_type": "aws_instance",
        "name": "web-1",
        "instance_type": "t3.micro",
        "ami": "ami-12345",
    },
    "aws_db_instance.main": {
        "resource_type": "aws_db_instance",
        "name": "main",
        "instance_class": "db.t3.micro",
    },
    "aws_instance.rogue": {
        "resource_type": "aws_instance",
        "name": "rogue",
        "instance_type": "t3.large",
        "ami": "ami-67890",
    },
}

detector = DriftDetector()
result = detector.detect(tf_desired, tf_actual)
print(f"Terraform drift detected: {result.has_drift}")
print(f"Total drifted: {result.total_drifted}")
for d in result.drifts:
    print(f"  {d.drift_type.value}: {d.resource_name} - {d.description}")
