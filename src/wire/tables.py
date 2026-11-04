"""The two tables of the Spanish wire: what each field is called, and what each value says.

Everything here is data, English first: the left side is what the interior says, the right side is
what knowledge's `contrato/` says. `translate.py` reads these in both directions, so a pair is
written once and cannot drift between the request and the answer.

`SHAPES` is the names: one entry per class of `schemas/queries.py` and `schemas/compaction.py`
(a test keeps the two in step), plus the few objects that only exist inside an open dict (the
order of a judgment, a line of the payment link). `VALUES` is the words: the closed vocabularies
the interior and the host both read (the reasons of a handoff, the stage of a deal, the verb of a
cart change). Each table is injective, because a table that is not could not be turned back.

What is deliberately NOT in here, because it is not a name but data that crosses as it is:
the customer's text, the bundle's prose (labels, rule ids and actions, the `intent` of a plan
op), the model-written `state` of a judgment, the `verb` of an op (catalejo's API: `propose`,
`resolve`, `done`, `reject`, ...) and the `kind` of an effect (knowledge's own `Kind*` constants).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["scalar", "object", "list", "scalars", "map", "args", "opaque"]
"""How a field's value is read: a scalar, one object, a list of objects, a list of scalars, a dict, the
`[key, value]` pairs of an effect, or something that goes through untouched."""


@dataclass(frozen=True, slots=True)
class Field:
    """One English field and what it is called on the wire.

    `table` is a `VALUES` table: for a `scalar` or `scalars` it translates the values, for a
    `map` it translates the keys. `keyed` names a `KEYED` table: which `VALUES` table reads the
    value of each key of a `map`. `shape` is the nested object (of one value, of each item of a list).
    `extra` is a field knowledge sends or reads and the interior has no field for: it is carried
    under its English name so the payload survives the round trip, and is dropped before the
    interior sees it (see `to_english(extras=False)`).
    """

    wire: str
    kind: Kind = "scalar"
    shape: str = ""
    table: str = ""
    keyed: str = ""
    extra: bool = False


def f(wire: str, kind: Kind = "scalar", *, shape: str = "", table: str = "", keyed: str = "", extra: bool = False) -> Field:
    """`Field` in one short word, for the tables below."""
    return Field(wire, kind, shape, table, keyed, extra)


VALUES: dict[str, dict[str, str]] = {
    # --- the deal
    "deal_kind": {"sale": "venta", "quote": "cita"},
    "deal_stage": {
        "open": "abierto",
        "in_payment": "en_pago",
        "won": "ganado",
        "lost": "perdido",
        "cancelled": "cancelado",
    },
    "payment_state": {"paid": "pagado", "pending": "pendiente"},
    "item_op": {"add": "agregar", "change": "cambiar", "remove": "quitar"},
    "changes_deal": {"clear": "vaciar"},
    # --- the memory: who spoke, with the host's words
    "memory_kind": {"customer": "cliente", "advisor": "asesor", "operator": "operador", "system": "sistema"},
    # --- the handoff. The reasons are the CRM's: every value of the right side has to be one knowledge
    # accepts (`validHandoffMotivos`, checked by `tests/wire/test_handoff.py`); one it does not know it turns into `otro`.
    "handoff_origin": {"requested_by_agent": "solicitado_por_el_agente"},
    "handoff_reason": {
        "quality_complaint": "reclamo_calidad",
        "warranty_return": "garantia_devolucion",
        "product_outside_promo": "producto_fuera_promo",
        "other_promotions": "otras_promociones",
        "other_stores": "otras_tiendas",
        "outside_hours": "fuera_horario",
        "out_of_coverage": "fuera_cobertura",
        "billing_data": "datos_facturacion",
        "card_payment": "pago_tarjeta",
        "unverified_discount": "descuento_no_verificado",
        "quote_not_found": "cotizacion_no_encontrada",
        "special_order": "pedido_especial",
        "sale_completed": "venta_completada",
        "order_on_delivery": "pedido_contra_entrega",
        "product_not_found": "producto_no_encontrado",
        "unverifiable_specification": "especificacion_no_verificable",
        "other": "otro",
    },
    # --- the payment: how the customer said they pay, and what they asked about it
    "payment_methods": {
        "link": "link",
        "transfer": "transferencia",
        "credit": "credito",
        "check": "cheque",
        "on_delivery": "contra_entrega",
        "other": "otro",
        "none": "ninguno",
    },
    "payment_requests": {"account": "cuenta", "link": "link", "methods": "formas", "nothing": "nada"},
    # --- the datasheet: the `state` of its frontmatter (`okf/FORMAT.md`); empty says nothing and is not looked up
    "datasheet_state": {
        "current": "vigente",
        "out_of_stock": "agotado",
        "discontinued": "descontinuado",
        "withdrawn": "retirado",
    },
    # --- the sale's plan: the ids of `core_agent.SESSION`, and the names of the gates that close them
    "plan_id": {
        "diagnosis": "diagnostico",
        "pest": "plaga",
        "product": "producto",
        "recipe": "receta",
        "quantity": "cantidad",
        "decision": "decision",
        "payment": "pago",
        "method": "medio",
        "charge": "cobro",
        "billing": "facturacion",
        "data": "datos",
    },
    # --- the judge: the name of each question it answers (a key of `judgment.p`, a `done_when`)
    "question": {
        "has_search_terms": "hay_con_que_buscar",
        "said_quantity": "dijo_cantidad",
        "wants_to_buy": "quiere_comprar",
        "said_billing_data": "dijo_datos_de_factura",
        "asked_for_the_datasheet": "pidio_la_ficha",
        "asked_for_the_catalog": "pidio_el_catalogo",
        "gives_billing_data": "da_datos_de_facturacion",
        "asks_for_order_summary": "pide_resumen_del_pedido",
        "asks_to_start_over": "pide_empezar_de_cero",
        "said_payment_method": "dijo_medio_de_pago",
        "asked_for_the_account": "pidio_la_cuenta",
        "pays_with_link": "paga_con_link",
        "pays_with_credit_or_check": "paga_con_credito_o_cheque",
        "recommended_a_product": "recomendo_un_producto",
        "hands_off_to_a_person": "lo_pasa_a_una_persona",
        "did_not_give_what_was_asked": "no_le_dio_lo_que_pidio",
        "asks_for_the_unsolvable": "pide_lo_que_no_resuelve",
        "brings_a_complaint": "trae_un_reclamo",
        "asks_for_return": "pide_devolucion",
        "asks_about_their_order": "pregunta_por_su_pedido",
        "corrects_an_invoice": "corrige_una_factura",
        "shipping_outside_guatemala": "envio_fuera_de_guatemala",
        "ambiguous_order": "pedido_ambiguo",
        "order_with_quantities": "pedido_con_cantidades",
        "chargeable_order": "pedido_cobrable",
        "queried_the_catalog": "consulto_el_catalogo",
        "opens_a_datasheet": "mire_una_ficha",
        "read_the_payment_methods": "leyo_las_formas",
        "read_the_accounts": "leyo_las_cuentas",
        "complete_invoice": "factura_completa",
    },
    # --- the judge's labels: the name of each `choice`, and the case of the turn
    "label": {
        "payment_method": "medio_de_pago",
        "payment_request": "pedido_de_pago",
        "escalation_reason": "motivo_de_escalada",
        "case": "caso",
    },
    "turn_case": {
        "we_do_not_sell": "no_vendemos",
        "not_covered": "no_cubre",
        "discontinued": "descontinuado",
        "no_data": "sin_dato",
        "normal": "normal",
    },
    # --- the effects: the id of each one `EFFECT_RULES` proposes (and the two handoffs)
    "effect_id": {
        "send_datasheet": "send_ficha",
        "send_catalog": "send_catalogo",
        "send_payment_accounts": "send_payment_accounts",
        "send_payment_link": "send_payment_link",
        "sap_draft": "sap_draft",
        "handoff": "handoff",
        "takeover": "takeover",
    },
    # --- the billing form: the ids of `okf/forms/billing.md`
    "form_field": {
        "legal_name": "razon_social",
        "nit": "nit",
        "recipient": "recibe",
        "phone": "telefono",
        "email": "correo",
        "address": "direccion",
        "payment_method": "medio_pago",
    },
    # --- the keys of an effect's `[key, value]` args. The ones knowledge reads in its own tongue
    # (`moneda`, `nombre`, `recibe`, ...) and the ones that are the same on both sides, written out so
    # a key nobody has seen is a gap and not a silence.
    "args_key": {
        "path": "path",
        "item": "item",
        "currency": "moneda",
        "total": "total",
        "nit": "nit",
        "name": "nombre",
        "recipient": "recibe",
        "phone": "telefono",
        "address": "direccion",
        "payment_method": "medio_pago",
        "origin": "origin",
        "reason": "reason",
        "url": "url",
        "file": "file",
        "order": "pedido",
    },
}


KEYED: dict[str, dict[str, str]] = {
    "form_value": {"payment_method": "payment_methods"},
    "label_value": {
        "payment_method": "payment_methods",
        "payment_request": "payment_requests",
        "escalation_reason": "handoff_reason",
        "case": "turn_case",
    },
    "args_value": {"origin": "handoff_origin", "reason": "handoff_reason", "payment_method": "payment_methods"},
}
"""Which `VALUES` table reads the value of a given key: the value of `payment_method` in a form, the value of
`origin` in an effect's args. A key with no entry carries data (a NIT, an address) and crosses as it is."""


