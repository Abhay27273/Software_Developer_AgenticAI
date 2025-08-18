graph TD
    subgraph "User's Device"
        MobileClient[📱 Mobile Client <br>(React Native/Flutter)]
    end

    subgraph "Cloud Infrastructure (AWS)"
        APIGateway[🌐 API Gateway <br>(e.g., AWS API Gateway)]

        subgraph "Backend (Kubernetes Cluster - EKS)"
            AuthService[⚙️ Auth Service]
            UserService[⚙️ User Service]
            CoreService[⚙️ Core Business Service]
            NotificationService[⚙️ Notification Service]
        end

        subgraph "Data Stores"
            PostgresDB[🐘 PostgreSQL <br>(RDS)]
            RedisCache[⚡ Redis Cache <br>(ElastiCache)]
        end

        subgraph "Messaging"
            MessageQueue[📬 Message Queue <br>(RabbitMQ / SQS)]
        end

        subgraph "External Integrations"
            S3[📦 Object Storage <br>(AWS S3)]
        end
    end

    subgraph "Third-Party Services"
        AuthProvider[🔐 Auth Provider <br>(e.g., Auth0, Cognito)]
        PushNotifications[📨 Push Notification Service <br>(FCM/APNS)]
    end

    %% Connections
    MobileClient -->|HTTPS/REST API| APIGateway

    APIGateway -->|gRPC/REST| AuthService
    APIGateway -->|gRPC/REST| UserService
    APIGateway -->|gRPC/REST| CoreService

    AuthService --> AuthProvider
    UserService --> PostgresDB
    CoreService --> PostgresDB
    CoreService --> RedisCache
    CoreService --> S3

    %% Asynchronous Communication
    CoreService -- "UserCreated Event" --> MessageQueue
    UserService -- "UserUpdated Event" --> MessageQueue
    MessageQueue -- "UserCreated Event" --> NotificationService
    MessageQueue -- "UserUpdated Event" --> UserService

    NotificationService --> PushNotifications