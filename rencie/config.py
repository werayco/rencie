from pydantic import BaseModel
from typing import Optional
from celery import Celery


celery_app = Celery(
    "worker", broker="redis://redis:6379/0", backend="redis://redis:6379/0", include=["renci.logic"]
)

celery_app.conf.update(
    task_routes={
        "logic.*": {"queue": "default"},
    }
)

# celery_app.autodiscover_tasks(["renci"])

class responsemodel(BaseModel):
    status_code: int
    response: str


class dobPayload(BaseModel):
    day: int
    month: int
    year: int

class Payload(BaseModel):
    query: str
    otpQuery: Optional[str] = None

class createPayload(BaseModel):
    firstName: str
    lastName: str
    dob: dobPayload
    phoneNumber: str
    emailAddress: str
    password: str


class loginPayload(BaseModel):
    accountNumber: str
    password: str


class transferPayload(BaseModel):
    token: str
    receipientAccntNumber: str
    amount: int


class checkBalancePayload(BaseModel):
    token: str
