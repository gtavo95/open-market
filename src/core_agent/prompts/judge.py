"""What the judge reads: the compaction request and the questions TypeSafe answers about the conversation.

`COMPACT` is what the model reads to write the state and `CART_PROMPT` for the cart; `SALE_QUESTIONS`,
`REPLY_QUESTIONS` and `HANDOFF_REASON_QUESTIONS` are what TypeSafe reads to judge the conversation, and `HANDOFF_REASONS` the
label's options. How they are requested, memoized and chained with the
turn's facts lives in `world/question_judge.py`. Changing any of these texts is
changing what the judge sees, and that is measured.
"""

from __future__ import annotations

from typing import Any

SALE_QUESTIONS: dict[str, dict[str, Any]] = {
    "has_search_terms": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): has the customer already "
            "said what they are looking for, whether a pest, disease, symptom or concrete problem, or a product "
            "or type of product they have in mind?"
        ),
        "criteria": {
            "true": (
                "They named a pest, disease, symptom, problem or concrete need, or a product or "
                "type of product, even if the catalog does not have it. Examples: 'leafcutter ants in the coffee', "
                "'something for hard water', 'how much Escudo per manzana', 'an insecticide for corn', "
                "'yellow leaves on the tomato', 'I want 2 liters of Silverstrike 45 SC'."
            ),
            "false": (
                "They only said the crop, or that they have a problem without saying which, or they said hello. Examples: "
                "'I have a problem with my tomatoes', 'hi, I need help', 'what do you sell?'."
            ),
        },
    },
    "said_quantity": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): has the customer already "
            "said how much product they want, in liters, kilos or containers?"
        ),
        "criteria": {
            "true": (
                "They gave a concrete quantity of product: liters, gallons, kilos, containers, jugs, "
                "boxes, rolls, sheets or sacks. A bare number that answers the advisor's question "
                "about how many liters, containers or units they want is that quantity. Examples: 'I want 4 "
                "liters', 'two gallons', 'one jug of each', 'a box of traps', 'I'd like 3 "
                "rolls', 'one (to: How many liters would you like?)', '3 (to: How many do you want?)'."
            ),
            "false": (
                "They did not say how much product they want, or they only said the area they will treat ('it's three "
                "manzanas', 'half a hectare'), or something vague with no number ('a good amount', 'whatever it takes'), "
                "or the number answers a different question ('2 (to: How many applications do you do?)')."
            ),
        },
    },
    "wants_to_buy": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): has the customer already "
            "decided on the purchase? That means they said they want to buy, asked for a quantity of a product, "
            "asked how to pay or for the order to be placed, or say they already paid, deposited or transferred."
        ),
        "criteria": {
            "true": (
                "They expressed the decision to buy or asked to go ahead with the order or the payment, or said yes "
                "when the advisor offered to prepare, reserve or send the order: reserving the "
                "order is buying it. Asking for a quantity of a product ('I'd like 3 gallons', 'give me "
                "two boxes', 'I'd like 3 rolls') is buying it, and choosing the presentation, the size or the variant the "
                "advisor asked about after that order confirms it. Examples: 'I want it', 'send it "
                "to me', 'how do I pay?', 'place the order for me', 'I want two liters', 'I'd like 3 boxes of "
                "traps', 'the 1 L one is fine (to: Which presentation do you want them in?)', "
                "'yes (to: Do you want me to prepare the order for 4 liters?)', "
                "'yes let's reserve them (to: Do you want us to reserve the 4 containers for you?)', 'go ahead (to: Should I reserve it for you?)'. "
                "Saying they already paid, deposited or transferred, or asking for the account or the link to pay, is "
                "having bought. A separate question in the same message (shipping, the invoice, a "
                "lead time) does not undo the purchase. Examples: 'I already made the deposit', 'done, I already transferred "
                "the money for the rolls', 'yes, send it. Can you give me the account?', 'give me 4 of Silverstrike, do you charge for shipping?'."
            ),
            "false": (
                "They are still asking, comparing or asking the price without deciding, or they said no, or their 'yes' was to "
                "something that is not the order. Examples: 'how much is it?', 'does it work for tomato?', "
                "'how much is the 20 liter one?', "
                "'no (to: Do you want me to prepare the order?)', 'yes (to: Is the dose clear?)'."
            ),
        },
    },
    "said_billing_data": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): has the customer already "
            "given the details for invoicing?"
        ),
        "criteria": {
            "true": (
                "They gave the NIT (or said final consumer / CF), the name and phone of the person receiving, "
                "and the delivery address; the legal name is not needed. Example: 'NIT 1234567-8, "
                "Rodrigo Pérez receives it, 5555-0101, condominio Las Flores casa 12, zona 5, Quetzaltenango'."
            ),
            "false": (
                "One is missing: the NIT, who receives, their phone or the address. Example: 'Juan Pérez, "
                "NIT 1234567-8, Cobán' (did not say who receives or their phone)."
            ),
        },
    },
    "asked_for_the_datasheet": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): did the customer ask "
            "to be sent the technical datasheet, the sheet, the label or the PDF of a product?"
        ),
        "criteria": {
            "true": (
                "They asked for the product's document, under any name: the datasheet, the technical sheet, the "
                "little sheet, the safety sheet, the label, the leaflet, the PDF, the information in "
                "writing. Examples: 'send me the datasheet', 'pass me the product's little sheet', 'do you have the "
                "PDF?', 'can you send me the label', 'send me the info on Raíz Viva'."
            ),
            "false": (
                "They asked about the product without asking for the document: the dose, the price, what it is "
                "for, whether it works for them, how it is applied. Or they asked for the catalog of all the products and "
                "not the document of one. Examples: 'how much Raíz Viva per manzana?', 'how much is it?', 'does it work "
                "for tomato?', 'explain how it is applied', 'send me the catalog'."
            ),
        },
    },
    "asked_for_the_catalog": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): did the customer ask for "
            "the catalog, the list of all the products you sell?"
        ),
        "criteria": {
            "true": (
                "They asked for the catalog or the complete list of products, under any name. The word "
                "alone is already the request, even if earlier they asked about the products in general: "
                "'Catalog' after 'I want more information on your products' is true. Examples: "
                "'I want the catalog please', 'send me your catalog', 'what products do you have?', "
                "'pass me the product list', 'can you share everything you sell?', 'can you share "
                "the brochure?'."
            ),
            "false": (
                "They asked about a product, a pest or a crop, or asked for the datasheet of a product, "
                "without asking for the complete catalog. Examples: 'what do you have for thrips?', 'send me the "
                "datasheet for Silverstrike', 'how much is Raíz Viva?'."
            ),
        },
    },
    "gives_billing_data": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote): in `last_message`, does the customer give, "
            "correct or ask to remove any detail for invoicing or delivering the order: the NIT, the legal name, "
            "who receives, their phone or the delivery address?"
        ),
        "criteria": {
            "true": (
                "`last_message` carries at least one of those details, new or corrected, even if others are missing, "
                "even if the advisor asked for a different one, and even if it comes with a question. A bare phone "
                "number is the phone, and 'CF' or 'final consumer' is the NIT. Confirming that the details "
                "from an earlier purchase the advisor read back are unchanged ('yes, the same ones', 'same as last time') is giving them. "
                "Examples: 'NIT 1234567-8', 'CF', "
                "'Rodrigo receives it, 5555-0101', "
                "'5555-0101. and how long does it take to arrive?', 'to 4a calle 3-20 zona 1, Xela', 'change the "
                "address to Cobán', 'the NIT was a different one: 7654321-0', 'Juan Pérez (to: Whose name should the "
                "invoice be in?)', 'I'll receive it', 'yes, the same ones' (a few messages earlier the advisor asked whether to use "
                "the same invoice and delivery details)."
            ),
            "false": (
                "`last_message` carries none: it asks about a product, the price, shipping or payment, "
                "chooses how to pay, or says hello or thanks. Details given in earlier messages do not count. "
                "Examples: 'how much is shipping?', 'I'll pay with the link', 'thanks', 'what details do you need?'."
            ),
        },
    },
    "asks_for_order_summary": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote): in `last_message`, does the customer ask "
            "to be told what is in their order or cart, or which details they already gave and which are missing?"
        ),
        "criteria": {
            "true": (
                "They ask for the summary of what they are going to buy or of what they already gave. Examples: 'what do I have so far?', 'what "
                "do I have in my cart?', 'how is my order looking?', 'remind me what I ordered', 'what details are you missing?', "
                "'can you repeat the order?'."
            ),
            "false": (
                "They ask something else or add to the order. Asking the total or the price of a product is not "
                "asking for the summary. Examples: 'how much is the total?', 'add 2 more', 'when does it arrive?', "
                "'have I paid already?', 'I want 2 liters of Silverstrike'."
            ),
        },
    },
    "asks_to_start_over": {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote): in `last_message`, does the customer ask "
            "to empty the whole order or start from scratch?"
        ),
        "criteria": {
            "true": (
                "They ask to delete the whole order or begin again. Examples: 'delete it', 'delete everything', 'empty the "
                "cart', 'let's start from scratch', 'cancel that order, I want to place another one', 'better forget all of it and "
                "we'll start over', 'yes (to: Do you want me to empty the order?)'."
            ),
            "false": (
                "They remove or change a product and go on with the rest, correct a detail, or do not talk about the order. "
                "Examples: 'remove the Silverstrike', 'make it 2 instead of 4', 'change the address to Cobán', 'no "
                "thanks', 'no (to: Anything else?)', 'I don't want the 20 L one anymore, give me the 1 L one'."
            ),
        },
    },
}
"""One question per gate of the network, about `conversation`. They are data: edited here, with their examples.

Adding a gate is adding an entry here and a `done_when` with that
name in the plan, or an `Intent.asked` in the intents table. There is no separate list of
names: the ones asked come from the plan and the intents, and the ones
that can be answered are the keys of this.

The last two do not close steps: `propose_effects` asks them to propose an
effect, the datasheet and the account, which the host sends. They are about "what they said so
far" like the rest, so once the effect is proposed the judgment stays at
yes; it is the `effects` channel, seeded by the host, that prevents proposing it
twice.

Tested live on Sep 21, 2026, 19 cases compacted with the
`provider()` model and judged, USD 0.0008: the datasheet between 0.95 ("and the technical
datasheet?") and 0.99 ("pass me the product's little sheet"), with "do you have the PDF for that one?"
at 0.97 and "can you send me the label" at 0.98; against "how much Escudo per manzana"
0.02, "how much is it?" 0.02, "explain how it is applied" 0.02 and the first turn
0.06. The account between 0.87 ("pass me the account", the closest to `THRESHOLD`) and
0.98 ("what number do I deposit to?", "where do I make the transfer" 0.97); against
"how do I pay?" 0.05, "do you take cards?" 0.03, "paying by transfer" 0.05 and
"place the order for me" 0.03. Neither edge crosses to the other side.

The last three belong to the billing form and the cart (`roles/form.py`), since Oct 8,
2026, and look only at `last_message`: a "delete it" from three turns ago does not empty the order
again. `gives_billing_data` decides whether the form's model runs (`FORM_PROMPT`),
`asks_for_order_summary` gives the writer the order and the details with what is missing, and
`asks_to_start_over` empties the order and the form and tells the host (`restart`).
`said_billing_data` is still answered because plans saved earlier close `data` with it.
Tested before wiring them in, the judge alone on 24 messages with their conversation, n=2, USD 0.0025:
80/80 on the correct side of the threshold, with two fixes measured along the way: a bare phone with a
question ("5555-0101. and how long does it take?") gave 0.67–0.70 and "CF" 0.78–0.85 until the criterion said
that a bare phone is the phone and CF is the NIT (0.96 and 0.95); "yes, the same ones" to the details of
the earlier purchase gave 0.42–0.47 until it said that confirming them is giving them (0.85–0.86; "yes, I
want it" stays at 0.05). On Oct 8, 2026, in closed-sale-another-purchase:4 at n=3, the advisor had
asked "shall we use the same details?" two messages earlier and the last one did not repeat it: "yes, the
same ones" gave 0.76–0.78 and the form stayed empty (1/3). A rule saying so ("even if they were asked
a few messages earlier") brought it down to 0.69–0.71; the example with that case raised it to
0.90–0.91, with the 24 messages at 80/80 and "yes" or "yes, add it" to another advisor question, with the
one about the details two messages earlier, at 0.05–0.08. Details 0.98–0.99 ("NIT … receives …", "change the address to …",
"the NIT was a different one", "I'll receive it, Ana") against 0.03–0.05 ("how long does it take?", "I'll pay with the link", "what
details do you need?"). Summary 0.96–0.98 ("what do I have so far?",
"what do I have in my cart?") against 0.02–0.03 ("how much is the total?", "add 2 more"). Start from
scratch 0.89–0.98 ("delete it", "let's start from scratch", "cancel everything") against 0.02–0.04 ("remove the Escudo",
"make it 2", "no thanks", and "I want 1 liter of Escudo" after a "delete it").

`said_payment_method` has not been here since Sep 24, 2026: the
`payment_method` label answers it (see `LABEL_GATES`). Nor has `asked_for_the_account` since Sep
25, 2026: the `payment_request` label answers it.
"""

