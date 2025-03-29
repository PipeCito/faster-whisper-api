# faster-whisper-api
## How to Use It Locally

To run locally, you can use docker-compose. 

```bash
docker compose up --build -d
```

### Send an Audio File

Once the API is running, you can send an audio file using **cURL** or **Postman**:
```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "accept: application/json" \
     -F "file=@test.mp3"
```
There are 5 audio files to test in ./test

### Expected Output

The API should return a JSON response like this:
```json
{
  "transcription": "In the ancient land of Eldoria, where the skies were painted with shades of mystic hues,  and the forests whispered secrets of old, there existed a dragon named Zephyros.  Unlike the fearsome tales of dragons that plagued human hearts with terror,  Zephyros was a creature of wonder and wisdom, revered by all who knew of his existence."
}
```

### Request the stats endpoint
To request the stats endpoint, you can use 
```bash
curl "http://localhost:8000/stats" 
```

The endpoint should return a JSON response like this:
```json
{"total_calls":6,"median_latency":32.066720724105835,"average_audio_length":"11.475999999999999s"}
```

---

## How to Deploy Using Minikube

You can run the complete stack using **Minikube**.

### Install Minikube
First, install Minikube following the official guide: [Minikube Installation](https://minikube.sigs.k8s.io/docs/start/)

### Start the Minikube Cluster
Initialize the Minikube cluster with (For this test I used the driver `--driver=docker`):
```bash
minikube start --network-plugin=cni --cni=bridge 
```
*These flags ensure that internet access is enabled within the cluster.*

### Install Helm
Install Helm by following the official guide: [Helm Installation](https://helm.sh/docs/intro/install/)

### Deploy the API
Once Helm is installed, deploy the API using:
```bash
helm install faster-whisper-api ./k8s/faster-whisper-api/
```

### Expose the Service
Expose the service using:
```bash
minikube service api-service
```

This command will display two tables similar to this:

| NAMESPACE |    NAME     | TARGET PORT |            URL            |
|-----------|-------------|-------------|---------------------------|
| default   | api-service |        8000 | http://192.168.49.2:32453 |

🏃  Starting tunnel for service `api-service`...

| NAMESPACE |    NAME     | TARGET PORT |          URL           |
|-----------|-------------|-------------|------------------------|
| default   | api-service |             | http://127.0.0.1:64114 |

### Sending audio to the api
Once the service is exposed, grab the URL from the second table and make a request using **cURL** or **Postman**:

```bash
curl -X POST "http://127.0.0.1:64114/analyze" \
     -H "accept: application/json" \
     -F "file=@test.mp3"
```

This should return the expected transcription response.

### Requesting the stats endpoint
You can test the endpoint by using:
```bash
curl -X POST "http://127.0.0.1:64114/stats" 
```

## GitHub Actions
I used github actions to perform unit-test, build the docker api image and push it to docker hub.
The unit tests validate the following functionalities:
- **Model Initialization**, verifying that the object that references it is not null.
- **API Response for /analyze**, using a short test audio.
- **API Stats Endpoint**, verifying that the received json contains the expected fields.
- **Stats Update**, verifying that when a new call is made, the value of total calls is increased.

## Database for the stats endpoint
To collect the metrics, I chose FluxDB because it is an optimal database for storing metrics. It is designed specifically for time-series data, making it highly efficient for handling high-ingestion workloads while maintaining low latency. FluxDB provides excellent scalability, ensuring that metric data can be stored and queried efficiently, even as the system grows. Additionally, it offers built-in data retention policies and powerful query capabilities, which are essential for monitoring and analytics. Its compatibility with popular visualization and alerting tools further enhances its usability in observability-driven environments.

## Queue System 
### Why NATS?
I would implement NATS as our queue system because it offers:
- **Lightweight design**: Minimal resource overhead
- **High performance**: Capable of processing millions of messages per second
- **Reliable delivery**: Multiple quality-of-service options
- **Kubernetes-native**: Designed for cloud-native environments

First, I would install NATS by using helm
```bash
# Add NATS Helm repository
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install my-nats nats/nats \
  --version 0.19.0 \
  --set cluster.enabled=true \
  --set nats.jetstream.enabled=true
```
With this config, I would be able to access to the service using ```nats://my-nats.default.svc.cluster.local:4222```

For be able to use it in the api, I would create a NATS consumer to subscribe to the topic audio.process by using:
```
async def start_nats_consumer():
    nc = await nats.connect(servers=[NATS_URL])
    await nc.subscribe("audio.process", cb=process_audio_message)
```
and then, I would create the shared functions for processing the audio and extracting the stats:
```
async def handle_audio_processing(source: str, audio_data: bytes):
    if source == "http":
        # Direct processing
        return await process_audio(audio_data)
    elif source == "queue":
        # Queue-based processing
        await nc.publish("audio.process", audio_data)
```
For testing, I would use the NATS toolbox pod:

```bash
kubectl run -it --rm nats-box \
  --image=natsio/nats-box \
  --restart=Never -- sh

cat test.mp3 | nats request audio.process --wait 30
```

## How to make this "cross-cloud" compatible?

To make this system cross-cloud compatible and deployable across AWS, Google Cloud, and internal Kubernetes clusters, I would take a cloud-agnostic approach. 
First, I would ensure that all manifests use standard Kubernetes resources without cloud-specific dependencies, for example:

 - For storage, I’d configure PersistentVolumeClaims (PVCs) with dynamic provisioning, allowing the system to work seamlessly with AWS EBS, GCP Persistent Disks, or on-prem storage.

 - For networking, I’d use an Ingress Controller with a configurable LoadBalancer or external DNS integration. Instead of relying on Minikube’s built-in NATS, I’d deploy it using a Helm chart or an Operator to support different environments. 
 
Additionally, I would use a service mesh like Istio or Linkerd to securely connect and manage communication between services deployed across multiple clouds, ensuring observability, security, and traffic control. Finally, I’d implement a CI/CD pipeline that dynamically adjusts configurations using Helm values or Kustomize overlays based on the target cloud platform.

This approach ensures scalability, flexibility, and maintainability, making the system adaptable to various cloud providers.