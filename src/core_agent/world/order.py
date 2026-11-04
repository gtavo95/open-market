"""The order: what the model noted in `cart` at compaction, set against the catalog by code.

The model names the product, the presentation and the quantity as they were spoken;
nothing here calls it. This module looks up each product among the datasheets
(`title` or `name`) and reads the `# Presentations` table of that datasheet. It
takes the presentation if it is the only one or if what was noted is one of the labels
as is; otherwise, which one the customer chose is decided by the judge (`presentation_question`
in `prompts/judge.py`, applied by `QuestionJudge`) and set here with `choose`.
With product, presentation and a quantity that is a number, the price and the
subtotal. What it does not find stays with the field at `None` and the said value beside it:
the model never sets the price.

It travels in `Judgment.order` up to the host (`sale.judgment.order`) since Sep 25,
2026, and the writer reads it as one more report since that same
day (`roles/order.py`). A product no longer sold (`state` discontinued
or withdrawn) is recognized and not charged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..prompts.judge import OTHER_UNIT
from . import catalog


@dataclass(frozen=True, slots=True)
class Presentation:
    """A row of `# Presentations`: the label shown, its price and its SAP code.

    `code` is the `SAP Code` column, the article of that presentation in the org's SAP;
    empty if the datasheet does not have the column or the row does not say.
    """

    label: str
    price: float | None
    currency: str = ""
    code: str = ""


@dataclass(frozen=True, slots=True)
class Item:
    """A line of the order: what was said, and what the catalog says about it.

    `product` and `presentation` are the catalog's, or `None` if they were not
    found (or if there is more than one possible presentation and what was said does not
    choose). `unit_price` and `subtotal` only with both and the quantity.
    `status` is the datasheet's `state`; `options`, the presentations it
    has when what was said chose none; `other_unit`, that the judge read a
    unit none of them has ("1 gallon" of something that comes in liters);
    `code`, the SAP code of the chosen presentation.
    """

    said_product: str
    said_presentation: str
    quantity: float | None
    product: str | None = None
    path: str | None = None
    presentation: str | None = None
    unit_price: float | None = None
    status: str = ""
    options: tuple[str, ...] = ()
    currency: str = ""
    other_unit: bool = False
    code: str = ""

    @property
    def sold(self) -> bool:
        """Whether the datasheet is sold: empty, `current` or `out_of_stock` (which will come back)."""
        return self.status not in RETIRED

    @property
    def subtotal(self) -> float | None:
        if self.unit_price is None or self.quantity is None:
            return None
        return round(self.unit_price * self.quantity, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "said": {"product": self.said_product, "presentation": self.said_presentation},
            "product": self.product,
            "path": self.path,
            "presentation": self.presentation,
            "quantity": self.quantity,
            "price": self.unit_price,
            "subtotal": self.subtotal,
            "state": self.status,
            "sku": self.code or None,
            "currency": self.currency or None,
        }


RETIRED = frozenset({"discontinued", "withdrawn"})
"""The okf `state`s that say the datasheet is no longer sold (`FORMAT.md`)."""


def presentations(text: str) -> list[Presentation]:
    """The rows of a datasheet's `# Presentations` table: `Size Unit` as the label, `Price` and `SAP Code`."""
    text = "\n" + text
    if "\n# Presentations" not in text:
        return []
    block = text.split("\n# Presentations", 1)[1].split("\n# ", 1)[0]
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in block.splitlines() if line.startswith("|")]
    if len(rows) < 2:
        return []
    head, body = rows[0], [row for row in rows[1:] if not set("".join(row)) <= set("-: ")]
    column_at = {name: i for i, name in enumerate(head)}
    out = []
    for row in body:
        if len(row) != len(head):
            continue
        price = row[column_at["Price"]].replace(",", "") if "Price" in column_at else ""
        currency = row[column_at["Currency"]] if "Currency" in column_at else ""
        code = row[column_at["SAP Code"]] if "SAP Code" in column_at else ""
        out.append(Presentation(f"{row[column_at['Size']]} {row[column_at['Unit']]}", float(price) if price else None, currency, code))
    return out


def exact(said: str, options: list[Presentation]) -> Presentation | None:
    """The presentation without asking: the only one if there is one, or the one the note names as is.

    The rest ("4 liters", "jerrycan", "the yellow 15s") is chosen by the judge: what the
    customer said is not interpreted here.
    """
    if len(options) == 1:
        return options[0]
    return next((o for o in options if o.label == said.strip()), None)