PAYMENT_METHOD = "payment_method"

PAYMENT_METHODS: dict[str, str] = {
    "link": (
        "Pays with the payment link, or by card: they chose it or asked for the link (asking for the link already is "
        "choosing it, even if transfer was discussed earlier)."
    ),
    "transfer": (
        "Pays by transfer or deposit: they chose it, asked for the number or the name of the account "
        "(asking for the account already is choosing transfer, even without saying the word), or say they are sending "
        "the deposit slip or the receipt."
    ),
    "credit": "Asks for credit, to pay in installments or to pay later against an invoice.",
    "check": "Wants to pay by check.",
    "on_delivery": "Wants to pay in cash or by card on receiving the order.",
    "other": "Named a way of paying that is none of the above.",
    "none": "Has not yet said how they will pay, nor asked for the account or the link.",
}
"""The ways of paying the customer can name: the business's two and the ones that are not.

It is a closed list on purpose. The sale and the host act on keys they
know (the link, the account, handing credit to a person), and a key
invented by the model during the turn is one nobody knows how to use. `other` is the bucket
for what is new: a category is created by reading what fell in there in real sales
(the judge's pass over the Mongo conversations) and adding it here, with
its text, as was done with `credit`, `check` and `on_delivery` on Sep 24,
2026.
"""

PAYMENT_ASK = "payment_request"

PAYMENT_ASKS: dict[str, str] = {
    "account": (
        "Asked for the account or where the payment goes: the number or the name of the account, which bank to "
        "deposit at or where to transfer, even if they ask politely or begin with 'if' ('if you "
        "could give me the account number', 'can you share your account number?', "
        "'do you have an account to deposit to')."
    ),
    "link": "Asked to be sent the payment link.",
    "methods": "Asked how to pay or what payment methods there are, without asking for the account or the link.",
    "nothing": (
        "Did not ask for anything about payment: did not talk about payment, or chose a method, said they will pay or that "
        "they are sending the receipt, without asking for the account or the link."
    ),
}
"""What the customer asked the advisor for about payment: the account, the link, how to pay, or nothing.

It is not how they pay (`PAYMENT_METHODS`): "paying by transfer" chooses and does not ask,
"can you give me the account?" asks. `asked_for_the_account` comes from here, which sends the account
card (`roles/effects.py`).
"""

