# RideFlow — Cloud-Native Ride-Hailing Platform

## Project Overview

RideFlow is a cloud-native, microservices-based ride-hailing platform designed to demonstrate modern cloud infrastructure, container orchestration, Infrastructure as Code, CI/CD, GitOps, event-driven architecture, and multi-cloud data analytics.

The target architecture uses **AWS as the primary application platform, Confluent Cloud for event streaming, and Microsoft Azure for real-time analytics using Apache Spark**.

The project is being developed incrementally, with implementation and testing evidence documented for each milestone.

## System Architecture
![RideFlow Multi-Cloud Architecture](docs/architecture.png)


**Architecture:** AWS + Confluent Cloud + Azure

- **AWS:** Application hosting, networking, container orchestration, databases, and supporting services.
- **Confluent Cloud:** Kafka-based event streaming for trip events and analytical results.
- **Microsoft Azure:** Azure Databricks, Apache Spark, and Azure Data Lake Storage Gen2.
- **DevOps:** GitHub Actions, Amazon ECR, Terraform, Kubernetes, and Argo CD.
- **Observability:** Prometheus, Grafana, and Loki.

> **Implementation note:** This diagram represents the target architecture. Individual components will be marked implemented and verified only after their configurations, integrations, and tests are completed.

---

## Project Objectives

1. Design a modular ride-hailing application using microservices.
2. Containerize services using Docker.
3. Orchestrate application workloads using Amazon EKS and Kubernetes.
4. Automate infrastructure provisioning using Terraform.
5. Implement CI/CD workflows using GitHub Actions.
6. Adopt GitOps-based deployment management using Argo CD.
7. Implement event-driven processing using Confluent Cloud and Apache Kafka.
8. Process trip events using Azure Databricks and Apache Spark.
9. Store analytical outputs and streaming checkpoints in Azure Data Lake Storage Gen2.
10. Introduce monitoring, logging, security controls, and load testing.

---

## Architecture and Technology Stack

| Layer                  | Technology                                       | Responsibility                                                   |
| ---------------------- | ------------------------------------------------ | ---------------------------------------------------------------- |
| Application            | Python, FastAPI                                  | API endpoints and business logic                                 |
| API entry point        | Application Load Balancer + RideFlow API Gateway | External traffic handling and application request routing        |
| Containers             | Docker                                           | Consistent application packaging                                 |
| Orchestration          | Amazon EKS, Kubernetes                           | Container scheduling, service discovery, and workload management |
| Infrastructure as Code | Terraform                                        | Reproducible infrastructure provisioning                         |
| CI                     | GitHub Actions                                   | Automated validation, testing, and image builds                  |
| Container registry     | Amazon ECR                                       | Container image storage                                          |
| GitOps / CD            | Argo CD                                          | Reconciliation of Git-defined Kubernetes resources               |
| Relational database    | Amazon RDS for PostgreSQL                        | Structured transactional data                                    |
| NoSQL database         | Amazon DynamoDB                                  | Selected key-value and document access patterns                  |
| Object storage         | Amazon S3                                        | Files, exports, and archived data                                |
| Messaging              | Amazon SQS                                       | Asynchronous background work where required                      |
| Serverless compute     | AWS Lambda                                       | Event-triggered background processing where required             |
| Event streaming        | Confluent Cloud / Apache Kafka                   | Trip event distribution                                          |
| Analytics processing   | Azure Databricks / Apache Spark                  | Stream processing and analytical aggregation                     |
| Analytics storage      | Azure Data Lake Storage Gen2                     | Analytical datasets and streaming checkpoints                    |
| Metrics                | Prometheus                                       | Metrics collection                                               |
| Dashboards             | Grafana                                          | Visualization and monitoring                                     |
| Logs                   | Grafana Loki                                     | Log aggregation and querying                                     |
| Load testing           | k6                                               | Performance and load validation                                  |

---

## Microservices Architecture

RideFlow is organized around five application services.

### 1. API Gateway

**Purpose:** Provides a consistent application entry point and routes client requests to backend services.

Planned responsibilities include request validation, correlation IDs, authentication integration, rate limiting, and consistent error responses.

### 2. Rider Service

**Purpose:** Manages rider profile information.

Planned operations include rider registration, profile retrieval, profile updates, and rider deletion.

### 3. Driver Service

