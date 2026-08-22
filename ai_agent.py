import re
import requests
import pandas as pd


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"


def load_products():
    return pd.read_csv("products.csv")


def get_product_context(products=None):
    if products is None:
        products = load_products()

    context = ""

    for _, product in products.iterrows():
        context += f"""
Product ID: {product['id']}
Name: {product['name']}
Category: {product['category']}
Price: ₹{product['price']}
Description: {product['description']}
Features: {product['features']}
Stock: {product['stock']}
---
"""

    return context


def extract_budget(text):
    """
    Extract maximum budget from natural language.
    """

    text = text.lower().replace(",", "")

    patterns = [
        r"(?:under|below|within|less than|max(?:imum)?|budget(?: is)?)[^\d]{0,10}₹?\s*(\d+)",
        r"₹\s*(\d+)",
    ]

    for pattern in patterns:

        match = re.search(pattern, text)

        if match:
            return float(match.group(1))

    return None

def detect_category(text):
    """
    Detect the product category requested by the customer.
    """

    text = text.lower()

    if any(word in text for word in [
        "headphone",
        "headphones",
        "earphone",
        "earphones",
        "earbuds",
        "airpods",
        "audio",
    ]):
        return "Audio"

    if any(word in text for word in [
        "smartphone",
        "smart phone",
        "mobile",
        "iphone",
        "android",
    ]):
        return "Smartphone"

    if any(word in text for word in [
        "mouse",
        "keyboard",
        "power bank",
        "accessory",
        "accessories",
    ]):
        return "Accessories"

    if any(word in text for word in [
        "smartwatch",
        "smart watch",
    ]):
        return "Smartwatch"

    return None

def filter_products(user_message):
    """
    Apply deterministic business rules:
    - budget
    - category
    - stock
    """

    products = load_products()

    budget = extract_budget(user_message)
    category = detect_category(user_message)

    # Budget filter
    if budget is not None:

        products = products[
            products["price"] <= budget
        ]

    # Category filter
    if category is not None:

        products = products[
            products["category"].str.lower()
            == category.lower()
        ]

    # Stock filter
    products = products[
        products["stock"] > 0
    ]

    return products, budget


def ask_agent(user_message, conversation_history=None):

    if conversation_history is None:
        conversation_history = []

    # Combine current message + recent conversation
    all_text = user_message

    for message in conversation_history[-6:]:

        all_text += " " + message["content"]

    # -----------------------------------
    # Deterministic product filtering
    # -----------------------------------

    products, budget = filter_products(all_text)

    product_context = get_product_context(products)

    # -----------------------------------
    # Conversation history
    # -----------------------------------

    history_text = ""

    for message in conversation_history[-6:]:

        history_text += (
            f"{message['role'].upper()}: "
            f"{message['content']}\n"
        )

    # -----------------------------------
    # Budget instruction
    # -----------------------------------

    budget_instruction = ""

    if budget is not None:

        budget_instruction = f"""
IMPORTANT BUSINESS RULE:

The customer's maximum budget is ₹{budget:,.0f}.

You MUST NOT recommend any product above ₹{budget:,.0f}.
"""

    # -----------------------------------
    # Handle no matching products
    # -----------------------------------

    if products.empty:

        product_context = (
            "No products satisfy the customer's "
            "budget and availability requirements."
        )

    # -----------------------------------
    # AI Prompt
    # -----------------------------------

    prompt = f"""
You are ShopPilot AI, an intelligent sales and commerce assistant.

Your job is to:

1. Understand the customer's requirement.
2. Recommend products ONLY from the catalogue provided below.
3. Respect all price and stock constraints.
4. Never invent products, prices, features, or stock.
5. Remember previous messages in the conversation.
6. Understand references such as:
   - "it"
   - "that one"
   - "the phone"
   - "buy this"
   - "I'll take it"
7. If the customer explicitly names a product, acknowledge it.
8. If the customer wants to purchase a product previously discussed,
   clearly identify that product.
9. If the customer wants to purchase but no product is selected,
   ask which product they want.
10. Be concise and helpful.

{budget_instruction}

AVAILABLE PRODUCTS AFTER BUSINESS RULE FILTERING:

{product_context}

CONVERSATION HISTORY:

{history_text}

LATEST CUSTOMER MESSAGE:

{user_message}

Respond naturally to the customer.
"""

    # -----------------------------------
    # Call Ollama
    # -----------------------------------

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["response"]


def detect_product(conversation_history):
    """
    Detect the most recently mentioned product
    from the conversation.
    """

    products = load_products()

    # Search newest messages first
    for message in reversed(conversation_history):

        message_text = message["content"].lower()

        for _, product in products.iterrows():

            product_name = str(product["name"]).lower()

            if product_name in message_text:

                return {
                    "id": int(product["id"]),
                    "name": product["name"],
                    "price": float(product["price"]),
                    "stock": int(product["stock"]),
                }

    return None