SALE_LABELS: dict[str, dict[str, Any]] = {
    PAYMENT_METHOD: {
        "type": "choice",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote): how did the customer say they are going to "
            "pay? What counts is what the customer chose or asked for, or what the advisor offered and the customer "
            "accepted. The advisor saying how to pay is not a choice by the customer, even if the customer "
            "goes on with the purchase. If they chose more than one, the last one."
        ),
        "criteria": PAYMENT_METHODS,
    },
    PAYMENT_ASK: {
        "type": "choice",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts): what did they ask "
            "the advisor for about payment? If they asked for more than one thing, the last one."
        ),
        "criteria": PAYMENT_ASKS,
    },
}
"""What is asked about the conversation and comes back as a label, not as a probability.

It goes in the same request as `SALE_QUESTIONS`, so it does not cost a separate one, and
travels to the host in `sale.judgment.labels`: it says which, so the host knows whether to
send the link or the account, or whether a person has to see the credit.

`payment_method` has separated what the advisor says from what the customer chooses
since Oct 3, 2026. It said "what the advisor said and the customer accepted counts", and in prod
the advisor said "the products are paid by transfer", the customer went on with
"i wan tto buy" and then "wnat link": the judge read transfer (link 0.14) and the
link did not go out. With the new line and "asking for the link already is choosing it" in `link`, the judge
alone on that conversation and eight controls (chooses, asks for the account, accepts what
the advisor offers, sends the slip, switches to link, is offered both), n=3: 24/30 →
30/30, `pays_with_link` 0.14–0.19 → 0.89–0.92, above `THRESHOLD`. Without "or the
link" in `none`, link stayed at 0.72–0.77, below.
"""

LABEL_GATES: dict[str, tuple[str, tuple[str, ...]]] = {
    "said_payment_method": (PAYMENT_METHOD, ("link", "transfer")),
    "asked_for_the_account": (PAYMENT_ASK, ("account",)),
    "pays_with_link": (PAYMENT_METHOD, ("link",)),
    "pays_with_credit_or_check": (PAYMENT_METHOD, ("credit", "check")),
}
"""Gates that are not asked: their `p` is the sum of a label's distribution over those options.

The `method` step closes when the customer chose one of the business's two ways,
and that is the same thing the label says another way. Asking it twice
gave two answers: on Sep 24, 2026, on 19 phrases from a
customer's real sales, the `noul` there was closed 9 ("can you share your
account number?" 0.16, "A. Payment. Link" 0.74) and the label got 19 right; with the
gate taken from the label, 56 of 57 over three rounds, with no false positives
(credit, check and paying on receipt do not close it). It happened in sales: of 60
closed, `said_payment_method` did not close in 18, and in about 14 the customer had already
said it by asking for the account or sending the slip.

`asked_for_the_account` comes from `payment_request` since Sep 25, 2026, for
the same reason: the `noul` closed 2 or 3 of 6 with "can you share your account
number?" and with "yes, prepare it. If you could give me the account number"
across the whole batch, depending on how the state came out.

`pays_with_link` has proposed the payment link since the same day: asking for the link or
choosing it is the same label (`PAYMENT_METHODS["link"]`), and the link goes out the same
in both cases.
"""

ASKED_DATASHEET = "asked_for_the_datasheet"
ASKED_ACCOUNT = "asked_for_the_account"
ASKED_CATALOG = "asked_for_the_catalog"
ASKED_LINK = "pays_with_link"

GIVES_DATA = "gives_billing_data"
ASKS_SUMMARY = "asks_for_order_summary"
ASKS_RESET = "asks_to_start_over"

RECOMMENDED = "recommended_a_product"
PASSES_TO_A_PERSON = "hands_off_to_a_person"
LEFT_WITHOUT = "did_not_give_what_was_asked"
ASKS_THE_UNSOLVABLE = "asks_for_the_unsolvable"
HANDOFF_QUESTIONS = (PASSES_TO_A_PERSON, LEFT_WITHOUT, ASKS_THE_UNSOLVABLE)
"""The guardian's questions, one per family: it escalates if any passes `ESCALATE_THRESHOLD` (see `REPLY_QUESTIONS`)."""
HANDOFF_REASON = "escalation_reason"

_REPLY_CONTEXT = (
    "`customer` is what the customer has said so far, in order, `last_message` the last thing they said and "
    "`advisor` the answer of an agricultural catalog's advisor to that message. The advisor already answered "
    "the earlier messages on other turns: they are context, not something pending. "
)

