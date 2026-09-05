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
    reduce_stock,
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

init_database()

# =========================================================
# HEADER
# =========================================================

st.title("🛍️ ShopPilot AI")
st.subheader("AI-Powered Sales & Commerce Agent")

st.write(
    "ShopPilot AI helps businesses understand customer requirements, "
    "recommend suitable products, and convert conversations into orders."
)

# =========================================================
# SIDEBAR
# =========================================================

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

                    st.subheader(
                        "💳 Complete Payment"
                    )

                    st.info(
                        f"""
This is Razorpay TEST mode.

Product price:
₹{pending_order['price']:,.0f}

Demo payment amount:
₹{DEMO_PAYMENT_AMOUNT:,.0f}

No real money will be charged.
"""
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
                            padding: 20px;
                            border-radius: 10px;
                            border: 1px solid #444;
                            background: #11141a;
                        }}

                        .payment-title {{
                            color: white;
                            font-size: 20px;
                            font-weight: bold;
                            margin-bottom: 10px;
                        }}

                        .payment-info {{
                            color: #aaa;
                            margin-bottom: 15px;
                        }}

                        button {{
                            background: #3399cc;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            padding: 14px 24px;
                            font-size: 17px;
                            cursor: pointer;
                        }}

                        button:hover {{
                            background: #287fa8;
                        }}

                        </style>
                    </head>

                    <body>

                    <div class="payment-box">

                        <div class="payment-title">
                            💳 Razorpay Test Payment
                        </div>

                        <div class="payment-info">
                            Demo amount:
                            <strong>
                                ₹{DEMO_PAYMENT_AMOUNT:,}
                            </strong>
                            <br><br>

                            Product:
                            <strong>
                                {html.escape(
                                    pending_order["product"]
                                )}
                            </strong>
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
                        height=180,
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

                    # -----------------------------------------
                    # REDUCE STOCK ONLY AFTER VERIFIED PAYMENT
                    # -----------------------------------------

                    stock_reduced = reduce_stock(
                        product_id,
                        1,
                    )

                    if not stock_reduced:
                        st.error(
                            "Payment succeeded, but the product "
                            "is no longer available."
                        )
                    else:

                        # -------------------------------------
                        # UPDATE EXISTING ORDER TO PAID
                        # -------------------------------------

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

                            # Clear query parameters
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
            if order[5] == "Paid"
        )

        st.metric(
            "Revenue",
            f"₹{total_revenue:,.0f}",
        )

    # -----------------------------------------------------
    # LEADS
    # -----------------------------------------------------

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
            "Created At",
            
        ],
     )
     
     lead_df["Created At"] = (
        pd.to_datetime(lead_df["Created At"], utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.strftime("%d-%m-%Y %H:%M:%S")
     )

     st.dataframe(
        lead_df,
        use_container_width=True,
        hide_index=True,
     )

    else:

     st.info("No leads have been created yet.")

    # -----------------------------------------------------
    # ORDERS
    # -----------------------------------------------------

    st.subheader(
        "🛒 Orders"
    )

    if orders:
        
        order_df = pd.DataFrame(
            orders,
            columns=[
                "ID",
                "Customer Name",
                "Contact",
                "Product",
                "Price",
                "Status",
                "Razorpay Order ID",
                "Payment ID",
                "Created At",
                "Product ID",
            ],
        )
        
        order_df["Created At"] = (
            
          pd.to_datetime(order_df["Created At"], utc=True)
         .dt.tz_convert("Asia/Kolkata")
         .dt.strftime("%d-%m-%Y %H:%M:%S"))

        st.dataframe(
            order_df,
            use_container_width=True,
            hide_index=True,
        )
        
    else:
        
        st.info(
            "No orders have been created yet."
        )