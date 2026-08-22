import streamlit as st
import pandas as pd

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
)

# -----------------------------
# Page Configuration
# -----------------------------

st.set_page_config(
    page_title="ShopPilot AI",
    page_icon="🛍️",
    layout="wide",
)

init_database()

# -----------------------------
# Header
# -----------------------------

st.title("🛍️ ShopPilot AI")
st.subheader("AI-Powered Sales & Commerce Agent")

st.write(
    "ShopPilot AI helps businesses understand customer requirements, "
    "recommend suitable products, and convert conversations into qualified leads."
)

# -----------------------------
# Sidebar
# -----------------------------

st.sidebar.title("Navigation")

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

    st.header("🤖 AI Sales Agent")

    st.write(
        "Ask about products, prices, features, or recommendations."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.write(message["content"])

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

            with st.spinner("AI is analyzing your requirement..."):

                try:
                    response = ask_agent(
                      user_message,
                      st.session_state.messages
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
                    
# -----------------------------
# Purchase Action
# -----------------------------

    purchase_keywords = [
        "buy",
        "purchase",
        "order",
        "checkout",
        "take it",
        "i'll take",
        "i will take",
    ]

    latest_user_message = ""

    if st.session_state.messages:

        for message in reversed(st.session_state.messages):

            if message["role"] == "user":
                latest_user_message = message["content"].lower()
                break

    wants_to_buy = any(
        keyword in latest_user_message
        for keyword in purchase_keywords
    )

    if wants_to_buy:

        selected_product = detect_product(
            st.session_state.messages
        )

        if selected_product:

            st.divider()

            st.subheader("🛒 Ready to Purchase?")

            st.write(
                f"**{selected_product['name']}**"
            )

            st.write(
                f"Price: **₹{selected_product['price']:,.0f}**"
            )

            st.write(
                f"Available stock: **{selected_product['stock']}**"
            )

            if selected_product["stock"] > 0:

                with st.form("purchase_form"):

                    buyer_name = st.text_input(
                        "Customer Name"
                    )

                    buyer_contact = st.text_input(
                        "Phone / Email"
                    )

                    confirm_purchase = st.form_submit_button(
                        "✅ Confirm Purchase"
                    )

                    if confirm_purchase:

                        if buyer_name and buyer_contact:

                            create_order(
                                buyer_name,
                                buyer_contact,
                                selected_product["name"],
                                selected_product["price"],
                            )

                            st.success(
                                f"🎉 Order created successfully for "
                                f"{selected_product['name']}!"
                            )

                            st.balloons()

                        else:

                            st.warning(
                                "Please enter your name and contact details."
                            )

            else:

                st.error(
                    "Sorry, this product is currently out of stock."
                )                                        

    
    # -----------------------------
    # Lead Capture
    # -----------------------------

    st.divider()

    st.subheader("📋 Interested in a product?")

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
                    "Please fill in your name, contact and requirement."
                )


# =========================================================
# PRODUCT CATALOGUE
# =========================================================

elif page == "📦 Product Catalogue":

    st.header("📦 Product Catalogue")

    products = load_products()

    st.dataframe(
        products,
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# BUSINESS DASHBOARD
# =========================================================

elif page == "📊 Business Dashboard":

    st.header("📊 Business Dashboard")

    leads = get_leads()
    orders = get_orders()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Leads",
            len(leads),
        )

    with col2:
        st.metric(
            "Total Orders",
            len(orders),
        )

    with col3:

        total_revenue = sum(
            order[4]
            for order in orders
        )

        st.metric(
            "Revenue",
            f"₹{total_revenue:,.0f}",
        )

    # -----------------------------
    # Leads
    # -----------------------------

    st.subheader("📋 Recent Leads")

    if leads:

        lead_df = pd.DataFrame(
            leads,
            columns=[
                "ID",
                "Name",
                "Contact",
                "Requirement",
                "Recommended Product",
                "Status",
                "Created At",
            ],
        )

        st.dataframe(
            lead_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No leads have been created yet."
        )

    # -----------------------------
    # Orders
    # -----------------------------

    st.subheader("🛒 Orders")

    if orders:

        order_df = pd.DataFrame(
            orders,
            columns=[
                "ID",
                "Customer",
                "Contact",
                "Product",
                "Price",
                "Status",
                "Created At",
            ],
        )

        st.dataframe(
            order_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No orders have been created yet."
        )