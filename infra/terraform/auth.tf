resource "random_password" "auth_password" {
  length  = 20
  special = true
}

resource "random_password" "jwt_secret" {
  length  = 32
  special = true
}

output "auth_username" {
  value = "demo"
}

output "auth_password" {
  value     = random_password.auth_password.result
  sensitive = true
}

output "jwt_secret" {
  value     = random_password.jwt_secret.result
  sensitive = true
}

