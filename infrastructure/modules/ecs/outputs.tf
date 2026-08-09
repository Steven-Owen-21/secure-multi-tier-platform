# -----------------------------------------------------------------------------
# ECS Fargate Module — Outputs
# -----------------------------------------------------------------------------

output "service_arn" {
  description = "ARN of the ECS Fargate service."
  value       = aws_ecs_service.app.id
}

output "task_definition_arn" {
  description = "ARN of the current ECS task definition."
  value       = aws_ecs_task_definition.app.arn
}

output "cluster_arn" {
  description = "ARN of the ECS cluster."
  value       = aws_ecs_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.main.name
}

output "service_name" {
  description = "Name of the ECS service."
  value       = aws_ecs_service.app.name
}

output "task_execution_role_arn" {
  description = "ARN of the task execution IAM role."
  value       = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  description = "ARN of the task IAM role (runtime application permissions)."
  value       = aws_iam_role.task.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group for ECS container logs."
  value       = aws_cloudwatch_log_group.ecs.name
}
