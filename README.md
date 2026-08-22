# ShopPilot AI 🛍️

## AI-Powered Sales & Commerce Agent

ShopPilot AI is an AI-powered commerce assistant designed to help small businesses convert customer conversations into product recommendations, qualified leads, and orders.

The system combines natural-language understanding using a local LLM with deterministic business rules for product availability, category matching, and budget constraints.

---

## Problem

Small businesses often lose potential customers because they cannot respond instantly to product queries, understand customer requirements, recommend suitable products, or convert conversations into structured leads and orders.

Traditional chatbots are also unreliable when business rules such as price limits and stock availability are involved.

ShopPilot AI addresses this problem by combining conversational AI with deterministic commerce logic.

---

## Solution

ShopPilot AI provides a conversational sales agent that can:

- Understand customer requirements in natural language
- Recommend relevant products
- Respect customer budget constraints
- Filter products by category
- Check stock availability
- Maintain conversation context
- Detect purchase intent
- Create customer orders
- Store leads and orders in SQLite
- Display business metrics through a dashboard

---

## Architecture

```text
Customer
   │
   ▼
Streamlit Interface
   │
   ▼
Conversation Context
   │
   ├───────────────┐
   │               │
   ▼               ▼
Business Rules     Llama 3.2
   │               │
   ├── Budget      │
   ├── Category    │
   └── Stock       │
   │               │
   └───────┬───────┘
           ▼
     Product Recommendation
           │
           ▼
      Purchase Intent
           │
           ▼
       Order Creation
           │
           ▼
        SQLite DB
           │
           ▼
   Business Dashboard
   