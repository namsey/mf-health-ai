from openai import OpenAI
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()  # loads variables from .env

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#client = OpenAI(api_key="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")

#client = OpenAI()

def generate_explanation(fund_code, returns, volatility, drawdown, consistency, score, status):
    
    prompt = f"""
    You are a mutual fund analyst.

    Explain the fund health in simple terms.

    Data:
    Fund: {fund_code}
    Returns: 1Y={returns['return_1y']}%, 3Y={returns['return_3y']}%, 5Y={returns['return_5y']}%
    Volatility: {volatility}%
    Drawdown: {drawdown}%
    Consistency: {consistency}%
    Score: {score}
    Status: {status}

    Do NOT give buy/sell advice. Just explain.
    Keep it under 100 words.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content