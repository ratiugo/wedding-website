# Container images for the RSVP Lambda.
resource "aws_ecr_repository" "rsvp" {
  name                 = "wedding/rsvp"
  image_tag_mutability = "IMMUTABLE"
}

resource "aws_ecr_lifecycle_policy" "rsvp" {
  repository = aws_ecr_repository.rsvp.name

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
