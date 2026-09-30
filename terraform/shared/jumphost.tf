# ---------- AMI ----------
# Cel mai nou Amazon Linux 2023 pentru ARM (Graviton), publicat de AWS in SSM
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# ---------- IAM role ----------
# Trust policy: CINE poate lua rolul -> serviciul EC2
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "jumphost" {
  name               = "wfm-jumphost-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# Permission policy: CE poate face -> doar ce ii trebuie agentului SSM
resource "aws_iam_role_policy_attachment" "jumphost_ssm" {
  role       = aws_iam_role.jumphost.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# "Ambalajul" care leaga rolul de instanta EC2
resource "aws_iam_instance_profile" "jumphost" {
  name = "wfm-jumphost-profile"
  role = aws_iam_role.jumphost.name
}

# ---------- Security group ----------
resource "aws_security_group" "jumphost" {
  name        = "wfm-jumphost-sg"
  description = "JumpHost: fara reguli de intrare, acces doar prin SSM"
  vpc_id      = module.network.vpc_id

  tags = {
    Name = "wfm-jumphost-sg"
  }
}

# Iesire HTTPS: agentul SSM si actualizarile de pachete (dnf)
resource "aws_vpc_security_group_egress_rule" "jumphost_https" {
  security_group_id = aws_security_group.jumphost.id
  description       = "HTTPS spre SSM si repository-urile de pachete"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# Iesire spre VPC-ul stage (prin peering): InfluxDB, Grafana, backend...
resource "aws_vpc_security_group_egress_rule" "jumphost_to_stage" {
  security_group_id = aws_security_group.jumphost.id
  description       = "Orice trafic spre VPC-ul stage"
  ip_protocol       = "-1"
  cidr_ipv4         = "10.0.0.0/16"
}

# ---------- Instanta ----------
resource "aws_instance" "jumphost" {
  ami                    = data.aws_ssm_parameter.al2023_arm64.insecure_value
  instance_type          = "t4g.micro"
  subnet_id              = module.network.public_subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.jumphost.id]
  iam_instance_profile   = aws_iam_instance_profile.jumphost.name

  # IMDSv2 obligatoriu (protectie impotriva furtului de credentiale prin SSRF)
  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "wfm-jumphost"
  }

  lifecycle {
    # AMI-ul "latest" se schimba lunar; nu vrem ca fiecare plan sa recreeze masina
    ignore_changes = [ami]
  }
}

# ---------- Pornit / oprit din cod ----------
resource "aws_ec2_instance_state" "jumphost" {
  instance_id = aws_instance.jumphost.id
  state       = var.jumphost_running ? "running" : "stopped"
}
