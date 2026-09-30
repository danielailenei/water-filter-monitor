output "state_bucket_name" {
  description = "Numele bucket-ului pentru state; il folosim in backend-ul celorlalte straturi"
  value       = aws_s3_bucket.tfstate.bucket
}

output "state_bucket_arn" {
  description = "ARN-ul bucket-ului (pentru politici IAM)"
  value       = aws_s3_bucket.tfstate.arn
}