REPLY_QUESTIONS: dict[str, dict[str, Any]] = {
    RECOMMENDED: {
        "type": "noul",
        "instructions": (
            "`customer` is what the customer has said so far, in order, and `advisor` is the latest "
            "answer of an agricultural catalog's advisor. Does the customer already have a concrete "
            "product: the advisor recommended it, or the customer asked for it by name or type and "
            "the advisor answers with that product?"
        ),
        "criteria": {
            "true": (
                "It names a product and recommends it for the customer's crop, pest or problem, "
                "with or without a dose. Or the customer asked for a product by name or type and "
                "the advisor answers with that concrete product: the price, the presentations or "
                "that they do have it. Examples: 'for whitefly on tomato I recommend "
                "Escudo 25 EW', 'Raíz Viva is certified for corn: 1 L/ha', 'the 1 L Raíz Viva "
                "costs Q280.00' to the customer who asked how much Raíz Viva is, 'yes, "
                "we have Grelthar Fe by the liter' to the one who asked whether they have iron for the soil."
            ),
            "false": (
                "It names no product, says it did not find one or that there is none certified for "
                "that crop, asks for more details before recommending, lists several without settling on "
                "one, or only explains. Examples: 'what pest do you see on the tomato?', 'I have nothing "
                "certified for cucumber', 'there are several options depending on the pest', 'for thrips "
                "we have Escudo, Raíz Viva and Escudo'."
            ),
        },
    },
    PASSES_TO_A_PERSON: {
        "type": "noul",
        "instructions": (
            f"{_REPLY_CONTEXT}Does the advisor say in this answer that another person (an engineer, an advisor, "
            "the office, the team) will look at, confirm or resolve the query, or offer to pass it on?"
        ),
        "criteria": {
            "true": (
                "It says it escalates, passes on, consults or confirms with another person, or that someone on "
                "the team handles that, even if it answers something alongside. Examples: 'I'll escalate your query "
                "to an agronomist', 'I'll pass you to an engineer', 'I'll confirm it with the office, "
                "do you want me to check?', 'an advisor on the team confirms the discounts'."
            ),
            "false": (
                "It answers itself and refers no one. Naming the team or the engineers without passing them the "
                "query does not count. Examples: 'the products are developed by the team of "
                "agronomists', 'I recommend Escudo 25 EW', 'what pest do you see?'."
            ),
        },
    },
    LEFT_WITHOUT: {
        "type": "noul",
        "instructions": (
            f"{_REPLY_CONTEXT}Did the advisor end up not giving the customer what they asked for in `last_message`, "
            "because it does not know, it is not in the datasheet, the catalog does not cover it or it cannot confirm it?"
        ),
        "criteria": {
            "true": (
                "It says it does not know, that the datasheet does not carry the fact, that the catalog has nothing for that "
                "pest or that use, that it cannot confirm it, or that it does not carry a product for what "
                "the customer needs (a rooter, something for rats) even if the customer named one "
                "that is no longer sold, even if it offers something else alongside. Examples: 'the Raíz Viva datasheet does not "
                "say anything about mixing it with copper', 'for leafcutter ants the catalog has no products', 'we do not "
                "carry a rooter', 'how the invoice is registered is not something I have'."
            ),
            "false": (
                "It gave what they asked for, or asked them for a missing detail. Saying it does not sell a product, a "
                "brand or an ingredient the customer asked for by name is answering: that it is not sold is "
                "the answer; saying it carries nothing for what the product did is not. Saying "
                "the crop is not among the certified ones and recommending it anyway is answering. Examples: 'we do not sell chlorpyrifos', 'tomato is not among the certified crops for "
                "Silverstrike, but it works: 1.42 L/ha', 'how many liters do you want?', 'payment is by transfer'."
            ),
        },
    },
    ASKS_THE_UNSOLVABLE: {
        "type": "noul",
        "instructions": (
            f"{_REPLY_CONTEXT}Does the customer ask in `last_message` for something the advisor cannot resolve "
            "however well and truthfully it answers?"
        ),
        "criteria": {
            "true": (
                "A complaint about something they bought, a return or a warranty, a discount, the registration "
                "or correction of an invoice, the delivery of an order they already placed, or paying with a method "
                "the business does not process (card, credit, check). Examples: 'the Raíz Viva I bought "
                "burned my tomato', 'do you give me a discount if I take 20 liters?', 'do you take cards?', "
                "'how do you register the invoice?'."
            ),
            "false": (
                "They ask about products, pests, doses, prices, how to pay with what is used, or give "
                "their invoice details without asking for anything else. Examples: 'I have whitefly', 'how do I "
                "pay?', 'do you sell chlorpyrifos?', 'NIT 1234567-8, in the name of Juan Pérez'."
            ),
        },
    },
}
"""The questions about what the advisor answered, not what the customer said: whether it recommended, and the guardian's.

Since Oct 3, 2026 the guardian is three noul, one per family, and it escalates if
any passes `ESCALATE_THRESHOLD`: the advisor hands them to a person (`PASSES_TO_A_PERSON`),
the advisor did not give what was asked (`LEFT_WITHOUT`), or the customer asks for something the advisor does not
resolve (`ASKS_THE_UNSOLVABLE`). Before it was a single one, `needs_a_person`, with the three
families in the criterion. On the 29 cases of `guardian.tsv` (the two chlorpyrifos ones already in
"does not escalate"), n=2, USD 0.0062 both together: both 58/58, but the old one left
the card at 0.65 and a "we do not sell chlorpyrifos" at 0.21, and the three together leave the card
at 0.88 and the highest of the non-escalating ones at 0.13. Each family is a row in
`governance/escalation.outbound.md` and is measured alone: the promise gives 0.94–0.99 in all the
escalations that state it, the card and the complaint are lifted by `ASKS_THE_UNSOLVABLE`, and the
leafcutter ants "to check with the office", which promises nothing, by `LEFT_WITHOUT` (0.95).

What follows is the history of `needs_a_person`, which is that of the criteria of the three.

`needs_a_person`, tested live on Sep 22, 2026, 16 cases, USD 0.0010:
the eleven that escalate between 0.82 and 0.96 and the five that do not, between 0.07 and 0.13.
The lowest of those that escalate is "do you take cards?" answered with "transfer
only" (0.82) and the highest of those that do not, "how many manzanas are you going to
treat?" (0.13). It classified two cases better than whoever wrote the test:
"for cucumber I have nothing certified, if it's for squash Fungvane yes" (0.92)
and "I don't have the 1 L presentation listed, the 5 L is Q450" (0.90);
a refusal with an alternative alongside is still a refusal.

The exception, since Sep 28, 2026: a product that is not sold. "We do not sell
chlorpyrifos" gave 0.35 to 0.56, below the threshold but with nothing saying so, and the case
expected an escalation. The client decided that saying it is not sold is enough. With the line in
`false`, the product refusals (chlorpyrifos, Roundup, glyphosate) give 0.09 to 0.26, and not
covered, no data, discontinued and the complaint stay between 0.94 and 0.97 (USD 0.0004).

On Oct 3, 2026 the writer stopped saying "X is discontinued; I'll escalate…" and switched to
"we do not carry a rooter". Without the phrase, the no fell under the `false` line and stayed at
0.45; the client wants that case in the queue. Naming "does not carry a product
for what they need" in `true` and clarifying in `false` that this is not a "we do not sell" raises it to 0.67–0.73
(`rooter-we-do-not-carry`, n=3), and the product refusals stay at 0.14–0.21. With the
guardian in three, that criterion lives in `LEFT_WITHOUT`: 0.71–0.76, and all of `guardian.tsv`
60/60 (30 cases, n=2, USD 0.0053). The `discontinued` case also escalates by code
(`CASE_HANDOFF`), so this question is the net for when the case did not see it.

What the test changed: with the criterion that only talked about the advisor not
knowing, the complaint about a product that burned the crop gave 0.52 and the card
0.34. The second family, what the customer brings and the advisor cannot resolve
however well and truthfully it answers, had to be spelled out in so many
words for it to get in.

It does not come in through `state`: compaction is of the customer's words and leaves the
advisor out on purpose. The turn's answer is judged with what the customer
said alongside, so that "for that crop" has something to compare against. Until Sep 20,
2026 `product` closed with `queried_the_catalog`, and once the
searcher queried on every turn that always closed: a gate that
always closes is not a gate.

Tested live before wiring it in, 8 answers, USD 0.0002: the four that
recommend between 0.94 and 0.99 ("I recommend Escudo 25 EW", "Raíz Viva is
certified for corn", and one that recommends conditionally, "if it's white
fly, the certified one is..."); the four that do not, between 0.02 and 0.05 (asks for the
pest, "I have no certified fungicide for cucumber", lists options without
choosing, explains how to pay).

`last_message` has been separate since Sep 25, 2026. `customer` carries everything
the customer said and `advisor` only the latest answer, so what they asked
two turns earlier looked unanswered: "how much is the red roll?" made
the purchase of two yellow rolls escalate (0.49–0.59, in prod a
`quote_not_found` case), and "iron deficiency" a well-answered "how do I pay?".
With the guardian looking at the last message they drop to 0.12–0.33, and in three probes
with history the excess open cases went from 7/9 to 0/9. `customer` stays
whole because `RECOMMENDED` needs it: with `before` separated, "I recommend
Escudo" for the whitefly of an earlier turn dropped from 0.88 to 0.65. The
promise ("I'll pass it to another person") escalates even if it comes from something earlier: without
saying so, an "I'll escalate" over a discontinued product gave 0.46.
"""


HANDOFF_REASONS: dict[str, str] = {
    "quality_complaint": (
        "Complains about something they already bought: it did not work, arrived in bad condition, damaged the crop."
    ),
    "warranty_return": (
        "Wants to return, exchange or have replaced what they bought, or asks about the warranty."
    ),
    "product_outside_promo": (
        "Asks for a promotional price that is not current, or that the catalog does not have for that product."
    ),
    "other_promotions": "Asks about discounts, offers or combos the catalog does not list.",
    "other_stores": (
        "Asks about another branch, another point of sale or a distributor that is not this catalog."
    ),
    "outside_hours": (
        "Asks for something that can only be resolved with someone attending, or asks until what time they attend."
    ),
    "out_of_coverage": (
        "Asks for shipping or a visit to a place that is not reached, or asks whether they reach their area."
    ),
    "billing_data": (
        "Asks to change, correct or confirm invoice details: the NIT, the name, the legal name."
    ),
    "card_payment": (
        "Wants to pay with credit, in installments or by check, which the advisor does not process."
    ),
    "unverified_discount": (
        "Asks for a discount, or says they were promised one, and the advisor cannot confirm it."
    ),
    "quote_not_found": (
        "Asks about a quote, an order or an earlier price the advisor does not have in view."
    ),
    "special_order": (
        "Asks for a quantity, a presentation or a mix the catalog does not list."
    ),
    "sale_completed": (
        "Has already decided what they are buying and how much, and a person is needed to take the order and dispatch it."
    ),
    "order_on_delivery": "Wants to pay on receipt, or to coordinate the delivery with someone.",
    "product_not_found": (
        "Asks for a product, a pest or a use the catalog does not cover: the advisor said it does not "
        "have it or that it does not appear."
    ),
    "unverifiable_specification": (
        "Asks a technical fact (dose, ingredient, compatibility, pre-harvest interval, registration) that is not "
        "in the datasheet and the advisor could not confirm."
    ),
    "other": (
        "A person is needed and none of the reasons above says why."
    ),
}
"""The queue each escalation falls into, in the business's vocabulary and not the advisor's.

It is the CRM's taxonomy, and that is why it is data: the keys are what the host
stores, and the descriptions are what the judge reads. Changing a description is
changing what the judge sees and is measured; adding a row is a row.

The reasons are not all of the same class, and that is fine. Some belong to the
advisor who did not know (`product_not_found`, `unverifiable_specification`,
`quote_not_found`); others to the
business, which says no by rule and not out of ignorance (`card_payment`,
`out_of_coverage`, `order_on_delivery`); others to the customer who brings
something that is not a sale (`quality_complaint`, `warranty_return`). The
three groups arrive by the same place, an answer that left the customer
without what they asked for (`HANDOFF_QUESTIONS`), and that is why the same questions open them and this
table separates them. `sale_completed` is the only one that is not a refusal, and it does not
come from here: the code proposes it when the sale plan closes
(`roles/human_handoff.py`, `sold`).

The CRM's ORIGIN is not here, on purpose: the one that comes out of this turn is
always "requested by the agent" (`roles/human_handoff.py`). The other two,
payment rejection and document failure, are what the host returns when
it `reject`s an effect that had been proposed, and they live in that `reject`'s note.

The keys are those of the host's handoff policy
(until 2026-09-25 they lived in a connector, legacy today). Until Sep 22, 2026 they were
read from the CRM interface and nine did not match (`reclamo_de_calidad`,
`otro_sin_clasificar`...): the host drops the key it does not know to "other", and
the human advisor loses the reason. `order_on_delivery` is still not on
that list (the webapp has it and the host does not) and falls to "other" until the host
adds it. `technical_error` and `link_prerequisite_pending` belong to the host and do not
go here: the first is the turn that failed, the second the payment gate.
"""