**Purpose:** Manages driver profiles, vehicle details, availability, and location-related information.

The service provides the driver information needed during trip creation.

### 4. Pricing Service

**Purpose:** Calculates estimated trip fares using configurable business rules, such as base fare, distance, duration, and applicable surcharges.

### 5. Trip Service

**Purpose:** Coordinates trip creation and lifecycle operations.

The target workflow validates rider information, retrieves driver availability, requests a fare estimate, persists trip state, and publishes trip events for downstream processing.

**Internal communication:** Backend services use Kubernetes service discovery and HTTP/REST according to their API contracts. Kafka is used for asynchronous event distribution rather than replacing every synchronous request.

---

## AWS Infrastructure

### Networking

The target AWS environment uses the `rideflow-vpc` VPC in the `ap-south-1` region.

Planned infrastructure includes:

- Internet Gateway for appropriate VPC internet connectivity.
- Public subnets for the internet-facing load balancer and configured network egress resources.
- Private application subnets for EKS workloads.
- Private database subnets for database resources.
- Route tables, security groups, and restricted network access.
- Multi-Availability-Zone deployment where supported by the selected resource configuration.

### Amazon EKS and Kubernetes

Amazon EKS provides the managed Kubernetes control plane for the containerized application.

Planned Kubernetes resources include:

- Deployments and Pods for application services.
- ClusterIP Services for internal service discovery.
- Ingress/load-balancer integration for incoming traffic.
- Readiness and liveness probes.
- Resource requests and limits.
- Horizontal Pod Autoscalers where appropriate.
- Kubernetes access controls and workload security configuration.

### AWS Data and Supporting Services

- **Amazon RDS for PostgreSQL:** Relational transactional storage.
- **Amazon DynamoDB:** Selected high-throughput key-value or document access patterns.
- **Amazon S3:** Object storage for exports, files, and archived datasets.
- **Amazon SQS:** Queue-based background processing where required.
- **AWS Lambda:** Event-triggered processing, such as a future notification handler.
- **Amazon ECR:** Storage of versioned application container images.

Database ownership and synchronization responsibilities will be documented before implementing any duplicated data across storage systems.

---

## CI/CD and GitOps

The intended delivery workflow is:

1. Developers commit and push source changes to GitHub.
2. GitHub Actions runs automated validation and tests.
3. The pipeline builds the service's Docker image.
4. Image vulnerability and configuration checks run.
5. The validated image is published to Amazon ECR.
6. Deployment configuration is updated with the new image version.
7. Argo CD detects changes in Git.
8. Argo CD reconciles the desired Kubernetes resources into Amazon EKS.
9. Application health and deployment results are verified.

**GitHub Actions** handles CI and image publishing. **Argo CD** manages GitOps-based deployment reconciliation.

Cloud credentials will be managed through appropriately scoped identities and permissions rather than embedded in source code or container images.

---

## Event-Driven Architecture — Confluent Cloud

Confluent Cloud provides the managed Kafka platform for distributing application events.

### Planned Kafka Topics

| Topic                | Purpose                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `trips`              | Carries trip-related events produced by the application for downstream consumers.        |
| `analytical-results` | Optional stream for derived analytical results when a downstream consumer requires them. |

### Event Processing Workflow

1. Trip Service creates and persists a trip.
2. Trip Service publishes a trip event.
3. Confluent Cloud stores the event in the `trips` topic.
4. Azure Databricks consumes the event stream.
5. Spark processes and aggregates the event data.
6. Analytics outputs are persisted to Azure Data Lake Storage Gen2.
7. Derived results may optionally be published to `analytical-results`.

The implementation will include secure Kafka connectivity, topic permissions, event schema management, retries, and appropriate handling of duplicate delivery.

---

## Azure Analytics — Databricks and Apache Spark

Azure is the target analytics environment.

### Azure Databricks

Azure Databricks provides the managed environment for running Apache Spark jobs.

Planned processing includes:

- Reading trip events from Confluent Cloud.
- Validating and transforming event records.
- Aggregating trip counts and other operational metrics.
- Processing event-time windows where required.
- Persisting processed results for downstream analysis.

### Azure Data Lake Storage Gen2

ADLS Gen2 is the planned storage layer for analytics datasets and streaming checkpoints.

Proposed logical layout:

