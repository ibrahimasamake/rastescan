output "app_url" {
  description = "Open this on a phone. Use it as VITE_API_BASE for the Android build."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "server_ip" {
  value = aws_eip.app.public_ip
}

output "ssh" {
  value = "ssh ubuntu@${aws_eip.app.public_ip}"
}

output "photo_bucket" {
  value = aws_s3_bucket.photos.bucket
}
