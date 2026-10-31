# Container images for the two Lambdas: wedding/rsvp and wedding/notifier.
resource "aws_ecr_repository" "lambda" {
  for_each = toset(["rsvp", "notifier"])

  name                 = "wedding/${each.key}"
  image_tag_mutability = "IMMUTABLE"
}

resource "aws_ecr_lifecycle_policy" "lambda" {
  for_each = aws_ecr_repository.lambda

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep every image that reached prod, and the first image each Lambda was created with"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["release-", "bootstrap"]
          countType     = "imageCountMoreThan"
          countNumber   = 9999
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the 10 newest other images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}

# The RSVP repo was created before the notifier's, under these names. These tell
# Terraform it's the same repo, so it isn't deleted and recreated.
moved {
  from = aws_ecr_repository.rsvp
  to   = aws_ecr_repository.lambda["rsvp"]
}

moved {
  from = aws_ecr_lifecycle_policy.rsvp
  to   = aws_ecr_lifecycle_policy.lambda["rsvp"]
}