```text
rideflow-analytics/
├── raw/
│   └── trip-events/
├── processed/
│   └── trip-metrics/
└── checkpoints/
    └── trip-streaming/
```

The final directory layout, access policies, retention rules, and checkpoint configuration will be established during implementation.

---

## Observability and Monitoring

The target observability stack consists of Prometheus, Grafana, and Loki.

### Prometheus

Collects numerical metrics such as request rate, error rate, response latency, resource utilization, and application-specific counters.

### Grafana

Visualizes metrics and logs through dashboards and supports configured alerting workflows.

### Grafana Loki

Aggregates and queries application and infrastructure logs to help diagnose failures and trace application behavior.

The completed setup will include metric endpoints, scrape configuration, log collection, data-source configuration, dashboards, and alert rules as applicable.

---

## Testing and Performance Validation

RideFlow will use layered testing rather than relying only on successful deployment.

### Unit Testing

Tests individual business rules, input validation, pricing calculations, and service functions.

### Integration Testing

Tests database operations, service-to-service API contracts, and Kafka producer/consumer behavior.

### API Testing

Bruno or equivalent HTTP tooling will be used to exercise the service endpoints and validate responses.

### Container Testing

Docker images will be built and run locally to verify startup behavior, health endpoints, environment configuration, and dependency installation.

### Load Testing

k6 will be used to generate controlled traffic and measure request throughput, latency, and error rates. Kubernetes scaling behavior will be validated when the relevant workloads and monitoring are deployed.

Performance results will be documented only after tests have been executed, including the environment, test duration, virtual users, request count, error rate, and latency percentiles.

---

## Repository Structure

```text
rideflow-cloud-native/
├── .github/
│   └── workflows/
├── .gitops/
├── analytics/
│   └── spark/
├── bruno/
├── docs/
│   ├── architecture.md
│   └── architecture.png
├── k8s/
├── load-tests/
│   └── k6/
├── observability/
│   ├── prometheus/
│   ├── grafana/
│   └── loki/
├── scripts/
├── services/
│   ├── api-gateway/
│   ├── rider-service/
│   ├── driver-service/
│   ├── pricing-service/
│   └── trip-service/
├── terraform/
│   ├── aws/
│   └── azure/
├── tests/
├── docker-compose.yml
├── .gitignore
└── README.md
```

Directories and configuration files will be added as each component is implemented.

---

## Development Roadmap

| Milestone | Deliverable                                                | Status      |
| --------- | ---------------------------------------------------------- | ----------- |
| 1         | Repository foundation and architecture documentation       | In progress |
| 2         | Rider, Driver, Pricing, Trip, and API Gateway services     | Planned     |
| 3         | Local Docker and Docker Compose integration                | Planned     |
| 4         | Automated CI and container image publishing                | Planned     |
| 5         | Terraform-managed AWS infrastructure                       | Planned     |
| 6         | Kubernetes deployment and Argo CD GitOps                   | Planned     |
| 7         | Confluent Cloud event streaming                            | Planned     |
| 8         | Azure Databricks and Spark analytics                       | Planned     |
| 9         | Prometheus, Grafana, and Loki                              | Planned     |
| 10        | Load testing, security validation, and final documentation | Planned     |

Statuses will be updated as implementation and verification evidence becomes available.

---

## Security and Reliability Considerations

The implementation will address:

- Least-privilege IAM and Kubernetes permissions.
- Secure handling of application and cloud credentials.
- Encrypted network communication.
- Restricted database and service access.
- Container image vulnerability checks.
- Application health checks and resource limits.
- Kafka access controls and reliable event delivery.
- Database backup and recovery considerations.
- Controlled deployments and rollback procedures.
- Monitoring, logging, and failure investigation.

---

## Cost Considerations

Managed Kubernetes, databases, NAT gateways, Confluent Cloud, and Azure Databricks can incur charges even when a project is used for development.

Development resources will be kept as small as practical. Unneeded compute resources will be stopped or deleted, and cloud usage will be monitored during implementation.

---

## Project Status and Contributions

This repository documents the design and implementation of RideFlow as a learning and engineering project.

The architecture is a target design until individual components have been implemented and verified. Deployment claims, load-test results, and operational metrics will be added only when supported by actual test evidence.

See [docs/architecture.md](docs/architecture.md) for the architecture overview.