def _plan_ops() -> dict[str, Field]:
    return {
        "verb": f("verb"),
        "id": f("id", table="plan_id"),
        "intent": f("intent"),
        "status": f("status"),
        "done_when": f("done_when", table="question"),
        "parent": f("padre", table="plan_id"),
    }


SHAPES: dict[str, dict[str, Field]] = {
    # ------------------------------------------------------------------ what comes in (`Consulta`)
    "Query": {
        "question": f("pregunta"),
        "history": f("historia", "list", shape="TurnIn"),
        "sale": f("venta", "list", shape="OpIn"),
        "effects": f("efectos", "list", shape="EffectIn"),
        "payment": f("pago", table="payment_state"),
        "memory": f("memoria", "object", shape="MemoryIn"),
        "deal": f("deal", "object", shape="DealIn"),
        "customer": f("cliente", "object", shape="CustomerIn"),
        "resumption": f("retomada"),
        "interview": f("entrevista", "opaque"),
        "form": f("formulario", "opaque"),
        # what knowledge sends and the interior has no use for
        "trace": f("traza", extra=True),
        "turn_id": f("turnId", extra=True),
        "conversation_id": f("conversationId", extra=True),
        "attachments": f("adjuntos", "list", shape="Attachment", extra=True),
        "notice": f("aviso", "object", shape="Notice", extra=True),
        "closed_ids": f("cerrados", "scalars", extra=True),
    },
    "TurnIn": {"question": f("pregunta"), "answer": f("respuesta")},
    "OpIn": _plan_ops(),
    "EffectIn": {
        "verb": f("verb"),
        "id": f("id", table="effect_id"),
        "kind": f("kind"),
        "args": f("args", "args"),
        "note": f("note"),
    },
    "MessageIn": {"i": f("i"), "kind": f("kind", table="memory_kind"), "text": f("text"), "date": f("date")},
    "NodeIn": {"l": f("l"), "i": f("i"), "text": f("text")},
    "MemoryIn": {
        "messages": f("mensajes", "list", shape="MessageIn"),
        "tree": f("arbol", "list", shape="NodeIn"),
    },
    "ItemDealIn": {
        "sku": f("sku"),
        "product": f("producto"),
        "presentation": f("presentacion"),
        "quantity": f("cantidad"),
        "price": f("precio"),
        "subtotal": f("subtotal"),
        "price_from": f("precio_de", extra=True),
    },
    "FormDealIn": {
        "fields": f("campos", "map", table="form_field", keyed="form_value"),
        "missing": f("faltan", "scalars", table="form_field"),
    },
    "LinkDealIn": {"url": f("url"), "active": f("activo"), "expires_at": f("vence_en")},
    "PaymentDealIn": {"link": f("link", "object", shape="LinkDealIn"), "paid": f("pagado"), "paid_at": f("pagado_en")},
    "QuoteDealIn": {
        "slot_id": f("slot_id"),
        "at": f("at"),
        "deal_id": f("deal_id", extra=True),
        "version": f("version", extra=True),
        "state": f("estado", extra=True),
        "time_zone": f("time_zone", extra=True),
        "label": f("label", extra=True),
        "event_id": f("event_id", extra=True),
        "meet": f("meet", extra=True),
    },
    "EffectDealIn": {"id": f("id", table="effect_id"), "kind": f("kind"), "status": f("status")},
    "DealIn": {
        "id": f("id"),
        "kind": f("kind", table="deal_kind"),
        "stage": f("stage", table="deal_stage"),
        "version": f("version"),
        "number": f("numero"),
        "from_turn": f("desde_turno"),
        "items": f("items", "list", shape="ItemDealIn"),
        "total": f("total"),
        "currency": f("moneda"),
        "form": f("form", "object", shape="FormDealIn"),
        "payment": f("pago", "object", shape="PaymentDealIn"),
        "quote": f("cita", "object", shape="QuoteDealIn"),
        "effects": f("efectos", "list", shape="EffectDealIn"),
        "opened_at": f("abierto_en"),
        "updated_at": f("actualizado_en"),
        "form_name": f("formulario", extra=True),
    },
    "AddressIn": {"label": f("label"), "address": f("address")},
    "CustomerIn": {
        "name": f("nombre"),
        "nit": f("nit"),
        "legal_name": f("razon_social"),
        "addresses": f("direcciones", "list", shape="AddressIn"),
        "email": f("correo"),
        "phone": f("telefono"),
        "last_appointment": f("ultima_cita", "opaque", extra=True),
    },
    "Attachment": {
        "path": f("ruta"),
        "type": f("tipo"),
        "mime": f("mime"),
        "file_name": f("nombre_archivo"),
        "description": f("descripcion"),
    },
    "Notice": {"reason": f("motivo")},
    # ------------------------------------------------------------------ what goes out (`Respuesta`)
    "AnswerOut": {
        "answer": f("respuesta"),
        "messages": f("mensajes", "scalars"),
        "sources": f("fuentes", "scalars"),
        "grounded": f("fundada"),
        "tokens": f("tokens"),
        "tokens_input": f("tokens_entrada"),
        "tokens_cached": f("tokens_cacheados"),
        "tokens_output": f("tokens_salida"),
        "tokens_typesafe": f("tokens_typesafe"),
        "turns": f("turnos"),
        "halt": f("halt"),
        "fails": f("fails", "opaque"),
        "seconds": f("segundos"),
        "truncated": f("cortada"),
        "no_search_terms": f("sin_que_buscar"),
        "sale": f("venta", "object", shape="SaleOut"),
        "effects": f("efectos", "object", shape="EffectsOut"),
        "form": f("formulario", "object", shape="FormOut"),
        "restart": f("reiniciar"),
        "changes": f("cambios", "object", shape="ChangesOut"),
        "rules": f("reglas", "list", shape="RuleOut"),
        # what knowledge reads and the interior does not (yet) say
        "model": f("modelo", "object", shape="ModelOut", extra=True),
        "llm": f("llm", "object", shape="LLM", extra=True),
        "trace": f("traza", "opaque", extra=True),
        "opted_out": f("opted_out", extra=True),
        "interview": f("entrevista", "opaque", extra=True),
    },
    "SaleOut": {
        "ops": f("ops", "list", shape="OpIn"),
        "state": f("estado"),
        "stage": f("etapa", table="plan_id"),
        "active": f("activa", table="plan_id"),
        "asks": f("pide", "object", shape="AskOut"),
        "pending": f("pendientes", "scalars", table="plan_id"),
        "closed_steps": f("cerradas", "scalars", table="plan_id"),
        "tree": f("arbol"),
        "closed": f("cerrada"),
        "judgment": f("juicio", "object", shape="Judgment"),
    },
    "AskOut": {"id": f("id", table="plan_id"), "what": f("que")},
    "Judgment": {
        "state": f("estado", "opaque"),
        "p": f("p", "map", table="question"),
        "labels": f("etiquetas", "map", table="label", keyed="label_value"),
        "order": f("pedido", "object", shape="Order"),
        "already_said": f("ya_dicho", "scalars"),
        "asks_again": f("pide_de_nuevo", "scalars"),
        "unanswered": f("sin_contestar", "scalars", table="plan_id"),
        "error": f("error"),
    },
    "Order": {
        "items": f("items", "list", shape="OrderItem"),
        "total": f("total"),
        "currency": f("moneda"),
        "chargeable": f("cobrable"),
        "restarted": f("reiniciado"),
    },
    "OrderItem": {
        "said": f("dicho", "object", shape="Said"),
        "product": f("producto"),
        "path": f("ruta"),
        "presentation": f("presentacion"),
        "quantity": f("cantidad"),
        "price": f("precio"),
        "subtotal": f("subtotal"),
        "state": f("estado", table="datasheet_state"),
        "sku": f("sku"),
        "currency": f("moneda"),
        "price_from": f("precio_de", extra=True),
    },
    "Said": {"product": f("producto"), "presentation": f("presentacion")},
    "EffectsOut": {
        "ops": f("ops", "list", shape="EffectIn"),
        "pending": f("pendientes", "list", shape="PendingOut"),
        "state": f("estado"),
    },
    "PendingOut": {
        "id": f("id", table="effect_id"),
        "kind": f("kind"),
        "args": f("args", "args"),
        "executable": f("ejecutable"),
    },
    "FormOut": {
        "title": f("titulo"),
        "fields": f("campos", "map", table="form_field", keyed="form_value"),
        "missing": f("faltan", "scalars", table="form_field"),
        "form_schema": f("esquema", "list", shape="FieldOut"),
    },
    "FieldOut": {
        "id": f("id", table="form_field"),
        "label": f("etiqueta"),
        "type": f("tipo"),
        "required": f("requerido"),
        "options": f("opciones", "scalars", table="payment_methods"),
        "position": f("orden"),
        "group": f("grupo", extra=True),
    },
    "LineOut": {"said": f("dicho"), "option": f("opcion"), "p": f("p")},
    "RuleOut": {
        "id": f("id"),
        "p": f("p"),
        "threshold": f("umbral"),
        "fired": f("disparo"),
        "action": f("accion"),
        "option": f("opcion"),
        "lines": f("renglones", "list", shape="LineOut"),
    },
    "ItemChangeOut": {
        "op": f("op", table="item_op"),
        "sku": f("sku"),
        "product": f("producto"),
        "presentation": f("presentacion"),
        "quantity": f("cantidad"),
        "price": f("precio"),
        "price_from": f("precio_de", extra=True),
    },
    "ChangesOut": {
        "base": f("base"),
        "items": f("items", "list", shape="ItemChangeOut"),
        "form": f("form", "map", table="form_field", keyed="form_value"),
        "deal": f("deal", table="changes_deal"),
        "appointment": f("cita", "opaque", extra=True),
    },
    "ModelOut": {
        "calls": f("llamadas"),
        "attempts": f("intentos"),
        "seconds": f("segundos"),
        "slowest": f("mas_lenta"),
    },
    "LLM": {"provider": f("proveedor"), "model": f("modelo"), "effort": f("esfuerzo")},
    "FailedTurnOut": {
        "detail": f("detail"),
        "tokens": f("tokens"),
        "tokens_input": f("tokens_entrada"),
        "tokens_cached": f("tokens_cacheados"),
        "tokens_output": f("tokens_salida"),
        "tokens_typesafe": f("tokens_typesafe"),
        "model": f("modelo", "object", shape="ModelOut", extra=True),
        "llm": f("llm", "object", shape="LLM", extra=True),
        "trace": f("traza", "opaque", extra=True),
    },
    # ------------------------------------------------------------------ the compactor
    "Compaction": {"memory": f("memoria", "object", shape="MemoryIn"), "max": f("max")},
    "CompactionOut": {
        "nodes": f("nodos", "list", shape="NodeIn"),
        "failed": f("fallidos", "list", shape="FailedOut"),
        "pending": f("pendientes"),
        "tokens": f("tokens"),
        "tokens_input": f("tokens_entrada"),
        "tokens_cached": f("tokens_cacheados"),
        "tokens_output": f("tokens_salida"),
        "seconds": f("segundos"),
    },
    "FailedOut": {"l": f("l"), "i": f("i"), "error": f("error")},
    # ------------------------------------------------------------------ inside an effect's args
    "ArgsItem": {
        "line": f("renglon"),
        "product": f("producto"),
        "presentation": f("presentacion"),
        "quantity": f("cantidad"),
        "price": f("precio"),
        "subtotal": f("subtotal"),
        "item_code": f("item_code"),
    },
}

OPEN: frozenset[str] = frozenset({"OpIn", "EffectIn"})
"""The shapes whose keys nobody but the interior knows: a plan op and an effect op travel to the host and come
back as they are, so a key outside the table crosses untouched and is not a gap. (The interior refuses it
afterwards if it really is unknown: `host/sale.py`, `host/effects.py`.)"""

NOT_ON_THE_WIRE: frozenset[str] = frozenset({"Incoming", "CatalogOut"})
"""The classes of `schemas/` knowledge never sees: the base of what comes in, and `GET /queries/catalog`."""