def _asks(what: str, true: str, false: str) -> dict[str, Any]:
    return {
        "type": "noul",
        "instructions": (
            "Looking at `conversation`, what the customer and the advisor have said to each other so far, in order "
            "(`last_message` is the last thing the customer wrote; what the advisor said and the customer "
            "accepted counts), to the advisor of an "
            f"agricultural catalog: {what}?"
        ),
        "criteria": {"true": true, "false": false},
    }


HANDOFF_ASKS: dict[str, dict[str, Any]] = {
    "brings_a_complaint": _asks(
        "does the customer complain about a product they already bought",
        "They say something they already bought did not work, arrived in bad condition or damaged the crop. Examples: "
        "'I sprayed the Silverstrike and the worm is still there', 'the jug arrived broken', 'the product burned my "
        "leaves'.",
        "They ask about a product they have not bought yet, whether it will work for them, how to apply it, or "
        "describe the pest they have. Examples: 'does Silverstrike really kill the worm?', 'I have worm in "
        "the corn and I can't get rid of it', 'how often do I apply it?'.",
    ),
    "asks_for_return": _asks(
        "does the customer want to return, exchange or have replaced something they already bought, or ask about the "
        "warranty",
        "They want to return or exchange what they bought, have it replaced, or ask about the warranty. "
        "Examples: 'I want to return the two liters', 'can you exchange it for the 5 L one?', 'does it have a "
        "warranty?'.",
        "They have not bought yet, or they change what they are ordering before paying. Examples: 'better give me "
        "the 5 L one', 'change my order to 3 liters', 'remove the Raíz Viva'.",
    ),
    "asks_about_their_order": _asks(
        "does the customer ask about an order they already placed or paid for: whether it shipped, the tracking number, where it is, or "
        "a problem with the delivery",
        "They ask about the status of an order that already exists, or say it did not arrive or that it was "
        "delivered wrong. Examples: 'I already paid for last week's order, has it shipped?', 'can you send me "
        "the tracking number?', 'the courier says it was delivered but I didn't get it', 'my order hasn't "
        "arrived'.",
        "They ask how long shipping takes, how much it costs or where you deliver, even if they already paid, or "
        "they are putting together the current order. Examples: 'when will it reach me in Chimaltenango?', 'I already paid, "
        "how many days until it arrives?', 'how much is shipping?', 'do you deliver to Petén?'.",
    ),
    "corrects_an_invoice": _asks(
        "does the customer ask to correct, cancel or resend an invoice already issued to them, ask for the one from an "
        "earlier purchase, or ask how or when the invoice reaches them",
        "They talk about an invoice that already exists or how it is delivered to them: it came out with a wrong detail, they "
        "want it in another name, it did not reach them, they ask for the one from a past purchase, or they ask whether it is sent "
        "through the chat or in the package. Examples: 'the invoice came out with a different NIT', 'I didn't get "
        "last month's invoice', 'cancel it and make it out to the farm', 'will you send me the invoice "
        "here or does it come in the package?'.",
        "They give their details for this order's invoice for the first time, or correct them before it is "
        "issued, or ask whether you give an invoice. Examples: 'NIT 1234567-8', 'better in the name of the "
        "farm', 'do you give an invoice?'.",
    ),
    "shipping_outside_guatemala": _asks(
        "does the customer ask for the order to be sent to another country, outside Guatemala",
        "They name another country or a city in another country for the delivery. Examples: 'I need it in San "
        "Salvador', 'do you ship to Honduras?', 'I'm from Tapachula, Mexico'.",
        "The delivery is in Guatemala, in any department, or they did not say where. Examples: 'do you deliver "
        "to Cobán?', 'it's for Petén', 'how much is shipping?'.",
    ),
}
"""What the customer asks for and the advisor does not resolve however well it answers: it escalates before the writer writes.

Each name is a row of `HANDOFF_ASKED` (`roles/human_handoff.py`), which says the CRM
reason. They go in the same request as `SALE_QUESTIONS`, over the same `conversation`, so they do not
cost a separate one. Credit and check are not here: they come from the
`payment_method` label (`pays_with_credit_or_check` in `LABEL_GATES`).
"""


ALERT_ASKS: dict[str, dict[str, Any]] = {
    "ambiguous_order": _asks(
        "is what the customer wrote impossible to understand as an order or as a question",
        "They wrote a loose word or phrase that does not clearly name a pest, a crop, a "
        "product of the trade or a question, without the advisor having asked them for a detail: a name, a "
        "place, something cut off or unrelated. Examples: 'Bellota', 'Juan Carlos', 'La Esperanza', "
        "'ok ok', '???'.",
        "It is clear what they want, even if it is little or the catalog does not have it: a greeting, a product, "
        "a pest, a crop, a purchase, a payment. Examples: 'hi', 'Catalog', 'Escudo', "
        "'leafcutter ants', 'I have a problem on the tomato', 'do you sell chlorpyrifos?', 'yes (to: Do you want it?)'. "
        "It is also a detail the advisor just asked them for (a NIT, a name, an address, a "
        "quantity), even if it comes alone: '1234567-8 (to: Can you give me your NIT?)', 'Juan Pérez (to: who receives it?)'.",
    ),
}
"""What the customer said and the writer has to know before writing: each name is a row of `ALERT_LINES`.

It travels in the same request as `SALE_QUESTIONS` (`STATE_QUESTIONS`), so it does not cost a separate
one. `ambiguous_order` dates from Sep 26, 2026: "Bellota", after the Escudo
ad, was read as a product that does not exist, the writer answered "We do not sell Bellota" and
the guardian escalated with `product_not_found` (0.66).

On Oct 1, 2026 the detail the advisor asked for was added: with the sale asking for the
invoice, "Juan Carlos Pérez" gave 0.81–0.85, the address 0.72–0.77 and "CF" 0.73–0.76, and the
writer would have asked them what they need. On 11 messages, n=2, across three wordings:
with this one, the sale's details give 0.05–0.47, "Bellota" with an ad 0.75–0.78 (same as
before), "Juan Carlos" 0.84–0.85 and "hi" 0.42–0.45; 8/11 before, 11/11 after. Only the
examples on the `false` side, without "without the advisor having asked them for a detail", left "Bellota"
at 0.69.
"""


