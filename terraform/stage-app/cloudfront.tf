# Valoarea header-ului secret CloudFront -> ALB. Ajunge in state (face parte din
# configuratia CloudFront); state-ul e criptat in S3 si valoarea se regenereaza la fiecare create.
resource "random_password" "origin_verify" {
  length  = 32
  special = false
}

# Politici gestionate de AWS (cautate dupa nume, nu ID-uri scrise de mana)
data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled" # date live: fiecare cerere ajunge la ALB
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer" # trimite tot, inclusiv Host (necesar pentru CSRF-ul Grafana)
}

resource "aws_cloudfront_distribution" "this" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "wfm-stage: HTTPS in fata ALB-ului"
  price_class     = "PriceClass_100" # doar edge-uri Europa + America de Nord (cele mai ieftine)

  origin {
    origin_id   = "alb"
    domain_name = aws_lb.this.dns_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # HTTPS se termina la CloudFront; spre ALB, HTTP prin reteaua AWS
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # Dovada pentru ALB ca cererea vine de la distributia NOASTRA
    custom_header {
      name  = local.origin_verify_header
      value = random_password.origin_verify.result
    }
  }

  default_cache_behavior {
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"                                          # http:// -> https://
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"] # Grafana face POST
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Certificatul *.cloudfront.net, gratuit si reinnoit automat de AWS
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "wfm-stage-cdn"
  }
}
