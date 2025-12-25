# How to run this Agentic RAG project
`1.` Clone this repository
```console
git clone https://github.com/werayco/LLM-Evaluation.git
```
`2.` Navigate to the wd
```console
cd LLM-Evaluation
```

`3.` Create a docker netowork
```console
docker network create chatai
```

`4.` Add your environmental variables to your .env file
```console
  GOOGLE_API_KEY = "get your google api key from https://aistudio.google.com/app/api-keys"

  HUGGINGFACE_API = "get your huggingface api from https://huggingface.co"

  MONGODB_URL = "your mongodb url"
```

`5.` Start the Order Docker Service (Make sure you have Docker Installed)
```console

docker-compose -f app.docker-compose.yml up -d
```

`6.` Scale the service if you need
```console
docker-compose -f app.docker-compose.yml up --scale gentlepanther=3
```
`7.` Check the logs of the service
```console
docker logs orderservice --since=10m
```

`8.` Create an hash value to serve as your UUID (for tracking your conversation)

```console
GET http://localhost:8000/get-uuid?username=xxxx
```

`9.` Chat with with Agent
```console
POST http://localhost:8001/api/chat
```
```json
{
  "username": "xxxx",
  "query": "zzzz",
  "hashed_data": "yyyy"
}
```


## How to monitor the agent's responses
`1`  Navigate to the LLMEvals/agent/monitor and uncomment line 47 and 48

`2` Navigate back to the wd
```
Monitor the Agent by running this in your terminial
```console
python -m agent.monitor
```


python -c "import secrets; jwt_secret_urlsafe = secrets.token_urlsafe(32); print(jwt_secret_urlsafe)"