TAKEN_OVER: frozenset[str] = frozenset({
    "quality_complaint",
    "warranty_return",
    "quote_not_found",
    "billing_data",
    "out_of_coverage",
    "card_payment",
    "sale_completed",
})
"""The reasons with which the host turns the advisor off in that conversation until a person reactivates it.

They are the host's "heavy" ones (plus `technical_error`, which belongs to the host
and does not come from here), since Sep 28, 2026. The rule on this side: a reason
that turns the advisor off comes out only on the way in (`HANDOFF_ASKED` and `sold`), when the
writer knows before writing that it is its last message and says so. The guardian on the way
out cannot choose them: its answer is already written, and with "do you take cards?"
answered ("transfer only", `card_payment`) or a NIT with a question
(`billing_data`) it turned the advisor off in the middle of a sale without the customer
knowing that a person now answers them.
"""

REPLY_REASONS: dict[str, str] = {k: v for k, v in HANDOFF_REASONS.items() if k not in TAKEN_OVER}
"""The reasons the guardian on the way out can choose: the ones that notify a person while the advisor carries on."""

HANDOFF_REASON_QUESTIONS: dict[str, dict[str, Any]] = {
    HANDOFF_REASON: {
        "type": "choice",
        "instructions": (
            "Assuming this conversation needs a person from the business: what is it about? "
            "`customer` is what the customer has said so far, in order, and `advisor` is the latest "
            "answer of an agricultural catalog's advisor. Choose by what the customer needs, "
            "not by the advisor's words."
        ),
        "criteria": REPLY_REASONS,
    },
}
"""What is asked about the answer and comes back not as a probability but as a label.

A `choice` picks one option among those in `criteria` and returns the
distribution; a `Judge` returns probabilities by name, so this does not
enter through that door and comes out through `QuestionJudge.label`. It travels in the SAME request as the
noul of `REPLY_QUESTIONS`, with the premise stated ("assuming it needs a
person"): it is a speculative question, answered just the same when the answer
does not escalate, and the code discards the label if the noul did not reach the threshold. That way
the reason does not cost a separate request.

Why a `choice` and not eighteen noul: the reasons compete with each other, only one
is the one that goes, and eighteen independent questions about the same state
can say yes to three. Why the separate noul and not a `choice` with a
"do not escalate" option: with eighteen options, the yes is split among several and
"do not escalate" wins with less than half. The binary decision is the one that has
to be calibrated; the label only has to be the best of those there are.

Tested with the same 16 from Sep 22, 2026, in the same request:
nine of eleven with the expected reason, seven of them with confidence 1.00. The
two that do not are the same pair, which overlap by construction:
`product_not_found` where `certification_not_confirmed` was expected, with
confidence 0.71 and 0.73, when what the catalog does not cover is the crop and not the
product. A case that falls in the neighboring bucket is attended to all the same; one that does not
escalate is not. Below the threshold the label means nothing and that is why it is thrown away:
in the five turns that do not escalate, `other` came out three times and twice
some arbitrary reason.

`certification_not_confirmed` left `HANDOFF_REASONS` on Sep 26,
2026: every product is used on every crop, so a crop that
is not in the datasheet is not something the advisor did not know and has no queue of its own.
"""


COMPACT = """Read this WhatsApp conversation between a customer and the advisor of an agricultural catalog.
Write a JSON with what the customer has said so far, so that someone can read it without reading the
conversation. Choose the fields yourself according to what is there (for example the crop, the pest or the
problem, the product they named, the area or the quantity, whether they said they are buying, how they pay, the
invoice and delivery details, and whatever else they said). In each field copy the customer's words, do not
interpret or complete them. What the customer did not say does not go in: no empty fields and no
assumptions. What the advisor said does not count as said by the customer. The exception is
when the customer answers an advisor question with something that can only be understood with the
question ("yes", "no", "go ahead", "that one", "the first one"): there also copy the question they
answered, in the same field, like this: "yes (to: Do you want me to prepare the order for 4 liters?)".
One value per field, no lists: if they said the same thing several times it goes once, and if they confirmed something
they had already said their words go in, not the confirmation.
A message can say several things ("4 liters, how do I pay?"): each one goes in, questions too.
A question goes in while it stays open: if the advisor already answered it and the customer moved on (the price they
were already given, how to pay when they already chose), it does not go in, but the product, the crop or the pest they named
in it does.
Answer only with the JSON.

"""
"""The compaction request. No schema: the model sets the fields (see the module).

Every part of a message goes in, and old questions do not, since Sep 25,
2026. "4 liters, how do I pay?" stayed as `quantity: 4 liters` without the question, and the
"how much is Silverstrike?" from the first turn stayed in the state as if they were still
asking the price: `wants_to_buy` gave 0.48–0.69 on completed purchases. With the two
lines, 0.78–0.93, and those who only ask stay at 0.03–0.23 (8 conversations
by 3, USD 0.03). Naming the payment method in `wants_to_buy` added nothing on top.

A "yes" alone says nothing: on Sep 20, 2026 the customer answered "yes" to
"Do you want me to prepare the order?" and the state said `"answer": "yes"`, the
judge read 0.12 and `doubts` (today `decision`) did not close in four turns. That is why the answer to an
advisor question carries the question alongside: the only time what the
advisor said enters the state, and it enters as context for the customer's words, not
as said by them. `SALE_QUESTIONS` knows how to read that form. No lists because the judge
reads them halfway: the same "yes" to the order gave 0.92 as a string and 0.70 as a
list of one. And the confirmation does not overwrite what was said because the judge does not deduce:
"yes (to: Is it 2 manzanas?)" in `area` gave 0.25, "about 2 manzanas" 0.92.

Tested live on Sep 20, 2026, 9 cases compacted with gpt-5.6-luna
and judged: "yes", "go ahead" and "yes let's reserve" to the order between 0.86 and 0.93; "no" to the
order 0.04, "yes" to "is the dose clear?" 0.05; "yes" to "is it white
fly?" closes `pest` at 0.89 and "I have a problem on the tomato" stays at 0.05.

The cart left this request on Sep 28, 2026 and has its own, `CART_PROMPT`.
"""

CART_FIELDS = """`product` is the name of the product; if the advisor
named it, as the advisor named it. `presentation` is the container size, the color or the width as
it was discussed ("1 L", "20 L", "1 kg", "Yellow 0.15"), or null if nobody said it. `quantity` is a number:
how many of that presentation, or null if they did not say it.
A quantity with a unit is the number with the unit alongside: "5 liters of Silverstrike" is `quantity` 5
and `presentation` "1 L"; "2 kilos" is `quantity` 2 and `presentation` "1 kg"; "a 4 liter jug"
is `quantity` 1 and `presentation` "4 L". If the customer names the unit once for several
products ("2 liters of Silverstrike and 2 of Escudo"), it holds for all of them: both are 2 of "1 L".
What the advisor proposed and the customer accepted counts ("that would be 2 rolls of 10 cm" and the customer says
"yes"), and a bare number that answers "how many?" is the quantity.
"""
"""What `product`, `presentation` and `quantity` are: the same for the whole cart and for its changes."""

CART_PROMPT = (
    """Read this WhatsApp conversation between a customer and the advisor of an agricultural catalog.
Write the cart: what the customer is going to buy so far, across the whole conversation.
Answer only with a JSON like this: {"cart": [{"product": ..., "presentation": ..., "quantity": ...}]}.
One object per product and presentation. """
    + CART_FIELDS
    + """The cart is of the whole conversation: what they ordered in an earlier message stays, with its
presentation and its quantity, until the customer changes or removes it. If they change the product, the
presentation or the quantity, the last thing they said goes in. "Add 2 more" adds to what was already there.
What the customer only asked about or discarded does not go in; if they have not ordered anything yet, {"cart": []}. No prices.

"""
)
"""The cart request: what the two agreed on, normalized and as a list, which
`world/order.py` puts against the catalog.

It has had its own call since Sep 28, 2026, in parallel with `COMPACT`. Until
then it was a field of the compaction, because that one already read the whole conversation, and the
model mixed the two tasks: "2 liters of Silverstrike" stayed as `quantity` 2 with no
presentation, or as `presentation` "5 liters" with no quantity, and the order came out with no price. In
the 10 flows of `flows-cart.tsv` at n=2 the cart came out right in 38 of 54 turns; with the
line about the quantity with a unit, 50 (evals/runs/ab-20260928-011319, USD 0.65). Still
failing were "2 liters of Silverstrike and 2 of Escudo" and the Silverstrike from turn 1 that turn 2 lost
again, which are the two extra lines of this request. In the same flows at n=2, against the
compaction with that line: cart 52/54 to 54/54, `met` 48 on both sides and the
same tokens per turn (evals/runs/ab-20260928-012405, USD 0.65).
"""

