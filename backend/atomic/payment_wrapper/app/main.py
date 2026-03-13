import os
import stripe
from flask import Flask, request, jsonify
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Payment Wrapper Microservice API",
        "version": "1.0.0",
        "description": "Thin wrapper around the Stripe API. Creates and confirms a PaymentIntent server-side, returning the final payment status to the Make Payment orchestrator."
    }
})

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@app.route('/api/wrapper/stripe/charge', methods=['POST'])
def create_charge():
    """
    Create and confirm a Stripe PaymentIntent (server-side)
    ---
    description: >
      Called by the Make Payment orchestrator. Accepts the amount, currency, and a
      paymentMethodId (obtained from the frontend via Stripe.js before this call).
      Creates and immediately confirms the PaymentIntent server-side.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - amount
            - currency
            - paymentMethodId
          properties:
            amount:
              type: integer
              description: Amount in the smallest currency unit (e.g. cents — 5000 = SGD 50.00)
              example: 5000
            currency:
              type: string
              description: Three-letter ISO currency code
              example: "sgd"
            paymentMethodId:
              type: string
              description: Stripe PaymentMethod ID collected by the frontend via Stripe.js
              example: "pm_card_visa"
    responses:
      200:
        description: Payment succeeded
        schema:
          type: object
          properties:
            success:
              type: boolean
            transactionId:
              type: string
            status:
              type: string
              description: Stripe PaymentIntent status (e.g. "succeeded")
      400:
        description: Bad request (missing or invalid fields)
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
      402:
        description: Payment declined by Stripe
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
            status:
              type: string
      500:
        description: Internal Stripe or server error
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
    """
    data = request.get_json()

    amount = data.get('amount') if data else None
    currency = data.get('currency') if data else None
    payment_method_id = data.get('paymentMethodId') if data else None

    if not amount or not currency or not payment_method_id:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'amount', 'currency', and 'paymentMethodId'"
        }), 400

    if not isinstance(amount, int) or amount <= 0:
        return jsonify({
            "success": False,
            "error": "'amount' must be a positive integer (smallest currency unit, e.g. cents)"
        }), 400

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method=payment_method_id,
            confirm=True,
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never"
            }
        )

        if intent.status == "succeeded":
            return jsonify({
                "success": True,
                "transactionId": intent.id,
                "status": intent.status
            }), 200
        else:
            return jsonify({
                "success": False,
                "transactionId": intent.id,
                "status": intent.status,
                "error": f"Payment not completed. Stripe status: {intent.status}"
            }), 402

    except stripe.error.CardError as e:
        return jsonify({
            "success": False,
            "error": e.user_message,
            "status": "declined"
        }), 402

    except stripe.error.StripeError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    except Exception:
        return jsonify({
            "success": False,
            "error": "Payment processing failed at the gateway."
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('STRIPE_WRAPPER_PORT', 5005))
    app.run(host='0.0.0.0', port=port, debug=True)
