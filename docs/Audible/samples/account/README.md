# Orders API

**Endpoint:** `GET /1.0/orders`

Purchase history including credit usage, refunds, and payment details.

## Schema (Key | Value)

| Key | Value |
| ----- | ------- |
| `amount_charged.amount` | `23.97` |
| `amount_charged.currency` | `USD` |
| `billing_address` | `None` |
| `billing_period` | `None` |
| `customer_id` | `REDACTED` |
| `date` | `2026-01-02T12:57:43Z` |
| `detail_state` | `ORDER_SUCCEEDED` |
| `id` | `REDACTED` |
| `is_amazon` | `False` |
| `is_bogo_order` | `False` |
| `items` | [array of 3 objects] |
| `items[0].acquisition_type` | `None` |
| `items[0].action_code` | `ANONAUDW0378WS010202` |
| `items[0].amount_charged.amount` | `7.99` |
| `items[0].amount_charged.currency` | `USD` |
| `items[0].asin` | `B0BLZNZ47B` |
| `items[0].combined_order_id` | `None` |
| `items[0].coupon_amount.amount` | `0.0` |
| `items[0].coupon_amount.currency` | `USD` |
| `items[0].credit_promo_id` | `None` |
| `items[0].credits_applied` | `None` |
| `items[0].date_returned` | `None` |
| `items[0].emp_provider_id` | `None` |
| `items[0].id` | `REDACTED` |
| `items[0].institution_benefit_plan_id` | `None` |
| `items[0].institution_id` | `None` |
| `items[0].is_combined_order_id` | `False` |
| `items[0].is_externally_managed_payment` | `False` |
| `items[0].is_gift` | `False` |
| `items[0].is_preorder` | `False` |
| `items[0].is_returned` | `False` |
| `items[0].is_vet_charge_refunded` | `False` |
| `items[0].merchant_id` | `REDACTED` |
| `items[0].next_billing_date` | `None` |
| `items[0].payment_method` | `PURCHASE` |
| `items[0].plan_id` | `REDACTED` |
| `items[0].plan_status` | `None` |
| `items[0].promo_ids` | `None` |
| `items[0].promotion_amount.amount` | `0.0` |
| `items[0].promotion_amount.currency` | `USD` |
| `items[0].return_information` | `None` |
| `items[0].return_reason` | `None` |
| `items[0].source` | `None` |
| `items[0].tax_amount.amount` | `0.44` |
| `items[0].tax_amount.currency` | `USD` |
| `items[0].tax_transaction_id` | `None` |
| `items[0].taxes` | `None` |
| `marketplace_id` | `REDACTED` |
| `mfa_details` | `None` |
| `mfa_enabled` | `False` |
| `order_type_specification` | `Content` |
| `payment.active` | `True` |
| `payment.id` | `None` |
| `payment.issuer` | `Visa` |
| `payment.payment_method_id` | `REDACTED` |
| `payment.tail` | `1962` |
| `payment.type` | `CREDIT_CARD` |
| `payment_contract_id` | `REDACTED` |
| `payment_contract_revision_id` | `REDACTED` |
| `payment_plan_id` | `REDACTED` |
| `payment_profile` | `AudibleCheckout` |
| `refunds` | `None` |
| `state` | `ORDER_CLOSED` |
| `subCharges` | [array of 1 objects] |
| `subCharges[0].amount_charged.amount` | `25.29` |
| `subCharges[0].amount_charged.currency` | `USD` |
| `subCharges[0].payment.active` | `True` |
| `subCharges[0].payment.id` | `None` |
| `subCharges[0].payment.issuer` | `REDACTED` |
| `subCharges[0].payment.payment_method_id` | `REDACTED` |
| `subCharges[0].payment.tail` | `REDACTED` |
| `subCharges[0].payment.type` | `REDACTED` |
| `subscription_id` | `None` |
| `tax_amount.amount` | `1.32` |
| `tax_amount.currency` | `USD` |
| `type` | `CONTENT` |
| `vat_rate` | `5.5` |

---
*Generated from raw sample: `account/orders_full.json`*