CART = "cart"
"""The field of `CART_PROMPT`'s JSON that carries the order."""

CART_CHANGES_PROMPT = (
    """Read this WhatsApp conversation between a customer and the advisor of an agricultural catalog.
Below is the cart as it was recorded, one line per number. What is recorded already counts everything the
customer ordered before their last message: the changes come only from the last message, read with what the
advisor said to them just before. Answer only with a JSON like this:
{"changes": [...]}, one object per change:
- {"op": "add", "product": ..., "presentation": ..., "quantity": ...}: something they ordered or accepted and
  that is not recorded.
- {"op": "change", "line": n, "presentation": ..., "quantity": ...}: a recorded line whose
  presentation or quantity they changed. `quantity` is the total that remains: "add 2 more" to a
  line of 3 is 5. What does not change goes as null.
- {"op": "remove", "line": n}: a line they took out.
"""
    + CART_FIELDS
    + """An order from an earlier message is already recorded: do not add it or sum it again. What the customer
only asked about or discarded does not go in. If nothing changes, {"changes": []}. No prices.

Recorded cart:
{cart}

"""
)
"""The cart of a deal: it starts from what is recorded (`deal.items`) and the model writes only the changes.

Since Oct 8, 2026, for the knowledge deal (deals doc, phase 3). The whole
cart (`CART_PROMPT`) is built from the conversation, which arrives cut to six turns: a longer
deal lost what came before the window, and what the operator added by hand is not in the
conversation. With the changes, a line only goes away if the model writes `remove`. The
lines are named by number so that the code does not have to match names.

Measured on Oct 8, 2026, the prompt alone on 12 written messages at n=2 (adding,
removing, changing quantity and presentation, accepting what the advisor offered, a deal that started
before the window, a line the operator loaded, a question that changes nothing): 24/24,
USD 0.005. The 2 the probe marked wrong were the probe's fault: "1 of Brimnitro" with no size goes with
`presentation` null, as the rule says, and the advisor asks.

The phase 3 A/B at n=3 found that `cart-adds-per-turn:4` took the Escudo from 3 to 6 and to 9:
the model reapplied the "add 3 liters" from an earlier turn. It was told that what is recorded
already counts everything ordered before the last message and that the changes come only from that message. The
probe with 3 more add-per-turn cases, n=2: 28/30 (the same 2 Brimnitro ones). Seven cart
flows with `--deal`, n=3 (USD 0.38): order 59/59 (adds-per-turn 11/11; one turn was cut by
OpenAI moderation), and `met` the same as before in what is not the order.
"""

CART_CHANGES = "changes"
"""The field of `CART_CHANGES_PROMPT`'s JSON that carries the changes."""

CART_EMPTY = "(empty)"

FORM_PROMPT = """Read this WhatsApp conversation between a customer and the advisor of an agricultural catalog.
Below are the details for invoicing and delivering the order as recorded so far. Write
only what changes with this conversation: the fields the customer gave that are not recorded, the ones they
corrected with their new value, and the ones they asked to remove, with null. What is recorded and did not change, do not
write: it stays as it is.
Answer only with a JSON like this: {{"changes": {{"<field>": "<value>" or null, ...}}}}, or {{"changes": {{}}}}
if nothing changes.

The fields:
{fields}

How they are recorded:
- Each field goes with the customer's words, as they gave it: do not interpret or complete it.
- `nit` with its hyphen if it has one ("1234567-8"), or "CF" if they said final consumer or that they have no NIT.
- `recipient` is the name of the person receiving the order: "he receives it himself" or "I'll receive it" is the name
  of whoever is speaking or of the invoice, not those words. `phone` is the phone of the person receiving.
- `address` is the full delivery address, with the municipality and the department if they said them.
- What the customer did not say does not go in: no empty fields and no assumptions. What the advisor said does not count
  as said by the customer, unless the customer confirms it.
- A detail already recorded changes only if the customer corrects it or gives another in its place ("better
  send it to…", "the NIT is a different one", "change the address to…"). Repeating it the same or in other words
  is not a change.

Recorded so far:
{seed}

"""
"""The billing form request (`world/form.py`). `{fields}` is one line per field of
`forms/billing.md` that the model records (`FORM_LINE`) and `{seed}` what is recorded, as JSON.

It asks for changes and not the whole form, like stemcell's since Oct 3, 2026: staying silent about a
field is not touching it. It replaces `BILLING_PROMPT` since Oct 8, 2026, which extracted the
whole invoice once, on the turn `said_billing_data` passed the threshold; the lines for
`nit`, `recipient` and `address` are its own (12/12 on 12 conversations, Oct 3, 2026). It runs on
the turns where `gives_billing_data` passes the threshold (`roles/form.py`).

Tested with gpt-6-luna on 7 conversations with the record seeded, n=2 (about 520 input
tokens per call): 14/14. It records from scratch, "final consumer" as CF, "I'll receive it, my name is Ana"
with the record intact, changes only the address, corrects the NIT when the customer corrects it, records
the legal name, and with a different old NIT in the conversation it leaves the record and adds the phone.
"""

FORM_PREVIOUS = """The details from their earlier purchase, which they have not yet confirmed for this one:
{previous}
If the customer confirms they are unchanged ("yes, the same ones", "same as last time"), write them exactly
as they are; if they confirm some and change others, the confirmed ones exactly as they are and the others with their new value. If they
said nothing about them, do not write them.

"""
"""What goes after the record when the host sent `previous_form`: the details of the
sale that already closed. They are not taken as good: the advisor asks whether they are unchanged (`FORM_CONFIRM`) and
the model copies them when the customer confirms. Since Oct 8, 2026."""

FORM_CHANGES = "changes"
"""The field of `FORM_PROMPT`'s JSON that carries the changes."""

FORM_LINE = "- `{id}`: {label}"

PRODUCT = "datasheet"
SEVERAL = "several"
NO_PRODUCT = "none"


def product_question(titles: tuple[str, ...]) -> dict[str, Any]:
    """Which datasheet a cart name is: a `choice` with one option per datasheet of the bundle.

    The options are `f1`, `f2`… in the order of `titles`, plus `SEVERAL` and `NO_PRODUCT`. It is
    asked about `{"product": ...}`, what the cart recorded, only when it is not a title as
    it stands.

    Until Oct 1, 2026 code looked it up (`find_product`): string similarity
    (`SequenceMatcher`, 0.8) on the name without spaces or formulation. On 24 names (those
    from the test's 60 real sales, other brands and abbreviations), n=2, the code 23/24 ("bio bt"
    did not make it) and this `choice` 24/24, telling "Stelvane" (several) from "glyphosate" (none).
    USD 0.00005 per name.
    """
    criteria = {f"f{i}": f"«{t}»." for i, t in enumerate(titles, 1)}
    criteria[SEVERAL] = "The name is the beginning of several products on the list equally and does not say which: 'Stelvane', 'Grelthar'."
    criteria[NO_PRODUCT] = "It names no product on the list: another brand, an ingredient, or a class of product without its name."
    return {
        PRODUCT: {
            "type": "choice",
            "instructions": (
                "`product` is the name of a product as it was recorded in a WhatsApp order, sometimes misspelled, "
                "abbreviated or without the formulation. Which of the catalog's products is it?"
            ),
            "criteria": criteria,
        }
    }


