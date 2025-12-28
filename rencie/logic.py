from pymongo import MongoClient
import math, random
import os
from dotenv import load_dotenv
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
from datetime import datetime, timezone, timedelta
import bcrypt
import uuid
import secrets
import jwt
from typing import Literal
from rencie.config import *

# load_dotenv(dotenv_path=r".\all.env")
# load_dotenv()

JWT_SECRET = str(os.getenv("JWT_SECRET"))
MONGO = os.getenv("MONGODB")

client = MongoClient(MONGO)
db = client["bank"]
userAccnts, transactions, otp, apiKey = (
    db["accountInfo"],
    db["Transactions"],
    db["OTP"],
    db["apiKeys"],
)

class bank:
    def generate_user_id():
        return str(uuid.uuid4())

    def hash_password(password: str):
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt)

    def main(length=10):
        digits = "0123456789"
        OTP = ""
        for _ in range(5):
            OTP += digits[math.floor(random.random() * length)]
        return OTP

    def send_email(
        subject="Welcome",
        body="<p>Congrats on sending your <strong>first email</strong>!</p>",
        to="werayco@gmail.com",
    ):
        import resend

        try:
            resend.api_key = os.getenv("RESEND_API_KEY")
            client = resend.Emails.send(
                {
                    "from": "onboarding@resend.dev",
                    "to": to,
                    "subject": subject,
                    "html": body,
                }
            )
            if client:
                return {"status": "successful", "response": f"email send to {to}"}
        except Exception as e:
            return {"status": "failed", "reason": e}

    def genTranID():
        return secrets.token_hex(16)

    def generateOTP(user_accnt_number: str, name: str, email: str):
        otp_code = bank.main()
        otpID = bank.genTranID()
        otp_entry = {
            "accountNumber": user_accnt_number,
            "otp": otp_code,
            "createdAt": bank.current_date(),
            "otpID": otpID,
            "expiresAt": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }

        if otp.insert_one(otp_entry):
            bank.send_email(
                subject=f"Hello, {name}!", body=f"Your OTP is {otp_code}", to=email
            )
            return {
                "status": "successful",
                "response": f"OTP has been sent to your email {email}",
                "OtpID": otpID,
            }

    def current_date():
        return datetime.now(timezone.utc).isoformat()

    def deposit():
        pass

    @celery_app.task
    def createUser(
        firstName: str,
        lastName: str,
        dob: str,
        password: str,
        phoneNumber,
        emailAddress: str,
        ethAddress: str,
        length=10,
    ):
        """this is used to create a new user"""
        userID = bank.generate_user_id()
        secret = os.getenv("secretKey")

        user_string: str = firstName + lastName + str(dob) + (password) + secret
        hash_object = hashlib.sha256(user_string.encode())
        hex_digest = hash_object.hexdigest()
        base_number = int(hex_digest, 16)

        accountNumber = str(base_number)[-length:]
        if userAccnts.find_one({"accountNumber": accountNumber}):
            return {"status": "failed", "response": "user exists"}

        newUser = {
            "userID": userID,
            "accountNumber": accountNumber,
            "firstName": firstName,
            "lastName": lastName,
            "DOB": dob,
            "hashedPassword": bank.hash_password(password),
            "accountBalance": 500_000,
            "currency": "NGN",
            "createdAt": bank.current_date(),
            "phoneNumber": phoneNumber,
            "emailAddress": emailAddress,
            "ethAddress": ethAddress,
        }

        saveUser = userAccnts.insert_one(newUser)
        if saveUser:
            bank.send_email(
                subject="Welcome to rencie!",
                body=f"<p>Hi {firstName},<br/>Your account has been created successfully. Your account number is <strong>{accountNumber}</strong>.</p>",
                to=emailAddress,
            )
            print("added new user to the database")
        else:
            print("couldn't add the newly created account to the database")

        return {
            "userID": userID,
            "accountNumber": accountNumber,
            "accountBalance": 500000,
            "currency": "NGN",
            "status": "successful",
        }

    def authenticateUser(accountNumber: int, pw: str):  # this is an endpoint
        try:
            checkUser = userAccnts.find_one({"accountNumber": accountNumber})
            if not checkUser:
                return {"status": "failed", "message": "User not found"}

            hashed_pw = checkUser["hashedPassword"]
            if isinstance(hashed_pw, str):
                hashed_pw = hashed_pw.encode()

            if not bcrypt.checkpw(pw.encode(), hashed_pw):
                return {"status": "failed", "message": "Wrong password"}

            token = bank.generate_token(checkUser)
            return {
                "status": "successful",
                "token": token,
                "message": "Login successful",
            }
        except Exception as e:
            return {"status": "failed", "response": "an error occured"}

    def generate_token(user):
        try:
            payload = {
                "accountNumber": user["accountNumber"],
                "userID": user["userID"],
                "email": user["emailAddress"],
                "name": user["firstName"],
                "exp": int(
                    (datetime.now(timezone.utc) + timedelta(days=1)).timestamp()
                ),
            }
            token = jwt.encode(payload=payload, key=JWT_SECRET, algorithm="HS256")
            return token
        except Exception as e:
            return {
                "status": "failed",
                "response": f"an error {e} occured during token generation",
            }

    def validateOTP(
        accountNumber: str, otp_code: str, otpID: str
    ) -> Literal["Invalid OTP", "OTP has expired", "Valid OTP"]:
        try:
            checkOTP = otp.find_one(
                {"accountNumber": accountNumber, "otp": otp_code, "otpID": otpID}
            )
            print(checkOTP)

            if not checkOTP:
                return "Invalid OTP"

            expires_at = datetime.fromisoformat(checkOTP["expiresAt"])
            if expires_at <= datetime.now(timezone.utc):
                return "OTP has expired"

            otp.delete_one(
                {"accountNumber": accountNumber, "otp": otp_code, "otpID": otpID}
            )

            return "Valid OTP"

        except Exception as e:
            return {"status": "failed", "response": f"An error occurred: {e}"}

    def checkBalance(senderAccntNumber: str):
        try:
            checkUser = userAccnts.find_one({"accountNumber": senderAccntNumber})
            if checkUser:
                balance, lastName, firstName = (
                    checkUser.get("accountBalance"),
                    checkUser.get("lastName"),
                    checkUser.get("firstName"),
                )
                return {
                    "response": {
                        "accountBalance": balance,
                        "accountNumber": senderAccntNumber,
                        "name": firstName + " " + lastName,
                        "currency": "NGN",
                    },
                    "status": "successful",
                }
            else:
                return {"response": "user doesn't exists in our db", "status": "failed"}
        except Exception as e:
            pass

    @celery_app.task
    def transferMoney(
        senderAccntNumber: str,
        recipientAccntNumber: str,
        amount: int,
        senderName: str,
    ):
        """this method is used to transfer funds"""
        try:
            if senderAccntNumber == recipientAccntNumber:
                return {
                    "response": "You cannot transfer money to your own account",
                    "status": "failed",
                }

            if amount <= 0:
                return {"status": "failed", "response": "Invalid transfer amount"}

            if len(senderAccntNumber) != 10 or not senderAccntNumber.isdigit():
                return {
                    "response": "Your account number is invalid",
                    "status": "failed",
                }

            if len(recipientAccntNumber) != 10:
                return {
                    "response": "Recipient account number is invalid",
                    "status": "failed",
                }
            with ThreadPoolExecutor(max_workers=3) as workers:
                w1 = workers.submit(userAccnts.find_one,{"accountNumber": senderAccntNumber})
                w2 = workers.submit(userAccnts.find_one,{"accountNumber": recipientAccntNumber})
                
                results = []
            for future in as_completed([w1, w2]):
                result = future.result()
                results.append(result)

            senderData = w1.result()
            recipientData = w2.result()

            senderEmail = senderData.get("emailAddress", "") if senderData else ""
            recipientEmail = (
                recipientData.get("emailAddress", "") if recipientData else ""
            )

            if not senderData:
                return {
                    "response": "Sender doesn't exist in database",
                    "status": "failed",
                }
            if not recipientData:
                return {
                    "response": "Recipient doesn't exist in database",
                    "status": "failed",
                }

            recipientName = f"{recipientData.get('lastName', '')} {recipientData.get('firstName', '')}".strip()

            currentBalance = senderData.get("accountBalance", 0)
            if currentBalance < amount:
                return {
                    "status": "failed",
                    "response": "You don't have enough money in your account",
                }
            print("transfering....")
            with client.start_session() as session:
                with session.start_transaction():

                    userAccnts.update_one(
                        {"accountNumber": senderAccntNumber},
                        {"$inc": {"accountBalance": -amount}},
                        session=session,
                    )

                    userAccnts.update_one(
                        {"accountNumber": recipientAccntNumber},
                        {"$inc": {"accountBalance": amount}},
                        session=session,
                    )

                    transactionID = bank.genTranID()
                    transactions.insert_one(
                        {
                            "senderInfo": {
                                "name": senderName,
                                "accountNumber": senderAccntNumber,
                            },
                            "recipientInfo": {
                                "name": recipientName,
                                "accountNumber": recipientAccntNumber,
                            },
                            "amount": amount,
                            "status": "successful",
                            "transactionID": transactionID,
                            "transactionCreatedAt": bank.current_date(),
                        },
                        session=session,
                    )

                    newBalance = userAccnts.find_one(
                        {"accountNumber": senderAccntNumber}, session=session
                    ).get("accountBalance", 0)

            bank.send_email(
                subject="Debit Alert",
                body=f"<p>Hi {senderName},<br/>You have sent {amount} NGN to account number {recipientAccntNumber}.</p>",
                to=senderEmail,
            )

            bank.send_email(
                subject="Credit Alert",
                body=f"<p>Hi {recipientName},<br/>You have received {amount} NGN from account number {senderAccntNumber}.</p>",
                to=recipientEmail,
            )

            return {
                "status": "success",
                "response": f"Transfer successful. Your new balance is {newBalance}",
                "newBalance": newBalance,
                "transactionID": transactionID,
            }

        except Exception as e:
            return {"status": "failed", "response": str(e)}

    def decodeJWT(token):
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return decoded
        except jwt.exceptions.ExpiredSignatureError:
            return {
                "response": "your session has ended, try logging in again",
                "status": "failed",
            }
        except jwt.exceptions.InvalidTokenError:
            return {
                "response": "token is invalid, try logging in again",
                "status": "failed",
            }

    @celery_app.task
    def getBankStatement(yourAccntNumber, name, email):
        # yourAccntNumber, name, email = data[0], data[1], data[2]

        recordOut = list(
            transactions.find({"senderInFo.accountNumber": yourAccntNumber})
        )
        recordIn = list(
            transactions.find({"receiverInFo.accountNumber": yourAccntNumber})
        )

        moneyOut = [everyTransaction.get("amount") for everyTransaction in recordOut]
        moneyIn = [everyTransaction.get("amount") for everyTransaction in recordIn]

        totalmoneyOut = sum(moneyOut)
        totalmoneyIn = sum(moneyIn)

        uniqueTransactors = list(
            set(
                [
                    everyTransaction.get("receiverInFo").get("name")
                    for everyTransaction in recordOut
                ]
            )
        )

        totalTransactions: int = len(recordOut) + len(recordIn)
        bank.send_email(
            subject=f"Your Bank Statement is here, {name}",
            body=(
                f"<p>Odogwu {name}!<br/>"
                f"Here is your bank statement summary:<br/>"
                f"Total Transactions: <strong>{totalTransactions}</strong><br/>"
                f"Total Money Sent: <strong>{totalmoneyOut}</strong><br/>"
                f"Total Money Received: <strong>{totalmoneyIn}</strong><br/>"
                f"Unique Transactors: <strong>{', '.join(uniqueTransactors)}</strong></p>"
            ),
            to=email,
        )
        return {
            "staus": "successful",
            "response": "your bank statement has been sent to your email",
        }

    @staticmethod
    def genApiKey():
        key = secrets.token_urlsafe(24)
        print(key)
        salt = bcrypt.gensalt()
        hashedApiKey = f"r3nci_{bcrypt.hashpw(key.encode(), salt).decode()}"
        print(hashedApiKey)
        # pass


# print(bank.createUser(firstName="ray", lastName="ayodeji",dob= "20191827", password="password83737", emailAddress="werayco@gmail.com", ethAddress="0xwhvghcsc", phoneNumber="08109219988"))
# bank.genApiKey()
# print(bank.authenticateUser(accountNumber="2264356190", pw="password83737"))
