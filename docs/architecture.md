# RideFlow Architecture

## 1. Overview

RideFlow is a cloud-native ride-hailing platform built around
independent microservices, container orchestration, event streaming,
and cross-cloud analytics.

## 2. Application Services

- API Gateway: routes client requests to backend services.
- Rider Service: manages rider profiles.
- Driver Service: manages driver profiles and availability.
- Pricing Service: calculates fare estimates.
- Trip Service: coordinates trip creation and lifecycle operations.

## 3. AWS Application Platform

- Amazon VPC: network isolation and routing.
- Application Load Balancer: receives external HTTP/HTTPS traffic.
- Amazon EKS: runs the containerized services.
- Amazon ECR: stores application container images.
- Amazon RDS for PostgreSQL: relational transactional storage.
- Amazon DynamoDB: selected key-value/document access patterns.
- Amazon S3: object and archive storage.
- Amazon SQS and AWS Lambda: optional asynchronous processing.

## 4. Event Streaming

Confluent Cloud provides Kafka topics for trip events and,
when required by downstream consumers, analytical results.

## 5. Azure Analytics

Azure Databricks runs Apache Spark jobs.
Azure Data Lake Storage Gen2 stores analytics outputs and
stream-processing checkpoints.

## 6. Delivery and GitOps

GitHub Actions validates, tests, and builds application images.
Amazon ECR stores the images.
Argo CD reconciles Kubernetes resources from Git.

## 7. Observability

Prometheus collects metrics, Grafana visualizes operational data,
and Loki aggregates logs.

## 8. Implementation Status

This document describes the target architecture.
Components will be marked implemented and verified only after
their code, configuration, and tests have been completed.
