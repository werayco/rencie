from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
from pydantic import BaseModel
import re
from typing import Optional
from fastapi import File, UploadFile
from typing import Optional
from pathlib import Path
from fastapi.exceptions import HTTPException
from agent.process import *
from agent.ragsystem import *
from renci.logic import *
from renci.config import *

app = FastAPI(title="Renci AI Agent Server", version="1.0.0")

@app.get("/")
async def health_check():
    return JSONResponse(
        content={"message": "health check route is active!"}, status_code=200
    )

def extract_five_digit_number(query: str) -> Optional[str]:
    match = re.search(r"\b\d{5}\b", query)
    return match.group(0) if match else None


def extract_stop_word(query: str) -> bool:
    return bool(re.search(r"\bstop\b", query, re.IGNORECASE))

@app.post("/create-vector-store")
async def create_vector_store(file_path: UploadFile = File(...)):
    safe_filename = Path(file_path.filename).name
    filename = uuid.uuid4().hex + "_" + safe_filename
    try:
        with open(filename, "wb") as buffer:
            content = await file_path.read()
            buffer.write(content)
        vectorstorecreator(filename)

        return {"message": "Vector store created successfully."}

    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        raise HTTPException(
            status_code=500, detail=f"Error creating vector store: {str(e)}"
        )

@app.post("/api/chat")
async def chat_endpoint(req: Payload, request: Request):
    try:
        auth_header = request.headers.get("JWT")
        decodedJWT = bank.decodeJWT(auth_header)
        accntNumber = decodedJWT["accountNumber"]
        data = req.dict()
        query = data.get("query")

        config = {"configurable": {"thread_id": accntNumber}}
        current_state = compiled.get_state(config)

        if current_state.next:
            otp_value = extract_stop_word(query)

            if otp_value and otp_value.lower() == "stop":
                compiled.clear_interrupts(config)
                
                return JSONResponse(
                    content={
                        "status": "success",
                        "response": "Your transaction has been stopped, but previous messages are retained."
                    },
                    status_code=200
                )

            if otp_value is None:
                return JSONResponse(
                    content={"status": "error", "message": "OTP is required when graph is interrupted"},
                    status_code=400
                )

            response = compiled.invoke(
                Command(resume=extract_five_digit_number(query)),
                config=config
            )

        else:
            query = data.get("query")
            if not query:
                return JSONResponse(
                    content={"status": "error", "message": "Query is required"},
                    status_code=400
                )

            response = compiled.invoke(
                {
                    "messages": [HumanMessage(content=query)],
                    "senderAccountNumber": accntNumber,
                    "name": decodedJWT["name"],
                    "email": decodedJWT["email"],
                },
                config=config,
            )

        lastMessage = None
        if response and response.get("messages"):
            lastMessage = response["messages"][-1].content

        if lastMessage is None:
            return JSONResponse(
                content={"status": "error", "response": "No messages returned from the graph."},
                status_code=500
            )

        return JSONResponse(
            content={"status": "success", "response": lastMessage},
            status_code=200
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/api/v1/create-account")
async def createAccount(req: createPayload):
    try:
        requestPayload = req.dict()
        firstName: str = requestPayload.get("firstName")
        lastName: str = requestPayload.get("lastName")
        dob: str = requestPayload.get("dob")

        password: str = requestPayload.get("password")
        phoneNumber: int = requestPayload.get("phoneNumber")
        emailAddress: str = requestPayload.get("emailAddress")
        ethAddress : str = requestPayload.get("ethAddress")
        task = bank.createUser.delay(
            firstName, lastName, dob, password, phoneNumber, emailAddress, ethAddress
        )

        return JSONResponse(
            content={
                "status": "Processing",
                "response": f"Your Account would be created shortly, check your email in few minutes!",
            },
            status_code=201,
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "failed", "response": str(e)}, status_code=500
        )


@app.post("/api/v1/login")
async def login(req: loginPayload):
    try:
        requestPayload = req.dict()
        accountNumber: str = requestPayload.get("accountNumber")
        password: str = requestPayload.get("password")

        response = bank.authenticateUser(accountNumber, password)
        return JSONResponse(
            content={"status": "successful", "token": f"{response['token']}"},
            status_code=201,
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "failed", "response": str(e)}, status_code=500
        )


@app.post("/api/v1/check-balance")
async def checkBalance(req: checkBalancePayload):
    try:
        requestPayload = req.dict()
        token: str = requestPayload.get("token")
        response = bank.checkBalance(token)
        return JSONResponse(
            content={"status": "successful", "response": response}, status_code=201
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "failed", "response": str(e)}, status_code=500
        )


@app.post("/api/v1/check-statement")
async def getTransactionStatement(req: checkBalancePayload):
    try:
        requestPayload = req.dict()
        token: str = requestPayload.get("token")
        response = bank.getBankStatement.delay(token)
        return JSONResponse(
            content={
                "status": "Processing",
                "response": "Your Bank Statement is on it's way! check your email",
            },
            status_code=201,
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "failed", "response": str(e)}, status_code=500
        )


@app.post("/api/v1/transfer")
async def transfer(req: transferPayload):
    try:
        requestPayload = req.dict()
        token: str = requestPayload.get("token")
        receipientAccntNumber = requestPayload.get("receipientAccntNumber")
        amount = requestPayload.get("amount")
        response = bank.transferMoney(token, receipientAccntNumber, amount)
        return JSONResponse(
            content={"status": "successful", "response": response}, status_code=201
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "failed", "response": str(e)}, status_code=500
        )
