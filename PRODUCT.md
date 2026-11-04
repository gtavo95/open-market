# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Hackathon judges and public visitors, on the page at `/`. They play a farmer talking to a farm-input
distributor, and they want to see whether the advisor is right and why. The author also uses the
page to read what a turn did.

## Product Purpose

open-market is a sales advisor for farm inputs on Muse Wonder. A farmer describes a pest in writing,
in a voice note or with a photo; the advisor finds the product in the distributor's catalog, gives
the dose from the datasheet, cites its source, builds the priced order and takes it to payment. When
no datasheet covers the problem it says so and hands off to an agronomist.

## Positioning

The advisor does not invent a product or a dose. Every recommendation comes from a datasheet it
opened, and the trace of the turn shows that happening.

## Operating Context

A turn takes about 45 seconds, and up to 80 with a photo. The page is the host: sessions live in the
process, on one Cloud Run instance, and a restart forgets them. No login; `DEMO_TURNS` caps the paid
turns. Visitors may be on a phone.

## Capabilities and Constraints

- Input: text, a photo, a voice note. The page shows what was seen or heard so a misreading can be caught.
- Output: one or more messages, the sources, the tokens and the seconds of the turn.
- The page is one static HTML file, with no build step: the Dockerfile has no Node.
- The interface is in English. The advisor answers in the customer's language.
- What the agent understands and decides is text, not code (`CLAUDE.md`). The trace observes the turn
  and must never change it.

## Brand Commitments

The visual system is the one of `../platform-webapp` (`DESIGN.md` there), by the author's decision:
its bubbles, its trace rows and its palette. `okf/` belongs to a fictional distributor, Agroinsumos
Ceiba.

## Evidence on Hand

Eval numbers and the photo and voice measurements are in `README.md`. There are no customers,
testimonials or real farmers' recordings, and none may be invented.

## Product Principles

- Show the work: the trace is the proof, not a debugging extra.
- An honest wait beats a fast-looking one: a step on screen happened.
- The customer can always catch a misreading.
