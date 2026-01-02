from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import Sequence, Annotated, TypedDict, Literal
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt, Command
from rencie.logic import *
from agent.tools import *
from agent.ragsystem import vectordbMemory

# load_dotenv(dotenv_path=r".\all.env")
# load_dotenv()
MONGO = os.getenv("MONGODB")

client = MongoClient(MONGO)
checkpointer = MongoDBSaver(client, db_name="my_database")


SYSTEM_PROMPT = SystemMessage(
    content="""
You are Rencie, an AI assistant for finance and banking.
Answer questions clearly and concisely.
Use the vectordbMemory tool only for queries about the Rencie FAQ.
"""
)


class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intent: str
    name: str
    email: str
    amount: int
    senderAccountNumber: str
    receiverAccountNumber: str
    otpValid: Literal["Valid OTP", "Invalid OTP", "OTP has expired"]
    otpcode: str
    otpID: str
    dataComplete: bool
    otpAttempts: int
    otpDone: bool


# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash",
#     temperature=0,
# )

# chat_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0).bind_tools(
#     [vectordbMemory]
# )

from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
)

chat_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0).bind_tools([vectordbMemory])

toolnode = ToolNode([vectordbMemory])

class agents:
    @staticmethod
    def intentAgent(state: AgentState) -> AgentState:
        prompt = f"""
        Your name is Rencie, you are an intent classifier and structured data extractor for a banking assistant.

        Your task:
        1. Identify the user's intent.
        2. Extract only the data relevant to that intent.
        3. Return valid JSON ONLY — no explanations, no markdown.

        ---
        Allowed intents:
        - transfer → user wants to send money to another account
        - check_balance → user wants to know their account balance
        - bank_statement → user wants a transaction/bank statement
        - smalltalks → greetings, casual chat, or unrelated messages

        ---
        User message:
        {state["messages"][-1].content}
        ---

        Extraction rules:
        - If a field is missing or unclear, return null.
        - Do NOT guess or fabricate values.
        - Amount must be returned as a string (e.g. "5000").
        - Account numbers must be returned as strings.
        - Confidence level must be an integer between 0 and 100.

        ---

        Response format (STRICT JSON):

        If intent is "transfer":
        {{
        "confidence_level": 0-100,
        "intent": "transfer",
        "data": {{
            "receiverAccountNumber": string | null,
            "amount":  this should be an integer not string | null
        }}
        }}

        If intent is "check_balance":
        {{
        "confidence_level": 0-100,
        "intent": "check_balance",
        "data": {{}}
        }}

        If intent is "bank_statement":
        {{
        "confidence_level": 0-100,
        "intent": "bank_statement",
        "data": {{}}
        }}

        If intent is "smalltalks":
        {{
        "confidence_level": 0-100,
        "intent": "smalltalks",
        "data": {{}}
        }}
        """

        response = soParser(llm.invoke([HumanMessage(content=prompt)]).content)
        print(response)
        if response:
            if response.get("intent") == "transfer":
                receiverAccountNumber = response.get("data").get(
                    "receiverAccountNumber", None
                )
                amount = response.get("data").get("amount", None)
                return {
                    "intent": response["intent"],
                    "receiverAccountNumber": receiverAccountNumber,
                    "amount": amount,
                }
            else:
                return {"intent": response["intent"]}

    @staticmethod
    def firstRouter(state: AgentState):
        if state["intent"] in ["transfer", "check_balance", "bank_statement"]:
            return "secure"
        return "chat"

    @staticmethod
    def nameValidator(state: AgentState) -> AgentState:
        if state["intent"] == "transfer":
            recipientData = userAccnts.find_one(
                {"accountNumber": state["receiverAccountNumber"]}
            )
            recipientName = f"{recipientData.get('lastName', '')} {recipientData.get('firstName', '')}".strip()
            response = f"You are about to transfer {state['amount']} to {recipientName}"
            return {"messages": AIMessage(content=response)}

    @staticmethod
    def otpGenerator(state: AgentState) -> AgentState:
        otpCode: dict = bank.generateOTP(
            state["senderAccountNumber"], state["name"], state["email"]
        )
        print(otpCode)
        return {
            "messages": [
                AIMessage(
                    content="Your OTP has been sent to your email. Please enter the OTP to continue."
                )
            ],
            "otpID": otpCode["OtpID"],
            "otpAttempts": state.get("otpAttempts", 0),
        }

    @staticmethod
    def otpInput(state: AgentState) -> AgentState:
        user_input = interrupt("Please enter your OTP:")
        return {"otpcode": user_input}

    @staticmethod
    def otpValidator(state: AgentState) -> AgentState:
        accountNumber = state["senderAccountNumber"]
        otpCode = state["otpcode"]
        otpID = state["otpID"]
        otpresponse = bank.validateOTP(accountNumber, otpCode, otpID)
        return {"otpValid": otpresponse, "otpAttempts": state.get("otpAttempts", 0) + 1}

    @staticmethod
    def otpFailedResponse(state: AgentState) -> AgentState:
        attempts = state.get("otpAttempts", 1)
        if attempts >= 3:
            return {
                "messages": [
                    AIMessage(
                        content=f"OTP validation failed: {state['otpValid']}. Maximum attempts reached. Please start a new transaction."
                    )
                ]
            }
        return {
            "messages": [
                AIMessage(
                    content=f"OTP validation failed: {state['otpValid']}. You have {3 - attempts} attempts remaining. Please try again."
                )
            ]
        }

    @staticmethod
    def chat(state: dict):
        messages = state.get("messages", [])
        full_messages = [SYSTEM_PROMPT] + messages
        response = chat_llm.invoke(full_messages)
        updated_messages = messages + [response]  # Just use response directly

        return {"messages": updated_messages}

    @staticmethod
    def process(state: AgentState) -> AgentState:
        if state["intent"] == "transfer":
            response = bank.transferMoney(
                state["senderAccountNumber"],
                state["receiverAccountNumber"],
                state["amount"],
                state["name"],
            )

            return {
                "messages": [
                    AIMessage(content=response["response"])
                ]
            }
        elif state["intent"] == "check_balance":
            response = bank.checkBalance(state["senderAccountNumber"])
            return {
                "messages": [
                    AIMessage(content=f"Your account balance is NGN {response['response']['accountBalance']}")
                ]
            }
        else:
            response = bank.getBankStatement(
                state["senderAccountNumber"], state["name"], state["email"]
            )
            return {
                "messages": [
                    AIMessage(content="Your bank statement has been sent to your email")
                ]
            }

    @staticmethod
    def secondRouter(state: AgentState):
        if state["otpValid"] == "Valid OTP":
            return "valid"
        elif state.get("otpAttempts", 0) >= 3:
            return "max_attempts"
        return "invalid"

    @staticmethod
    def compileGraph():
        builder = StateGraph(AgentState)

        builder.add_node("intent", agents.intentAgent)
        builder.add_node("chat", agents.chat)
        builder.add_node("tools", toolnode)

        builder.add_node("nameValidator", agents.nameValidator)
        builder.add_node("otpgen", agents.otpGenerator)
        builder.add_node("otpinput", agents.otpInput)
        builder.add_node("otpvalidator", agents.otpValidator)
        builder.add_node("otpfailed", agents.otpFailedResponse)
        builder.add_node("process", agents.process)

        builder.add_edge(START, "intent")
        builder.add_conditional_edges(
            "intent", agents.firstRouter, {"secure": "nameValidator", "chat": "chat"}
        )

        builder.add_conditional_edges("chat", tools_condition)
        builder.add_edge("tools", "chat")

        builder.add_edge("nameValidator", "otpgen")
        builder.add_edge("otpgen", "otpinput")
        builder.add_edge("otpinput", "otpvalidator")

        builder.add_conditional_edges(
            "otpvalidator",
            agents.secondRouter,
            {"valid": "process", "invalid": "otpfailed", "max_attempts": "otpfailed"},
        )

        builder.add_conditional_edges(
            "otpfailed",
            lambda state: "retry" if state.get("otpAttempts", 0) < 3 else "end",
            {"retry": "otpinput", "end": END},
        )

        builder.add_edge("process", END)
        return builder.compile(checkpointer=checkpointer)

    @staticmethod
    def draw():
        compiled = agents.compileGraph()
        png_bytes = compiled.get_graph().draw_mermaid_png()
        with open("graph.png", "wb") as f:
            f.write(png_bytes)


# from pprint import pprint
compiled = agents.compileGraph()
# config = {"configurable": {"thread_id": "9"}}
# response = compiled.invoke(
#     {
#         "messages": [
#             HumanMessage(
#                 content="what can rencie do?"
#             )
#         ],
#         "senderAccountNumber": "0377052365",
#         "name": "ReaD",
#         "email": "werayco@gmail.com",
#     },
#     config=config,
# )
# print(response)

# # response = compiled.invoke({"messages":[HumanMessage(content="what's the summary of our conversation?")],"senderAccountNumber":"0377052365", "name":"ReaD", "email": "werayco@gmail.com"}, config=config)
# # print(response)

# # x = compiled.invoke(
# #     Command(resume="05977"),
# #     config=config)

# # print(x)