def quantity(value: object) -> tuple[float | None, str]:
    """The quantity as a number and what came stuck to it: 2, "2" or "4 liters" -> (4.0, "liters").

    The model sometimes writes the unit in `quantity` and leaves `presentation` at
    null ("I want 4 liters of Escudo", one of two runs on Sep 25,
    2026); what is left over from the number serves as the presentation.
    """
    if isinstance(value, bool):
        return None, ""
    if isinstance(value, (int, float)):
        return float(value), ""
    if isinstance(value, str):
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*(.*)", value)
        if m:
            return float(m.group(1).replace(",", ".")), m.group(2).strip()
    return None, ""


def sheets(bundle: Path | None = None) -> list[tuple[str, Path]]:
    """The bundle's datasheets: the title of each one and its path, in file order."""
    root = bundle or catalog.BUNDLE
    out = []
    for f in sorted((root / "products").glob("*.md")):
        if f.name == "index.md":
            continue
        out.append((str(catalog.frontmatter(f.read_text(errors="replace")).get("title") or f.stem), f))
    return out


def titled(said: str, found: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    """The datasheet whose title is what was noted as is, ignoring case and spaces at the edges.

    The rest ("Escudo", "Raíz Viva", "the silverstrike one") is chosen by the judge (`product_question` in
    `prompts/judge.py`) and arrives in `named`: a name is not interpreted here.
    """
    key = said.strip().casefold()
    return next(((t, p) for t, p in found if t.casefold() == key), None)


def said_products(raw: object) -> tuple[str, ...]:
    """The product names the cart noted, in order and without repeats."""
    if not isinstance(raw, list):
        return ()
    return tuple(dict.fromkeys(str(e.get("product") or "") for e in raw if isinstance(e, dict)))


def price_order(raw: object, bundle: Path | None = None, named: dict[str, str] | None = None) -> tuple[Item, ...]:
    """The model's raw `cart`, set against the datasheets. What is not a list of objects is an empty order.

    Each name reaches its datasheet if it is a title as is (`titled`) or if the judge chose it:
    `named` goes from what was noted to the title.
    """
    if not isinstance(raw, list):
        return ()
    root = bundle or catalog.BUNDLE
    found = sheets(root)
    by_title = dict(found)
    named = named or {}
    status = {path: str(catalog.frontmatter(path.read_text(errors="replace")).get("state") or "") for _, path in found}
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        said_product = str(entry.get("product") or "")
        amount, rest = quantity(entry.get("quantity"))
        said_presentation = str(entry.get("presentation") or rest)
        hit = titled(said_product, found) or ((named[said_product], by_title[named[said_product]]) if named.get(said_product) in by_title else None)
        if hit is None:
            items.append(Item(said_product, said_presentation, amount))
            continue
        title, path = hit
        options = presentations(path.read_text(errors="replace"))
        chosen = exact(said_presentation, options)
        if status[path] in RETIRED:
            options, chosen = [], None
        items.append(
            Item(
                said_product,
                said_presentation,
                amount,
                product=title,
                path=str(path.relative_to(root)),
                presentation=chosen.label if chosen else None,
                unit_price=chosen.price if chosen else None,
                status=status[path],
                options=() if chosen else tuple(o.label for o in options),
                currency=chosen.currency if chosen else "",
                code=chosen.code if chosen else "",
            )
        )
    return tuple(items)


def choose(item: Item, option: str, bundle: Path | None = None) -> Item:
    """The line with the presentation the judge chose: one of `item.options`, `OTHER_UNIT` or nothing.

    `option` is the row's label, as is; `OTHER_UNIT` marks `other_unit`; anything
    else leaves the line as it was.
    """
    if item.path is None or not item.options:
        return item
    if option == OTHER_UNIT:
        return replace(item, other_unit=True)
    root = bundle or catalog.BUNDLE
    picked = next((o for o in presentations((root / item.path).read_text(errors="replace")) if o.label == option), None)
    if picked is None:
        return item
    return replace(item, presentation=picked.label, unit_price=picked.price, options=(), currency=picked.currency, code=picked.code)


def remember(items: tuple[Item, ...], args: tuple[tuple[str, str], ...], bundle: Path | None = None) -> tuple[Item, ...]:
    """The order with the gaps filled from the payment link already sent: the presentation and quantity of that product.

    `args` are those of `send_payment_link` (`payment_args`), which travel in the
    `effects` channel and the host seeds each turn: they are the order the customer already saw
    quoted and, almost always, paid. It only fills what is missing; what compaction
    brings is not touched, and a product that was not in the link stays as it came.

    Compaction rebuilds the cart each turn and has no memory. In the
    prod sale of Sep 28, 2026 the advisor said "Silverstrike de 1 L" and
    the "yes" answered a question without the size: 2 of 3 compactions of the same
    turn lost it, and the advisor asked for the presentation after the payment, twice.
    """
    rows = []
    for key, value in args:
        if key != "item":
            continue
        try:
            row = json.loads(value)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("product"):
            rows.append(row)
    if not rows:
        return items
    out = []
    for i in items:
        same = [r for r in rows if r["product"] == i.product]
        if i.product is None or not i.sold or len(same) != 1 or (i.presentation is not None and i.quantity is not None):
            out.append(i)
            continue
        row = same[0]
        presentation = i.presentation or str(row.get("presentation") or "")
        amount = i.quantity if i.quantity is not None else row.get("quantity")
        filled = price_order([{"product": i.product, "presentation": presentation, "quantity": amount}], bundle)
        out.append(filled[0] if filled and filled[0].product == i.product else i)
    return tuple(out)


def has_quantities(items: tuple[Item, ...]) -> bool:
    """Whether the order says how much of each thing: at least one line that is sold, and all the sold ones with a quantity.

    This is what closes `quantity` since Sep 25, 2026, instead of
    `said_quantity`, a judge's yes or no that does not see several products: "10 of
    Raíz Viva and Escudo" is an order missing the quantity of the second.
    It also counts what was not found in the catalog: the customer said the quantity
    all the same. What is discontinued is not sold and needs no quantity.
    """
    sold = [i for i in items if i.sold]
    return bool(sold) and all(i.quantity is not None for i in sold)


def billable(items: tuple[Item, ...]) -> bool:
    """Whether the order can be charged: everything sold with a price, a whole quantity and a single currency.

    This is what the payment link (`send_payment_link`) requires since Sep 25,
    2026. Whole because the host's payment order counts
    units (`Quantity int64` in the host): "2.5" of a 1 L container is not
    a line that can be charged. Neither is a line not found in the
    catalog: it has no price to charge.
    """
    sold = [i for i in items if i.sold]
    return (
        bool(sold)
        and all(i.product is not None and i.subtotal is not None for i in sold)
        and all(float(i.quantity or 0).is_integer() and (i.quantity or 0) > 0 for i in sold)
        and len({i.currency for i in sold}) == 1
    )


def payment_args(items: tuple[Item, ...]) -> tuple[tuple[str, str], ...]:
    """The args of the payment link: one `item` per line (JSON), the `total` and the `currency`. Empty if not chargeable.

    Each `item` carries `line` so two equal lines do not merge:
    the args are an ordered set of pairs. `item_code` is the presentation's SAP
    code, empty if the datasheet does not have it: the host stores it as the position's `sku`
    and the SAP draft (`sap_draft`) uses it as the article. It also goes in the link because
    the host takes the position's reference from the whole lines, and the link and the
    draft of one sale have to land on the same position. Since Oct 3,
    2026.
    """
    if not billable(items):
        return ()
    sold = [i for i in items if i.sold]
    rows = tuple(
        (
            "item",
            json.dumps(
                {
                    "line": n,
                    "product": i.product,
                    "presentation": i.presentation,
                    "quantity": int(i.quantity or 0),
                    "price": f"{i.unit_price:.2f}",
                    "subtotal": f"{i.subtotal:.2f}",
                    "item_code": i.code,
                },
                ensure_ascii=False,
            ),
        )
        for n, i in enumerate(sold, 1)
    )
    total = sum(i.subtotal or 0.0 for i in sold)
    return (*rows, ("currency", sold[0].currency), ("total", f"{total:.2f}"))


def order_dict(items: tuple[Item, ...]) -> dict[str, Any]:
    """For the host: the lines, the total if all have a subtotal, the currency if there is only one, and whether it can be charged.

    `sku` and `currency` of each line, the order's `currency` and `chargeable` (`billable`, the same
    criterion as `chargeable_order`) are for the conversation's card: knowledge copies them
    without reading text. Since Oct 7, 2026.
    """
    subtotals = [i.subtotal for i in items]
    total = round(sum(s for s in subtotals if s is not None), 2) if items and None not in subtotals else None
    currencies = {i.currency for i in items if i.currency}
    return {
        "items": [i.as_dict() for i in items],
        "total": total,
        "currency": currencies.pop() if len(currencies) == 1 else None,
        "chargeable": billable(items),
    }
