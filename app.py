import os
import json
import html
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import razorpay

from ai_agent import (
    ask_agent,
    load_products,
    detect_product,
)

from database import (
    init_database,
    create_lead,
    create_order,
    get_leads,
    get_orders,
    get_order_by_razorpay_id,
    mark_order_paid,
)

# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# ---------------------------------------------------------
# DEMO PAYMENT AMOUNT
# ---------------------------------------------------------
# Product price can be ₹29,999.
# For Razorpay TEST checkout we temporarily charge ₹100.
# This is only for project demonstration.
DEMO_PAYMENT_AMOUNT = 100

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    st.error(
        "Razorpay credentials are missing. "
        "Please check your .env file."
    )
    st.stop()

razorpay_client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET
    )
)

def sync_razorpay_payment(razorpay_order_id):
    """
    Check Razorpay for a successful payment and update
    the local order + inventory.
    """

    try:
        payments = razorpay_client.order.payments(
            razorpay_order_id
        )

        items = payments.get("items", [])

        for payment in items:

            if payment.get("status") == "captured":

                payment_id = payment.get("id")

                local_order = get_order_by_razorpay_id(
                    razorpay_order_id
                )

                if not local_order:
                    return False, "Local order not found."

                # Already paid → don't reduce stock again
                if local_order[5] == "Paid":
                    return True, "Payment already recorded."

                # Get product ID
                product_name = local_order[3]

                products = load_products()

                product_id = None

                for product in products.to_dict("records"):
                    if product["name"] == product_name:
                        product_id = int(product["id"])
                        break

                if product_id is None:
                    return False, "Product not found."

                # Mark order as Paid
                updated = mark_order_paid(
                    razorpay_order_id,
                    payment_id
                )

                if not updated:
                    return False, "Order could not be updated." 

                return True, payment_id

        return False, "Payment has not been captured yet."

    except Exception as e:

        return False, str(e)

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ShopPilot AI",
    page_icon="🛍️",
    layout="wide",
)


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
        background:
            radial-gradient(circle at top left, rgba(84, 160, 255, 0.22), transparent 26%),
            radial-gradient(circle at bottom right, rgba(47, 209, 146, 0.18), transparent 28%),
            linear-gradient(180deg, #07111f 0%, #0f172a 100%);
        color: #e5eefb;
    }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 4rem;
        max-width: 1500px;
    }

    .top-shell {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 24px;
        padding: 1.4rem 1.5rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 12px 35px rgba(15, 23, 42, 0.3);
        margin-bottom: 1.25rem;
    }

    .eyebrow {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: #7dd3fc;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    h1 {
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.05em !important;
        margin-bottom: 0.25rem !important;
        color: #f8fbff !important;
    }

    .subheader-compact {
        font-size: 1.02rem;
        color: #c8d7f2;
        margin-bottom: 0.5rem;
    }

    .sidebar-card {
        background: linear-gradient(180deg, rgba(15, 118, 110, 0.18), rgba(15, 23, 42, 0.82));
        border: 1px solid rgba(125, 211, 252, 0.18);
        border-radius: 18px;
        padding: 0.9rem 0.9rem 0.5rem;
        margin-bottom: 0.8rem;
    }

    [data-testid="stSidebar"] {
        background: rgba(7, 17, 31, 0.9);
        border-right: 1px solid rgba(148, 163, 184, 0.12);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(14, 116, 144, 0.18), rgba(37, 99, 235, 0.08));
        border: 1px solid rgba(125, 211, 252, 0.18);
        border-radius: 20px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
        height: 100%;
    }

    .info-card {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }

    .pill {
        display: inline-block;
        background: rgba(96, 165, 250, 0.12);
        border: 1px solid rgba(96, 165, 250, 0.2);
        border-radius: 999px;
        padding: 0.42rem 0.8rem;
        font-size: 0.75rem;
        color: #bae6fd;
        font-weight: 600;
        margin: 0 0.4rem 0.4rem 0;
    }

    .chat-message {
        background: rgba(15, 23, 42, 0.9) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        border-radius: 18px !important;
    }

    div[data-testid="stChatMessage"] {
        margin-bottom: 0.8rem;
    }

    .stTabs [role="tablist"] {
        gap: 0.6rem;
    }

    .stTabs [role="tab"] {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 12px 12px 0 0;
        color: #dbeafe;
    }

    .stTabs [role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, rgba(14, 116, 144, 0.85), rgba(37, 99, 235, 0.8));
        border-color: rgba(147, 197, 253, 0.4);
    }

    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.14);
    }

    .section-shell {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 20px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }

    .mini-stat {
        background: linear-gradient(135deg, rgba(14, 116, 144, 0.18), rgba(37, 99, 235, 0.08));
        border: 1px solid rgba(125, 211, 252, 0.18);
        border-radius: 18px;
        padding: 0.9rem 1rem;
        height: 100%;
    }

    .mini-stat-label {
        font-size: 0.7rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7dd3fc;
        font-weight: 700;
    }

    .mini-stat-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: #f8fbff;
        margin-top: 0.2rem;
    }

    .dashboard-shell {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 24px;
        padding: 1.1rem;
        margin-top: 1rem;
    }

    .dashboard-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .dashboard-title {
        font-size: 1.2rem;
        font-weight: 800;
        color: #f8fbff;
    }

    .dashboard-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.4rem 0.7rem;
        border-radius: 999px;
        background: rgba(45, 212, 191, 0.12);
        border: 1px solid rgba(45, 212, 191, 0.28);
        color: #99f6e4;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .dashboard-stat {
        background: linear-gradient(180deg, rgba(9, 18, 35, 0.9), rgba(15, 23, 42, 0.8));
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 18px;
        padding: 1rem;
        min-height: 120px;
    }

    .dashboard-stat .label {
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7dd3fc;
        font-weight: 700;
    }

    .dashboard-stat .value {
        margin-top: 0.8rem;
        font-size: 2.2rem;
        font-weight: 800;
        color: #f8fbff;
        line-height: 1.1;
    }

    .dashboard-stat .delta {
        margin-top: 0.45rem;
        font-size: 0.76rem;
        color: #bbf7d0;
        font-weight: 600;
    }

    .panel-box {
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 20px;
        padding: 1rem;
        height: 100%;
    }

    .panel-box h4 {
        margin: 0 0 0.8rem 0;
        color: #f8fbff;
        font-size: 1rem;
        font-weight: 700;
    }

    .ops-header {
        background: linear-gradient(110deg, #102a2a 0%, #123b3b 58%, #173b4a 100%);
        border: 1px solid rgba(163, 230, 53, 0.28);
        border-radius: 8px;
        padding: 1.35rem 1.5rem;
        margin: 0.5rem 0 1rem;
        box-shadow: 0 18px 35px rgba(2, 12, 18, 0.28);
    }

    .ops-kicker {
        color: #bef264;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }

    .ops-title {
        color: #f7fee7;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
        margin-top: 0.4rem;
    }

    .ops-subtitle {
        color: #c7d7d8;
        font-size: 0.9rem;
        margin-top: 0.45rem;
    }

    .ops-tag {
        color: #d9f99d;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .brief-header {
        background: #f4eadb;
        border-left: 7px solid #f97316;
        border-radius: 4px;
        padding: 1.5rem 1.6rem;
        margin: 0.5rem 0 1.1rem;
        box-shadow: 0 14px 30px rgba(3, 10, 20, 0.22);
    }

    .brief-kicker {
        color: #9a3412;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }

    .brief-title {
        color: #172033;
        font-size: 2rem;
        font-weight: 850;
        line-height: 1.1;
        margin-top: 0.35rem;
    }

    .brief-subtitle {
        color: #475569;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }

    .revenue-banner {
        background: linear-gradient(135deg, #f97316, #ea580c);
        border-radius: 4px;
        padding: 1.25rem 1.35rem;
        min-height: 148px;
        box-shadow: 0 14px 28px rgba(234, 88, 12, 0.22);
    }

    .revenue-label {
        color: #ffedd5;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .revenue-value {
        color: #fff7ed;
        font-size: 2.35rem;
        font-weight: 850;
        margin-top: 0.65rem;
    }

    .revenue-note {
        color: #fed7aa;
        font-size: 0.78rem;
        margin-top: 0.35rem;
    }

    .brief-section-title {
        color: #f8fbff;
        font-size: 1.05rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }

    .cockpit-header {
        background: #111827;
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0 0.8rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .cockpit-kicker {
        color: #94a3b8;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }

    .cockpit-title {
        color: #f8fafc;
        font-size: 1.65rem;
        font-weight: 800;
        margin-top: 0.25rem;
    }

    .cockpit-live {
        color: #86efac;
        border: 1px solid rgba(134, 239, 172, 0.3);
        border-radius: 999px;
        padding: 0.45rem 0.75rem;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }

    .cockpit-revenue {
        background: linear-gradient(145deg, #172554, #164e63);
        border: 1px solid rgba(125, 211, 252, 0.28);
        border-radius: 14px;
        padding: 1.4rem;
        min-height: 210px;
        box-shadow: 0 18px 32px rgba(2, 8, 23, 0.28);
    }

    .cockpit-revenue-label {
        color: #bae6fd;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }

    .cockpit-revenue-value {
        color: #f0f9ff;
        font-size: 2.8rem;
        font-weight: 850;
        line-height: 1;
        margin-top: 1rem;
    }

    .cockpit-revenue-note {
        color: #bae6fd;
        font-size: 0.8rem;
        margin-top: 0.7rem;
    }

    .cockpit-rail {
        background: rgba(15, 23, 42, 0.84);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 1rem;
        height: 100%;
    }

    .cockpit-rail-title {
        color: #e2e8f0;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.7rem;
    }

    .ledger-header {
        background: #e7e5e4;
        border: 1px solid #a8a29e;
        border-radius: 2px;
        padding: 1.25rem 1.4rem;
        margin: 0.5rem 0 0.8rem;
    }

    .ledger-kicker {
        color: #57534e;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
    }

    .ledger-title {
        color: #1c1917;
        font-size: 1.9rem;
        font-weight: 850;
        letter-spacing: -0.03em;
        margin-top: 0.35rem;
    }

    .ledger-subtitle {
        color: #57534e;
        font-size: 0.86rem;
        margin-top: 0.35rem;
    }

    .ledger-rule {
        border-top: 3px solid #1c1917;
        margin: 0.8rem 0 1rem;
    }

    .ledger-revenue {
        background: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 2px;
        padding: 1.1rem 1.25rem;
        min-height: 154px;
    }

    .ledger-revenue-label {
        color: #92400e;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }

    .ledger-revenue-value {
        color: #451a03;
        font-size: 2.35rem;
        font-weight: 850;
        margin-top: 0.8rem;
    }

    .ledger-revenue-note {
        color: #92400e;
        font-size: 0.76rem;
        margin-top: 0.3rem;
    }

    .ledger-status {
        background: rgba(28, 25, 23, 0.88);
        border-radius: 2px;
        padding: 1rem 1.15rem;
        min-height: 154px;
    }

    .ledger-status-title {
        color: #d6d3d1;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-bottom: 0.7rem;
    }

    .ledger-status-line {
        color: #fafaf9;
        font-size: 0.9rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(214, 211, 209, 0.16);
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .status-pill.success {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.2);
        color: #bbf7d0;
    }

    .status-pill.warning {
        background: rgba(251, 191, 36, 0.1);
        border: 1px solid rgba(251, 191, 36, 0.2);
        color: #fef3c7;
    }

    .catalog-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
    }

    .catalog-card {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(15, 23, 42, 0.72));
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 20px;
        padding: 1rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.16);
        height: 100%;
    }

    .catalog-card .product-name {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fbff;
        margin-bottom: 0.4rem;
    }

    .catalog-card .product-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }

    .catalog-card .price {
        font-size: 1.2rem;
        font-weight: 800;
        color: #7dd3fc;
    }

    .catalog-card .stock {
        font-size: 0.72rem;
        font-weight: 700;
        border-radius: 999px;
        padding: 0.36rem 0.6rem;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.24);
        color: #bbf7d0;
    }

    .catalog-card .stock.low {
        background: rgba(251, 191, 36, 0.1);
        border-color: rgba(251, 191, 36, 0.24);
        color: #fef3c7;
    }

    .catalog-card .description {
        color: #cbd5e1;
        font-size: 0.88rem;
        line-height: 1.55;
        margin: 0.5rem 0;
    }

    .catalog-card .features {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.6rem;
    }

    .catalog-card .feature-pill {
        display: inline-block;
        border-radius: 999px;
        padding: 0.26rem 0.52rem;
        background: rgba(96, 165, 250, 0.1);
        border: 1px solid rgba(96, 165, 250, 0.18);
        color: #dbeafe;
        font-size: 0.68rem;
        font-weight: 600;
    }

    .table-panel {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 18px;
        padding: 0.8rem;
        margin-top: 1rem;
    }

    .stButton > button {
        border-radius: 12px;
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        color: white;
        border: none;
        font-weight: 700;
        padding: 0.7rem 1rem;
        transition: 0.2s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #0284c7, #1d4ed8);
        box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35);
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(15, 23, 42, 0.88);
        color: #e2e8f0;
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
    }

    .stForm {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 18px;
        padding: 1rem;
    }

    .success-box {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 14px;
        padding: 0.8rem 1rem;
        color: #d1fae5;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

init_database()

# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="top-shell">
        <div class="eyebrow">Smart commerce assistant</div>
        <h1>🛍️ ShopPilot AI</h1>
        <div class="subheader-compact">
            AI-powered sales and commerce agent for product discovery, purchase guidance, and order management.
        </div>
        <div>
            <span class="pill">Smart recommendations</span>
            <span class="pill">Order flow</span>
            <span class="pill">Inventory-aware</span>
            <span class="pill">Razorpay demo</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.markdown(
    """
    <div class="sidebar-card">
        <div style="font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.12em; color: #7dd3fc; font-weight: 700; margin-bottom: 0.35rem;">Navigation</div>
        <div style="font-size: 1.2rem; font-weight: 700; color: #f8fbff;">ShopPilot Console</div>
    </div>
    """,
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Go to",
    [
        "🤖 AI Sales Agent",
        "📦 Product Catalogue",
        "📊 Business Dashboard",
    ],
)

# =========================================================
# AI SALES AGENT
# =========================================================

if page == "🤖 AI Sales Agent":

    st.markdown(
        """
        <div class="info-card">
            <div style="font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.14em; color: #7dd3fc; font-weight: 700; margin-bottom: 0.35rem;">AI Concierge</div>
            <div style="font-size: 1.35rem; font-weight: 700; color: #f8fbff;">Ask about products, budgets, or recommendations.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # SESSION STATE
    # -----------------------------------------------------

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "order_created" not in st.session_state:
        st.session_state.order_created = False

    if "razorpay_order_id" not in st.session_state:
        st.session_state.razorpay_order_id = None

    if "payment_processed" not in st.session_state:
        st.session_state.payment_processed = False

    # -----------------------------------------------------
    # SHOW CHAT HISTORY
    # -----------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.write(message["content"])

    # -----------------------------------------------------
    # CHAT INPUT
    # -----------------------------------------------------

    user_message = st.chat_input(
        "Example: I need headphones under ₹5000"
    )

    if user_message:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        with st.chat_message("user"):
            st.write(user_message)

        with st.chat_message("assistant"):

            with st.spinner(
                "AI is analyzing your requirement..."
            ):

                try:

                    response = ask_agent(
                        user_message,
                        st.session_state.messages[:-1],
                    )

                    st.write(response)

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": response,
                        }
                    )

                except Exception as e:

                    st.error(
                        f"AI service error: {e}"
                    )

    # =====================================================
    # PURCHASE DETECTION
    # =====================================================

    purchase_keywords = [
        "buy",
        "purchase",
        "order",
        "checkout",
        "take it",
        "i'll take",
        "i will take",
        "i want it",
        "yes buy",
        "yes order",
    ]

    latest_user_message = ""

    if st.session_state.messages:

        for message in reversed(
            st.session_state.messages
        ):

            if message["role"] == "user":

                latest_user_message = (
                    message["content"].lower()
                )

                break

    wants_to_buy = any(
        keyword in latest_user_message
        for keyword in purchase_keywords
    )

    # =====================================================
    # PURCHASE FORM
    # =====================================================

    if (
        wants_to_buy
        and not st.session_state.order_created
    ):

        selected_product = detect_product(
          st.session_state.messages,
          st.session_state.messages[-1]["content"]
        )

        if selected_product:

            st.divider()

            st.subheader("🛒 Ready to Purchase?")

            st.write(
                f"### {selected_product['name']}"
            )

            st.write(
                f"Product Price: "
                f"**₹{selected_product['price']:,.0f}**"
            )

            st.write(
                f"Available stock: "
                f"**{selected_product['stock']} units**"
            )

            if selected_product["stock"] <= 0:

                st.error(
                    "Sorry, this product is currently "
                    "out of stock."
                )

            else:

                # -------------------------------------------------
                # CUSTOMER DETAILS
                # -------------------------------------------------

                with st.form("purchase_form"):

                    buyer_name = st.text_input(
                        "Customer Name"
                    )

                    buyer_contact = st.text_input(
                        "Phone / Email"
                    )

                    confirm_purchase = (
                        st.form_submit_button(
                            "💳 Proceed to Payment"
                        )
                    )

                # -------------------------------------------------
                # CREATE RAZORPAY ORDER
                # -------------------------------------------------

                if confirm_purchase:

                    if not buyer_name or not buyer_contact:

                        st.warning(
                            "Please enter your name "
                            "and phone/email."
                        )

                    else:

                        try:

                            # -------------------------------------
                            # Create Razorpay TEST order
                            # -------------------------------------

                            razorpay_order = (
                                razorpay_client.order.create(
                                    {
                                        "amount":
                                            DEMO_PAYMENT_AMOUNT * 100,
                                        "currency": "INR",
                                        "receipt":
                                            f"shop_{selected_product['id']}",
                                        "notes": {
                                            "product":
                                                selected_product["name"],
                                            "customer":
                                                buyer_name,
                                        },
                                    }
                                )
                            )

                            razorpay_order_id = (
                                razorpay_order["id"]
                            )

                            st.session_state.razorpay_order_id = (
                                razorpay_order_id
                            )
                            # Reset payment state for every new order
                            st.session_state.payment_processed = False
                            st.session_state.order_created = False

                            # Store customer/product information in session
                            # AND create a local Pending order immediately.
                            # This means payment success can still be linked
                            # to the order using the Razorpay Order ID.
                            local_pending_id = create_order(
                                
                              
                                 buyer_name,
                                 buyer_contact,
                                 selected_product["name"],
                                 selected_product["price"],
                                 status="Pending",
                                 razorpay_order_id=razorpay_order_id,
                                  product_id=selected_product["id"],
                                )

                            st.session_state.pending_order = {
                                "local_order_id":
                                    local_pending_id,
                                "customer_name":
                                    buyer_name,
                                "contact":
                                    buyer_contact,
                                "product":
                                    selected_product["name"],
                                "product_id":
                                    selected_product["id"],
                                "price":
                                    selected_product["price"],
                            }

                            st.success(
                                "Razorpay test order created!"
                            )

                        except Exception as e:

                            st.error(
                                f"Unable to create Razorpay "
                                f"order: {e}"
                            )

            # =================================================
            # RAZORPAY CHECKOUT
            # =================================================

            if st.session_state.razorpay_order_id:

                razorpay_order_id = (
                    st.session_state.razorpay_order_id
                )

                pending_order = st.session_state.get(
                    "pending_order"
                )

                if pending_order:

                    st.divider()

                    with st.container(border=True):
                        st.subheader(
                            "💳 Complete Payment"
                        )

                        st.markdown(
                            """
                            <style>
                            .payment-demo-banner {
                                display: flex;
                                align-items: center;
                                gap: 12px;
                                padding: 16px 18px;
                                border-radius: 14px;
                                background: linear-gradient(
                                    135deg,
                                    rgba(40, 124, 190, 0.28),
                                    rgba(70, 165, 225, 0.12)
                                );
                                border: 1px solid rgba(123, 210, 255, 0.45);
                                color: #ebf7ff;
                                font-size: 1.05rem;
                                font-weight: 600;
                                margin-bottom: 1rem;
                                box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
                            }
                            .payment-demo-icon {
                                width: 28px;
                                height: 28px;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                border-radius: 8px;
                                background: rgba(255,255,255,0.12);
                                font-size: 1rem;
                            }
                            </style>
                            <div class="payment-demo-banner">
                                <div class="payment-demo-icon">🛡️</div>
                                <div>No real money will be charged.</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # -------------------------------------------------
                        # SAFE VALUES FOR JAVASCRIPT
                        # -------------------------------------------------

                        js_key_id = json.dumps(
                            RAZORPAY_KEY_ID
                        )

                        js_order_id = json.dumps(
                            razorpay_order_id
                        )

                        js_name = json.dumps(
                            pending_order["customer_name"]
                        )

                        js_contact = json.dumps(
                            pending_order["contact"]
                        )

                        js_amount = (
                            DEMO_PAYMENT_AMOUNT * 100
                        )

                        # -------------------------------------------------
                        # RAZORPAY CHECKOUT
                        # -------------------------------------------------

                        checkout_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">

                            <script src=
                            "https://checkout.razorpay.com/v1/checkout.js">
                            </script>

                            <style>

                            body {{
                                margin: 0;
                                padding: 10px;
                                background: transparent;
                                font-family: Arial, sans-serif;
                            }}

                            .payment-box {{
                                padding: 22px 22px 18px;
                                border-radius: 22px;
                                border: 1px solid rgba(144, 191, 223, 0.35);
                                background: linear-gradient(
                                    135deg,
                                    rgba(9, 17, 26, 0.97),
                                    rgba(20, 28, 38, 0.96)
                                );
                                box-shadow: 0 12px 24px rgba(0, 0, 0, 0.28);
                            }}

                            .payment-header {{
                                display: flex;
                                align-items: center;
                                gap: 12px;
                                margin-bottom: 20px;
                            }}

                            .payment-logo {{
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                width: 40px;
                                height: 40px;
                                border-radius: 12px;
                                background: linear-gradient(
                                    135deg,
                                    #6cc5f5,
                                    #3d9ae5
                                );
                                box-shadow: 0 8px 16px rgba(61, 154, 229, 0.35);
                                font-size: 22px;
                            }}

                            .payment-title {{
                                color: #f4f8fb;
                                font-size: 28px;
                                font-weight: 800;
                                letter-spacing: -0.03em;
                                margin: 0;
                            }}

                            .payment-meta {{
                                display: flex;
                                flex-direction: column;
                                gap: 14px;
                                margin-bottom: 22px;
                            }}

                            .payment-row {{
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                gap: 12px;
                                padding: 12px 14px;
                                border-radius: 12px;
                                background: rgba(255, 255, 255, 0.02);
                                border: 1px solid rgba(255, 255, 255, 0.05);
                            }}

                            .detail-label {{
                                font-size: 13px;
                                font-weight: 700;
                                color: #a7bac8;
                                text-transform: uppercase;
                                letter-spacing: 0.06em;
                            }}

                            .detail-value {{
                                font-size: 18px;
                                font-weight: 700;
                                color: #f3f7fb;
                            }}

                            .product-value {{
                                font-size: 20px;
                                font-weight: 800;
                                color: #ffffff;
                                text-align: right;
                            }}

                            button {{
                                width: 100%;
                                background: linear-gradient(
                                    135deg,
                                    #6cc5f5,
                                    #3d9ae5
                                );
                                color: white;
                                border: none;
                                border-radius: 16px;
                                padding: 18px 24px;
                                font-size: 20px;
                                font-weight: 800;
                                cursor: pointer;
                                box-shadow: 0 12px 24px rgba(61, 154, 229, 0.3);
                                transition: transform 0.15s ease, box-shadow 0.15s ease;
                            }}

                            button:hover {{
                                background: linear-gradient(
                                    135deg,
                                    #7fd0ff,
                                    #4aa6eb
                                );
                                box-shadow: 0 16px 28px rgba(61, 154, 229, 0.38);
                            }}

                            button:active {{
                                transform: translateY(1px);
                            }}

                            </style>
                        </head>

                        <body>

                        <div class="payment-box">

                            <div class="payment-header">
                                <div class="payment-logo">💳</div>
                                <div class="payment-title">
                                    Razorpay Test Payment
                                </div>
                            </div>

                            <div class="payment-meta">
                                <div class="payment-row">
                                    <span class="detail-label">Demo amount</span>
                                    <span class="detail-value">
                                        ₹{DEMO_PAYMENT_AMOUNT:,}
                                    </span>
                                </div>

                                <div class="payment-row">
                                    <span class="detail-label">Product</span>
                                    <span class="product-value">
                                        {html.escape(
                                            pending_order["product"]
                                        )}
                                    </span>
                                </div>
                            </div>

                            <button onclick="startPayment()">
                                💳 Pay ₹{DEMO_PAYMENT_AMOUNT:,}
                            </button>

                        </div>

                        <script>

                        function startPayment() {{

                            var options = {{

                                "key": {js_key_id},

                                "amount": {js_amount},

                                "currency": "INR",

                                "name": "ShopPilot AI",

                                "description":
                                    "Test payment for "
                                    + {js_name},

                                "order_id":
                                    {js_order_id},

                                "prefill": {{

                                    "name":
                                        {js_name},

                                    "email":
                                        {js_contact}

                                }},

                                "theme": {{

                                    "color": "#3399cc"

                                }},

                                "handler":
                                    function(response) {{

                                        var params =
                                            new URLSearchParams();

                                        params.set(
                                            "payment_success",
                                            "1"
                                        );

                                        params.set(
                                            "razorpay_payment_id",
                                            response.razorpay_payment_id
                                        );

                                        params.set(
                                            "razorpay_order_id",
                                            response.razorpay_order_id
                                        );

                                        params.set(
                                            "razorpay_signature",
                                            response.razorpay_signature
                                        );

                                        window.parent.location.href =
                                            window.parent.location.origin
                                            +
                                            window.parent.location.pathname
                                            +
                                            "?"
                                            +
                                            params.toString();

                                    }},

                                "modal": {{

                                    "ondismiss":
                                        function() {{

                                            console.log(
                                                "Payment popup closed"
                                            );

                                        }}

                                }}

                            }};

                            var rzp =
                                new Razorpay(options);

                            rzp.on(
                                "payment.failed",
                                function(response) {{

                                    alert(
                                        "Payment failed: "
                                        +
                                        response.error.description
                                    );

                                }}
                            );

                            rzp.open();

                        }}

                        </script>

                        </body>
                        </html>
                        """

                        components.html(
                            checkout_html,
                            height=280,
                        )
                        
                        st.markdown("### 🔄 Payment Confirmation")
                        if st.button(
                            "✅ Sync Payment Status",
                            key=f"sync_payment_{razorpay_order_id}"
                            
                        ):
                            success, result = sync_razorpay_payment(
                                razorpay_order_id
                            )
                            if success:
                                st.success(
                                    "🎉 Payment confirmed successfully!"
                                )
                                if result != "Payment already recorded.":
                                    st.info(
                                        f"Payment ID: {result}"
                                    )
                                    st.rerun()
                                    
                            else:
                                st.warning(
                                     f"Payment not confirmed: {result}"
                                )


                        st.caption(
                            "Razorpay TEST mode — "
                            "No real money will be charged."
                        )

    # =====================================================
    # PAYMENT SUCCESS HANDLING
    # =====================================================

    payment_success = st.query_params.get(
        "payment_success"
    )

    payment_id = st.query_params.get(
        "razorpay_payment_id"
    )

    returned_order_id = st.query_params.get(
        "razorpay_order_id"
    )

    payment_signature = st.query_params.get(
        "razorpay_signature"
    )

    if (
        payment_success == "1"
        and payment_id
        and returned_order_id
        and payment_signature
        and not st.session_state.payment_processed
    ):

        try:

            # ---------------------------------------------
            # VERIFY PAYMENT SIGNATURE
            # ---------------------------------------------

            razorpay_client.utility.verify_payment_signature(
                {
                    "razorpay_order_id":
                        returned_order_id,

                    "razorpay_payment_id":
                        payment_id,

                    "razorpay_signature":
                        payment_signature,
                }
            )

            # ---------------------------------------------
            # FIND THE LOCAL PENDING ORDER
            # ---------------------------------------------

            local_order = get_order_by_razorpay_id(
                returned_order_id
            )

            if not local_order:
                st.error(
                    "Payment verified, but the local order "
                    "could not be found."
                )
            elif local_order[5] == "Paid":
                st.session_state.payment_processed = True
                st.session_state.order_created = True
                st.success("🎉 Payment already recorded.")
            else:

                # ---------------------------------------------
                # GET PRODUCT ID FROM PRODUCT NAME
                # ---------------------------------------------

                pending_order = st.session_state.get(
                    "pending_order"
                )

                if pending_order:
                    product_id = pending_order["product_id"]
                    product_name = pending_order["product"]
                else:
                    product_name = local_order[3]
                    product_id = None

                    for product in load_products().to_dict("records"):
                        if product["name"] == product_name:
                            product_id = product["id"]
                            break

                if product_id is None:
                    st.error(
                        "Payment verified, but product information "
                        "could not be found."
                    )
                else:

                    # mark_order_paid atomically reduces stock and updates
                    # the same pending order with Paid status and payment ID.
                    updated = mark_order_paid(
                        returned_order_id,
                        payment_id
                    )

                    if not updated:
                        st.error(
                            "Payment verified, but the local order "
                            "could not be updated."
                        )

                    if updated:
                        local_order_id = local_order[0]

                        st.session_state.payment_processed = True
                        st.session_state.order_created = True

                        st.success(
                            "🎉 Payment successful!"
                        )

                        st.success(
                            f"""
Order confirmed successfully.

Product: {local_order[3]}

Product Price:
₹{local_order[4]:,.0f}

Payment ID:
{payment_id}

Order ID:
{local_order_id}
"""
                        )

                        st.balloons()

                        # Clear query parameters after successful processing.
                        st.query_params.clear()

        except Exception as e:

            st.error(
                f"Payment verification failed: {e}"
            )

    # =====================================================
    # LEAD CAPTURE
    # =====================================================

    st.divider()

    st.subheader(
        "📋 Interested in a product?"
    )

    with st.form("lead_form"):

        customer_name = st.text_input(
            "Your Name"
        )

        contact = st.text_input(
            "Email / Phone"
        )

        requirement = st.text_area(
            "What are you looking for?"
        )

        recommended_product = st.text_input(
            "Recommended Product"
        )

        submitted = st.form_submit_button(
            "Save as Lead"
        )

        if submitted:

            if (
                customer_name
                and contact
                and requirement
            ):

                create_lead(
                    customer_name,
                    contact,
                    requirement,
                    recommended_product,
                )

                st.success(
                    "Lead successfully created!"
                )

            else:

                st.warning(
                    "Please fill in your name, "
                    "contact and requirement."
                )


# =========================================================
# PRODUCT CATALOGUE
# =========================================================

elif page == "📦 Product Catalogue":

    st.subheader("📦 Product Catalogue")
    products = load_products()

    product_count = len(products)
    low_stock_count = int((products["stock"] <= 5).sum())
    total_inventory_value = float(products["price"].sum())

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Products", product_count)
    with metric_cols[1]:
        st.metric("Low stock", low_stock_count)
    with metric_cols[2]:
        st.metric("Catalog value", f"₹{total_inventory_value:,.0f}")

    st.write("")

    product_cols = st.columns(3)
    for idx, row in products.iterrows():
        column = product_cols[idx % 3]
        with column:
            stock = int(row["stock"])
            status = "Low stock" if stock <= 5 else "In stock"
            stock_class = "low" if stock <= 5 else ""
            feature_list = [
                item.strip()
                for item in str(row["features"]).split(";")
                if item.strip()
            ]
            feature_html = "".join(
                f'<span class="feature-pill">{html.escape(item)}</span>'
                for item in feature_list[:4]
            )

            st.markdown(
                f"""
                <div class="catalog-card">
                    <div class="product-name">{html.escape(str(row['name']))}</div>
                    <div class="product-meta">
                        <div class="price">₹{float(row['price']):,.0f}</div>
                        <div class="stock {stock_class}">{status}</div>
                    </div>
                    <div class="description">{html.escape(str(row['description']))}</div>
                    <div style="font-size: 0.75rem; color: #9fb5d5; margin-top: 0.5rem; margin-bottom: 0.6rem;">
                        Units: <strong>{stock}</strong>
                    </div>
                    <div class="features">{feature_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")
    st.subheader("Inventory Table")
    st.dataframe(products, use_container_width=True, hide_index=True)


# =========================================================
# BUSINESS DASHBOARD
# =========================================================

elif page == "📊 Business Dashboard":
    leads = get_leads()
    orders = get_orders()
    paid_orders = [order for order in orders if order[5] == "Paid"]
    pending_orders = [order for order in orders if order[5] != "Paid"]
    total_revenue = sum(order[4] for order in paid_orders)
    conversion = (len(paid_orders) / len(orders) * 100) if orders else 0

    st.markdown(
        """
        <div class="ledger-header">
            <div class="ledger-kicker">ShopPilot / business ledger</div>
            <div class="ledger-title">Performance, without the noise.</div>
            <div class="ledger-subtitle">A concise operating record of sales, demand, and customer follow-up.</div>
        </div>
        <div class="ledger-rule"></div>
        """,
        unsafe_allow_html=True,
    )

    summary_cols = st.columns([1.1, 0.9])
    with summary_cols[0]:
        st.markdown(
            f"""
            <div class="ledger-revenue">
                <div class="ledger-revenue-label">Net collected revenue</div>
                <div class="ledger-revenue-value">₹{total_revenue:,.0f}</div>
                <div class="ledger-revenue-note">{len(paid_orders)} completed order(s) · {conversion:.0f}% conversion</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with summary_cols[1]:
        st.markdown(
            f"""
            <div class="ledger-status">
                <div class="ledger-status-title">Operating status</div>
                <div class="ledger-status-line">Orders <strong>{len(orders)}</strong></div>
                <div class="ledger-status-line">Open payments <strong>{len(pending_orders)}</strong></div>
                <div class="ledger-status-line">Active leads <strong>{len(leads)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.space("small")
    insight_cols = st.columns(2)
    with insight_cols[0]:
        with st.container(border=True):
            st.subheader("Payment ledger")
            st.caption("Paid and pending order count")
            status_df = pd.DataFrame(
                {"Status": ["Paid", "Pending"], "Orders": [len(paid_orders), len(pending_orders)]}
            )
            st.bar_chart(status_df, x="Status", y="Orders", color="#f59e0b")
            if pending_orders:
                st.warning(f"{len(pending_orders)} payment(s) need attention.", icon=":material/schedule:")
            else:
                st.success("All payments are complete.", icon=":material/check_circle:")

    with insight_cols[1]:
        with st.container(border=True):
            st.subheader("Demand ledger")
            st.caption("Products ranked by order count")
            if orders:
                product_demand = (
                    pd.DataFrame(
                        orders,
                        columns=["ID", "Customer Name", "Contact", "Product", "Price", "Status", "Razorpay Order ID", "Payment ID", "Created At", "Product ID"],
                    )
                    .groupby("Product")
                    .size()
                    .reset_index(name="Orders")
                    .sort_values("Orders", ascending=False)
                )
                st.bar_chart(product_demand, x="Product", y="Orders", color="#fbbf24")
            else:
                st.info("Product demand will appear after the first order.", icon=":material/bar_chart:")

    with st.container(border=True):
        st.subheader("Lead register")
        st.caption("Latest customer requests captured by the AI sales agent")
        if leads:
            lead_df = pd.DataFrame(
                leads,
                columns=["ID", "Name", "Contact", "Requirement", "Recommended Product", "Created At"],
            )
            lead_df["Created At"] = (
                pd.to_datetime(lead_df["Created At"], utc=True)
                .dt.tz_convert("Asia/Kolkata")
                .dt.strftime("%d-%m-%Y %H:%M:%S")
            )
            st.dataframe(lead_df, width="stretch", hide_index=True)
        else:
            st.info("No leads have been created yet.", icon=":material/inbox:")

    with st.container(border=True):
        st.subheader("Order register")
        st.caption("Payment and fulfilment record")
        if orders:
            order_df = pd.DataFrame(
                orders,
                columns=[
                    "ID", "Customer Name", "Contact", "Product", "Price",
                    "Status", "Razorpay Order ID", "Payment ID", "Created At", "Product ID",
                ],
            )
            order_df["Created At"] = (
                pd.to_datetime(order_df["Created At"], utc=True)
                .dt.tz_convert("Asia/Kolkata")
                .dt.strftime("%d-%m-%Y %H:%M:%S")
            )
            st.dataframe(order_df, width="stretch", hide_index=True)
        else:
            st.info("No orders have been created yet.", icon=":material/inbox:")