PRESENTATION = "presentation"
OTHER_UNIT = "other_unit"
UNCHOSEN = "unchosen"


def presentation_question(options: tuple[str, ...]) -> dict[str, Any]:
    """Which of the datasheet's presentations the customer chose: a `choice` with one option per row of the table.

    The options are `p1`, `p2`… in the order of `# Presentations`, plus `OTHER_UNIT` and
    `UNCHOSEN`. It is asked about `{"product": ..., "asked": {"presentation": ..., "quantity": ...}}`,
    what the cart recorded, only when the datasheet has more than one and the record is not one of
    them as it stands.

    Until Oct 1, 2026 code chose it (`find_presentation`), with a dictionary of
    how each unit is said in the chat, centimeters converted to meters and an `if` per case
    ("1 gallon" of something that comes in liters, "15" as the 0.15 mt roll). On those same 16
    cases, n=2, this `choice` chose correctly 16/16 (USD 0.0008), with "jerrycan" and "half gallon", which
    the code did not know.
    """
    criteria = {f"p{i}": f"The presentation «{o}»." for i, o in enumerate(options, 1)}
    criteria[OTHER_UNIT] = (
        "Names a unit of size that none of those presentations has: gallons of something "
        "sold in liters, kilos of something sold in liters."
    )
    criteria[UNCHOSEN] = "Does not say the size, or what it says fits more than one presentation equally."
    return {
        PRESENTATION: {
            "type": "choice",
            "instructions": (
                "`product` is a product of an agricultural catalog and `asked` is the presentation and the quantity "
                "as the customer said them. Which of the datasheet's presentations did they choose? A number with a "
                "unit that is not the size of any presentation is how many they are taking, not the size: '4 liters' "
                "of something that comes in 1 L and 20 L is the 1 L one. A number without a unit that is the size of one "
                "is that one. A width in centimeters is the same in meters (15 cm is 0.15 mt), and a bare number "
                "on a product sold by width is that width in centimeters. Customers call the 20 L container a "
                "jerrycan."
            ),
            "criteria": criteria,
        }
    }

SAID_PROMPT = """Read this WhatsApp conversation between a customer and the advisor of an agricultural catalog.
List what the advisor already gave the customer in its earlier messages, so that it does not repeat it.
Answer only with a JSON like this: {"already_said": [...], "asks_again": [...], "unanswered": [...]}.
In `already_said`, one short line per thing the advisor gave: what it is and about what, without copying it whole
("the dose of Silverstrike for thrips", "the bank accounts of Agroinsumos Ceiba", "the price
of 2 containers of 1 L of Silverstrike", "the cost and the days of shipping", "the payment methods"). The
questions the advisor asked the customer go in too, with whether the customer already answered
("asked how many liters they want; the customer answered 5", "asked for the NIT; unanswered").
In `asks_again`, whatever in `already_said` the customer's last message asks for again, in their
words ("can you send me the accounts again?"), or the empty list. Asking something new about the same thing
is not asking for it again.
In `unanswered`, which of these things the advisor already asked the customer for and the customer has not yet
answered, by name: "pest" (what pest they have or what product they are looking for), "quantity" (how many liters
or containers they want), "decision" (whether they want it), "method" (whether they pay by link or transfer), "data"
(the invoice or shipping detail the advisor asked for: if the customer gave that one, even if others are missing, they
already answered it). Empty list if none remains like that.

"""
"""The already-said request: what the advisor gave and asked, so that the writer does not repeat it.

It has had its own call since Sep 28, 2026, in parallel with `COMPACT` and
`CART_PROMPT`, for the same reason as the cart: the writer had the no-repeat rule
along with all the others and followed it halfway (asked for the quantity a
third time, copied the accounts again). Here the model does one single thing, and the
writer receives the finished list (`roles/alerts.py`). `asks_again` separates what the
customer does want to hear again, so that the writer does not have to decide it.

Tested before building it on the histories of five probes, about 1,000 tokens per
conversation: the accounts, the doses, the prices and the shipping come out in `already_said`; "asked
how many liters; did not answer" comes out twice where the advisor asked it twice; "can you send me
the accounts again?" comes out in `asks_again` and "it would be transfer" does not.

`unanswered` names the sale's leaves (`ASKS`) the advisor already asked for with no
answer, so that the sale's line does not ask for them again (`sale_line`): with only the
list, `SALE_LINE` kept ordering the quantity to be asked and won (does-not-repeat-quantity 0/2 with
and without the report, Sep 28, 2026). On the same histories it marks `quantity` in
does-not-repeat-quantity and nothing in asks-quantity-after-dose or does-not-repeat-accounts.
"""

SAID = "already_said"
AGAIN = "asks_again"
OPEN = "unanswered"


TURN_CASE = "case"
TURN_CASES: dict[str, str] = {
    "we_do_not_sell": (
        "Asks whether you sell a product, a brand, an active ingredient or a class of product "
        "(herbicides, chemical fertilizers) by name, and the report says no datasheet has it."
    ),
    "not_covered": "Is looking for something for a pest or a problem, and the report says no datasheet covers it.",
    "discontinued": "The only product the report found for what they are looking for is discontinued, and the report brings no other current one that works for them.",
    "no_data": (
        "Asks something agronomic (a dose, a way of applying, a mix) about a product the "
        "report found, and the datasheet does not carry that fact in any form: not general, not for another crop, "
        "not in another unit."
    ),
    "normal": (
        "Any other turn. Also when the datasheet carries a general dose or one for another crop even if "
        "not for theirs, when it carries it in another unit, when they ask what to use instead of a "
        "discontinued product and the report brings others, when a loose word is not a product, or when they do not "
        "ask anything about the catalog. Also when what they ask for is a quantity that comes from the dose with "
        "some arithmetic (how much for a drum, a sprayer pump or a backpack sprayer of so many liters, how much for so many "
        "manzanas): if the report brings the dose, it is `normal` even if it says the datasheet does not carry that quantity."
    ),
}
TURN_CASE_QUESTIONS: dict[str, dict[str, Any]] = {
    TURN_CASE: {
        "type": "choice",
        "instructions": (
            "`last_message` is what the customer of an agricultural catalog wrote and `report` what "
            "whoever searched found in the catalog. Which case is this turn? If `last_message` does not "
            "ask or request anything (an ok, a thanks, a greeting), it is `normal` even if the report says "
            "something is not there."
        ),
        "criteria": TURN_CASES,
    }
}
"""What class of turn it is, read from the searcher's report: the writer receives only that case's rule (`CASE_LINES`).

Until Sep 28, 2026 the four rules (we do not sell, not covered, discontinued,
missing agronomic fact) always went in `WRITER`, and the writer had to decide which one
applied. It is a TypeSafe `choice` over the question and the report, without the conversation: the
case is decided by what the searcher found. Tested before building it on 18 saved
probe reports, n=2: 13/18 with the first wording, which marked `no_data` when the
datasheet carried a general dose and not the crop's (melon and watermelon, tomato); 36/36 with this one.
Vivane, discontinued, comes out `normal` because the report does not say so: the case sees what
the searcher sees.

On Sep 30, 2026, from a prod conversation of the 29th: "Herbicde you dont have" came out
`not_covered`, because "a type of product" was there, and the `not_covered` line escalated it to the
engineer; and "OK thanks", with the searcher going back over the herbicides, too. A class
of product that is not sold moved to `we_do_not_sell`, and a message that asks nothing is
`normal`. On 12 question and report pairs, n=2: 16/24 before, 24/24 after; leafcutter ants,
rust and weeds stay in `not_covered`.

The same day, from the same conversation: "how much do I put in the drum?" came out `no_data`
when the searcher wrote that the datasheet does not carry the quantity for a drum, and the
`no_data` line sent it to the engineer after doing the arithmetic. A quantity that comes from the dose
with some arithmetic is `normal`. On the 6 saved reports of drum-roses, n=2: 8/12 `normal`
before, 12/12 after; pre-harvest interval and mixing with copper stay in `no_data`.
"""
