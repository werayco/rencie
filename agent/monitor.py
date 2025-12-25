from evidently import Dataset, DataDefinition
from evidently.descriptors import (
    LLMEval,
    DeclineLLMEval,
    FaithfulnessLLMEval,
    BERTScore,
    SentenceCount,
    CorrectnessLLMEval,
    IncludesWords,
    SemanticSimilarity,
    Sentiment,
)
import pandas as pd
import warnings
from pymongo import MongoClient
import os
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()


class monitorllm:
    "this class encapsulates the monitoring of the llm agent"

    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO"))
        self.db = self.client["responses"]
        self.collection = self.db["mdresponses"]

    def analysisData(self) -> pd.DataFrame:
        "retrieves the model's reponse and the user's query from my db"
        data = list(self.collection.find({}, {"_id": 0}))
        return pd.DataFrame(data)

    def responseAnalysis(self):
        datadef = DataDefinition(text_columns=["user's_query", "model's_response"])
        dataframe = self.analysisData()
        evidentlyAIDataframe = Dataset.from_pandas(dataframe, datadef)
        evidentlyAIDataframe.add_descriptors(
            descriptors=[
                IncludesWords(
                    column_name="model's_response",
                    words_list=["Hello", "good day"],
                    alias="include words",
                ),
                BERTScore(
                    columns=["user's_query", "model's_response"], alias="BertScore"
                ),
                SemanticSimilarity(
                    columns=["user's_query", "model's_response"], alias="hallucination"
                ),
            ]
        )
        evidentlyAIDataframe.as_dataframe().to_csv("./report.csv", index=False)
        print(dataframe)


# obj = monitorllm()
# obj.responseAnalysis()
