# A private network for the database and the RSVP Lambda.
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = { Name = "wedding-${var.environment}" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# Two subnets in different availability zones, because Aurora requires two.
resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)

  tags = { Name = "wedding-${var.environment}-private-${count.index}" }
}

# Allow the Lambda to write RSVP events to S3.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_vpc.main.main_route_table_id]
}

resource "aws_security_group" "rsvp" {
  name   = "wedding-${var.environment}-rsvp"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group" "database" {
  name   = "wedding-${var.environment}-database"
  vpc_id = aws_vpc.main.id
}

resource "aws_vpc_security_group_egress_rule" "rsvp_to_database" {
  security_group_id            = aws_security_group.rsvp.id
  referenced_security_group_id = aws_security_group.database.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "rsvp_to_s3" {
  security_group_id = aws_security_group.rsvp.id
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "database_from_rsvp" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.rsvp.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
