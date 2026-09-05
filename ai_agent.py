import re
import requests
import pandas as pd

from database import get_products


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"


def load_products():

    rows = get_products()

    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "name",
            "category",
            "price",
            "description",
            "features",
            "stock",
        ],
    )


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
        "phone",
        "smartphone",
        "smart phone",
        "mobile",
        "iphone",
        "android phone",
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

def detect_product_type(text):
    """
    Detect the specific product type requested by the customer.
    """

    text = text.lower()

    if any(word in text for word in [
        "mouse",
        "mice"
    ]):
        return "mouse"

    if "keyboard" in text:
        return "keyboard"

    if any(word in text for word in [
        "power bank",
        "powerbank"
    ]):
        return "power bank"

    if any(word in text for word in [
        "headphone",
        "head phone",
        "headphones"
    ]):
        return "headphone"

    if any(word in text for word in [
        "earphone",
        "earphones",
        "earbuds",
        "airpods"
    ]):
        return "earbuds"

    if any(word in text for word in [
        "smartphone",
        "smart phone",
        "mobile",
        "phone",
        "iphone",
        "android"
    ]):
        return "smartphone"

    if any(word in text for word in [
        "smartwatch",
        "smart watch"
    ]):
        return "smartwatch"

    return None

def filter_products(user_message):
    """
    Apply deterministic business rules:
    - budget
    - category
    - product type
    - stock
    """

    products = load_products()

    budget = extract_budget(user_message)
    category = detect_category(user_message)
    product_type = detect_product_type(user_message)

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

    # Specific product-type filter
    if product_type is not None:

        text_columns = (
            products["name"].fillna("").str.lower()
            + " "
            + products["description"].fillna("").str.lower()
            + " "
            + products["features"].fillna("").str.lower()
        )

        products = products[
            text_columns.str.contains(
                product_type,
                case=False,
                na=False
            )
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

    # First try to get budget from the current message.
    
    products, budget = filter_products(user_message)
    print("USER MESSAGE:", user_message)
    print("BUDGET:", budget)
    print("MATCHING PRODUCTS:")
    print(products[["id", "name", "category", "price", "stock"]].to_string(index=False))

    # If current message has no budget, preserve the
    # most recently mentioned budget from conversation.
    if budget is None:
        _, history_budget = filter_products(
            
            " ".join(
                
               message["content"]
               
              for message in conversation_history[-6:]
              
            )
         )
        budget = history_budget

      # Re-apply the preserved budget to the current product list.
        if budget is not None:
          products = products[
            products["price"] <= budget
          ]

    # If the current message does not contain a budget,
    # preserve the budget from the conversation.
    if budget is None:
        
         _, history_budget = filter_products(
              " ".join(
                  message["content"]
                 for message in conversation_history[-6:]
                 )
             )
         
         budget = history_budget
    
    # -----------------------------------
    # Deterministic purchase handling
    # -----------------------------------

    purchase_intent = detect_purchase_intent(user_message)

    selected_product = detect_product(
     conversation_history,
     user_message
   )

    # If customer wants to buy and a product
    # was already selected in the conversation
    if purchase_intent and selected_product:

        if selected_product["stock"] <= 0:

            return (
                f"Sorry, {selected_product['name']} is currently "
                f"out of stock."
            )

        return (
            f"Great! {selected_product['name']} is selected for purchase.\n\n"
            f"Price: ₹{selected_product['price']:,.0f}\n"
            f"Available stock: {selected_product['stock']} units.\n\n"
            f"Please enter your name and contact details below "
            f"to confirm your order."
        )

    product_context = get_product_context(products)
    if products.empty:
        product_context = "NO MATCHING PRODUCTS FOUND"
    else:
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
        if budget is not None:
            return (
                f"Sorry, I couldn't find any products in our catalogue "
                f"that are within your budget of ₹{budget:,.0f}."
            )
        else:
            return (
                "Sorry, I couldn't find a matching product in our catalogue."
            )

    # -----------------------------------
    # AI Prompt
    # -----------------------------------

    prompt = f"""
You are ShopPilot AI, an intelligent sales and commerce assistant.

Your job is to:

1. Understand the customer's requirement.
2. 1. Recommend products ONLY from the AVAILABLE PRODUCTS list below.
3. The AVAILABLE PRODUCTS list is the ONLY source of truth.
4. NEVER recommend a product that is not in the AVAILABLE PRODUCTS list.
5. NEVER invent a product, price, stock, category, feature, or specification.
6. NEVER recommend a product from another category.
7. If AVAILABLE PRODUCTS says there are no matching products, clearly tell the customer that no matching product is available.
8. NEVER mention a product that is not present in AVAILABLE PRODUCTS.
9. NEVER invent or guess a product name, price, stock, feature, or specification.
10. If a requested product is not present in AVAILABLE PRODUCTS, clearly say that it is not available.
11. Respect all price and stock constraints.
12. Never invent products, prices, features, or stock.
13. Remember previous messages in the conversation.
14. Understand references such as:
   - "it"
   - "that one"
   - "the phone"
   - "buy this"
   - "I'll take it"
15. If the customer explicitly names a product, acknowledge it.
16. If the customer wants to purchase a product previously discussed,
    resolve references like "it", "that one", or "this" to the most recently
    relevant product and clearly identify that product.
17. If the customer wants to purchase a product, do NOT ask them to accept
    the available stock quantity. Stock is an availability value, not a
   quantity the customer must purchase.
18. If the customer wants to purchase but no product is selected,
    ask which product they want.
19. Do not invent confirmation requirements that are not part of the
    purchasing process.
20. Be concise but informative. When recommending products, provide enough
    details about each product's price, features, description, and stock.

{budget_instruction}

IMPORTANT RESPONSE RULE:

When mentioning stock, state only the number of units available.
Never imply that the customer must purchase or accept all available units.
For example, say "20 units are currently in stock", not
"Are you willing to accept the available stock of 20 units?"

AVAILABLE PRODUCTS AFTER BUSINESS RULE FILTERING:

IMPORTANT RECOMMENDATION RULE:

When the customer asks for product recommendations:

- Recommend ALL products from AVAILABLE PRODUCTS that match the customer's
  budget and requested category/type.
- Do not mention products outside the customer's budget.
- Give each recommended product:
  1. Product name
  2. Price
  3. 2-4 important features
  4. Short description
  5. Available stock
- Do not recommend only a few products when multiple matching products
  are available.
- Do not invent any information.
- After showing the recommendations, ask the customer which product
  they would like to choose.

Example format:

1. Product Name — ₹Price
   Description: ...
   Features: ...
   Stock: ... units

2. Product Name — ₹Price
   Description: ...
   Features: ...
   Stock: ... units

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
        timeout=300
    )

    response.raise_for_status()

    return response.json()["response"]

def detect_purchase_intent(text):
    """
    Detect whether the customer wants to purchase.
    """

    text = text.lower().strip()

    purchase_phrases = [
        "i want to buy",
        "i want to purchase",
        "i'd like to buy",
        "i'd like to purchase",
        "i would like to buy",
        "i would like to purchase",
        "buy it",
        "buy this",
        "purchase it",
        "purchase this",
        "order it",
        "order this",
        "i'll take it",
        "i will take it",
        "take it",
        "place the order",
        "place an order",
        "checkout",
    ]

    return any(
        phrase in text
        for phrase in purchase_phrases
    )

def detect_product(conversation_history, current_message=""):
    """
    Detect the most recently mentioned product.

    Priority:
    1. Product explicitly mentioned in the current message.
    2. Most recently mentioned product in conversation history.
    """

    products = load_products()

    # -------------------------------------------------
    # First: check the CURRENT message
    # -------------------------------------------------

    current_text = current_message.lower().strip()

    for _, product in products.iterrows():

        product_name = str(product["name"]).lower()

        if product_name in current_text:

            return {
                "id": int(product["id"]),
                "name": product["name"],
                "price": float(product["price"]),
                "stock": int(product["stock"]),
            }

    # -------------------------------------------------
    # Second: check conversation history
    # -------------------------------------------------

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