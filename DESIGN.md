---
name: Open Market
description: A farm-input sales chat whose proof sits beside the answer.
colors:
  primary: '#6e2c01'
  primary-foreground: '#ffe1b6'
  primary-hover: '#4f1f01'
  primary-text: '#6e2c01'
  highlight: '#ffe1b6'
  highlight-foreground: '#6e2c01'
  background: '#faf9f5'
  foreground: '#1f1f1f'
  muted-foreground: '#6b5d51'
  receipt: '#6b5d51'
  surface: '#ffffff'
  surface-hover: '#fff5e6'
  surface-active: '#ffe1b6'
  border: '#e5d5c3'
  border-strong: '#c9b8a4'
  ring: '#9e4303'
  disabled: '#f3ede5'
  disabled-foreground: '#a8998a'
  destructive: '#b93815'
  destructive-text: '#a3300f'
  warning: '#f59e0b'
  warning-text: '#a14a06'
  success: '#7fa04a'
  success-text: '#4a6619'
  dark-primary: '#ffe1b6'
  dark-primary-foreground: '#6e2c01'
  dark-primary-hover: '#ffd29a'
  dark-primary-text: '#e0b48a'
  dark-highlight: '#3b2414'
  dark-highlight-foreground: '#ffe1b6'
  dark-background: '#1f1f1f'
  dark-foreground: '#faf9f5'
  dark-muted-foreground: '#b3a69a'
  dark-receipt: '#a8998a'
  dark-surface: '#292522'
  dark-surface-hover: '#342e2a'
  dark-surface-active: '#3b2414'
  dark-border: '#3a332e'
  dark-border-strong: '#5a4f46'
  dark-ring: '#e0b48a'
  dark-disabled: '#342e2a'
  dark-disabled-foreground: '#8a7d72'
  dark-destructive: '#f06a4a'
  dark-destructive-text: '#f4876b'
  dark-warning: '#fbbf24'
  dark-warning-text: '#fbbf24'
  dark-success: '#a9c46c'
  dark-success-text: '#b3cc7a'
typography:
  greeting:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '1.0625rem'
    fontWeight: 400
    lineHeight: 1.6
  input:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '1rem'
    fontWeight: 400
    lineHeight: '1.5rem'
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.9375rem'
    fontWeight: 650
    letterSpacing: '-0.015em'
  message:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.9375rem'
    fontWeight: 400
    lineHeight: 1.625
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.875rem'
    fontWeight: 400
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.8125rem'
    fontWeight: 500
  trace-row:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.8rem'
    fontWeight: 500
  summary:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.75rem'
    fontWeight: 400
  meta:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", sans-serif'
    fontSize: '0.6875rem'
    fontWeight: 500
  code:
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'
    fontSize: '0.72rem'
    fontWeight: 400
    lineHeight: 1.5
rounded:
  tail: '0.375rem'
  sm: '0.5rem'
  md: '0.75rem'
  lg: '1.25rem'
  xl: '1.5rem'
  full: '9999px'
spacing:
  gutter-mobile: '1rem'
  gutter-desktop: '2rem'
  edge-mobile: '1rem'
  edge-desktop: '1.75rem'
  header-height: '3.5rem'
  measure: '56rem'
  card-width: '22rem'
  trace-width: '36rem'
  turn-gap: '2rem'
  answer-gap: '0.75rem'
  touch-target: '2.75rem'
components:
  button-send:
    backgroundColor: '{colors.primary}'
    textColor: '{colors.primary-foreground}'
    rounded: '{rounded.full}'
    size: '2.75rem'
  button-send-hover:
    backgroundColor: '{colors.primary-hover}'
    textColor: '{colors.primary-foreground}'
  button-send-disabled:
    backgroundColor: '{colors.disabled}'
    textColor: '{colors.disabled-foreground}'
  button-round:
    backgroundColor: 'transparent'
    textColor: '{colors.muted-foreground}'
    rounded: '{rounded.full}'
    size: '2.75rem'
  button-round-hover:
    backgroundColor: '{colors.surface-hover}'
    textColor: '{colors.foreground}'
  button-new-chat:
    backgroundColor: 'transparent'
    textColor: '{colors.muted-foreground}'
    typography: '{typography.label}'
    rounded: '{rounded.full}'
    padding: '0 0.75rem'
    height: '2.25rem'
  button-tool:
    backgroundColor: 'transparent'
    textColor: '{colors.muted-foreground}'
    typography: '{typography.meta}'
    rounded: '{rounded.sm}'
    padding: '0 0.5rem'
    height: '1.75rem'
  starter:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.foreground}'
    typography: '{typography.body}'
    rounded: '{rounded.lg}'
    padding: '0.5rem 0.875rem'
  bubble-customer:
    backgroundColor: '{colors.highlight}'
    textColor: '{colors.highlight-foreground}'
    typography: '{typography.message}'
    rounded: '{rounded.lg}'
    padding: '0.5rem 0.875rem'
  pill-source:
    backgroundColor: '{colors.surface-hover}'
    textColor: '{colors.muted-foreground}'
    rounded: '{rounded.full}'
    padding: '0.1rem 0.5rem'
  composer:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.foreground}'
    typography: '{typography.input}'
    rounded: '{rounded.xl}'
    padding: '0.375rem 0.75rem'
  trace:
    backgroundColor: 'transparent'
    textColor: '{colors.foreground}'
    rounded: '{rounded.md}'
    padding: '0.5rem'
    width: '{spacing.trace-width}'
  trace-row:
    backgroundColor: 'transparent'
    textColor: '{colors.foreground}'
    typography: '{typography.trace-row}'
    rounded: '{rounded.sm}'
    padding: '0.3rem 0.4rem'
    height: '1.75rem'
  card:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.foreground}'
    rounded: '{rounded.lg}'
    width: '{spacing.card-width}'
  card-tab-active:
    backgroundColor: '{colors.surface-active}'
    textColor: '{colors.foreground}'
    rounded: '{rounded.full}'
    height: '1.875rem'
  tone-neutral:
    backgroundColor: '{colors.surface-active}'
    textColor: '{colors.muted-foreground}'
    rounded: '{rounded.full}'
    padding: '0.15rem 0.5rem'
  dock-bubble:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.primary-text}'
    rounded: '{rounded.full}'
    size: '3.25rem'
  count-badge:
    backgroundColor: '{colors.primary}'
    textColor: '{colors.primary-foreground}'
    rounded: '{rounded.full}'
    height: '1.15rem'
---

# Design System: Open Market

## Overview

**Creative North Star: "The Proof Beside the Answer"**

Open Market is a sales chat that shows its work. The customer's words sit in a warm cream bubble; the advisor's answer is plain prose with no bubble around it; under the answer lies the real trace of what the agent opened, and beside it float the cart and the billing details the agent is filling in. It is not a chatbot widget. The page is the whole conversation, and everything on it is either something said or evidence for it.

The ground is quiet paper, the ink is near black, and one cacao brown carries every action. Density is that of a working tool: compact rows, small tabular figures, hairlines instead of panels. Warmth comes from the neutrals, which are all tinted toward clay, and from soft corners. Nothing is decorative: the only imagery is the customer's own photo.

Depth is reserved for what floats. The thread stays flat, so a card or a dock bubble reads at once as something beside the conversation, not part of it.

**Key Characteristics:**

- Paper ground, white only where something floats or takes input.
- One brown for action, always paired with cream.
- Answers as bare prose at reading width; only the customer speaks in a bubble.
- Traces, hairlines and tabular figures as the visible proof.
- Soft corners, with one small corner on the speaker's side of the bubble.
- Light and dark follow the system; there is no theme switch.

### Provenance

This visual world was not invented here. By the author's decision it was brought from `../platform-webapp`, the Baalam console: its palette, its bubbles, its trace rows and its floating context card. The values were taken from what platform ships (`src/app.css` and the chatroom components under `src/lib/components/messages` and `src/lib/components/context`), and this file records what this page ships, not what platform has. Platform's own `DESIGN.md` is older than its code: it still names an orange primary and a white customer bubble, and neither is in platform's stylesheet or here. Where this file and platform disagree, this file describes Open Market.

Four differences from platform are deliberate:

- The card floats over the conversation and moves nothing; platform moves the thread (see The Shared Edges Rule).
- The card has no outside-click close on desktop (see The Three Ways Out Rule).
- The trace stays folded after a turn, with its step count in the toggle (see The Folded Proof Rule).
- A step the stream never closed shows as muted "cut off", not as failed (see The Honest Cut Rule).

## Colors

An earth palette of cacao, cream and clay on paper, with three state colors held back for what needs a reading.

### Primary

- **Cacao** (`primary`): the action color. Fills the send button and the count badges, and tints the composer's focus ring, the card's round icon and the flash on a changed value.
- **Cacao Deep** (`primary-hover`): the send button under the pointer.
- **Cacao Ink** (`primary-text`): brown as letters and icons: links, the dock bubble icons, the card icon, the caret, the spinner's moving arc. In dark mode it lightens to `dark-primary-text`, because the fill turns cream there and would be too strong for text.

### Secondary

- **Customer Cream** (`highlight`, `highlight-foreground`): the customer's bubble and text selection, with cacao letters (8.25:1). In dark mode it becomes a deep roast with cream letters (11.53:1).
- **Burnt Sienna** (`ring`): the keyboard focus outline, and nothing else.

### Neutral

- **Paper** (`background`): the whole page.
- **Night** (`foreground`): main text, including the advisor's prose.
- **Bark** (`muted-foreground`, `receipt`): everything secondary: labels, summaries, idle icons, times (6.02:1 on paper). `receipt` holds the time stamps and the turn figures; it matches Bark in light mode and sits a step quieter in dark.
- **White** (`surface`): only what floats or takes input: composer, starters, dock bubbles, cards, peek.
- **Warm Tints** (`surface-hover`, `surface-active`): `surface-hover` is every hover, the source pills, the code blocks and the typing bubble. `surface-active` is selection: the active tab, the neutral status pill, the quantity square.
- **Clay** (`border`, `border-strong`): every hairline and divider; the strong step marks hover, the expanded dock bubble, link underlines, thin scrollbars and the grab handle.
- **Disabled Sand** (`disabled`, `disabled-foreground`): the send button at rest with nothing to send.

### States

- **Red** (`destructive`, `destructive-text`): the fill is only the recording dot. The text form carries the error line, a failed step and composer problems (6.67:1 on paper).
- **Amber** (`warning`, `warning-text`): the order that cannot be charged yet, a pending field, a sent link. The fill appears only as a 16% tint under the status pill.
- **Leaf** (`success`, `success-text`): complete billing details and the drawn check of a finished step. The fill appears only as a 14% tint.

Dark mode is a full second palette, held in the `dark-` tokens and applied by `prefers-color-scheme`. Its surfaces are warm browns, never neutral greys.

### Named Rules

**The Cream On Cacao Rule.** Cacao fill wears cream, and customer cream wears cacao letters. In dark mode the pair inverts: cream fill, cacao icon. No other color goes on a cacao fill.

**The Fill Versus Text Rule.** Every state color has a fill and a text form. Fills only tint or dot; letters and icons always use the `-text` form. A new state brings both, and the text form reaches 4.5:1 on paper, white and the warm tints.

**The Warm Neutral Rule.** Borders, grounds and text neutrals are tinted toward clay in both modes. The cool tint exists only inside the light-mode shadows.

## Typography

**Body Font:** the system stack, -apple-system and SF Pro with Segoe UI as fallback
**Label/Mono Font:** ui-monospace with SFMono-Regular, Menlo and Consolas

**Character:** one system face at small, exact sizes, as in the console this world comes from. The page loads no web font, and it has no display tier: the largest text is the greeting, because the conversation is the page. Hierarchy comes from weight and color, and titles sit at 650 with slightly tightened tracking.

### Hierarchy

- **Greeting** (400, 17px, 1.6): the advisor's first line, capped at 65ch.
- **Input** (400, 16px, 24px): the composer's text. It stays at 16px so a phone does not zoom on focus.
- **Title** (650, 15px, -0.015em): the name in the header, the card's title.
- **Message** (400, 15px, 1.625): the customer's bubble and the advisor's prose, the answer capped at 70ch.
- **Body** (400, 14px): starters, cart lines, billing fields, empty states.
- **Label** (500, 13px): New chat, attachment tags, the Heard and Seen notes, composer problems.
- **Trace Row** (500, 12.8px): a step's title. Secondary trace text steps down through 12.5px to 11.5px; these fine steps come with the trace rows from platform.
- **Summary** (400, 12px): the card's summary, the working status, the header tagline, secondary line text.
- **Meta** (500, 11px): tool buttons and badges; status pills rise to 600 and time stamps drop to 400. This is the floor.
- **Code** (400 mono, 11.5px, 1.5): code blocks. Source pills are 11.2px mono and a REPL step's title is 12px mono.

### Named Rules

**The Eleven Pixel Floor Rule.** No text measures under 11px (0.6875rem): not a badge, not a stamp.

**The Machine Text Rule.** Mono is only for what a machine wrote: source paths, REPL step titles, Code and Output blocks. Words the advisor or the page says to a person are never mono.

**The Tabular Figures Rule.** Clock times, durations, tokens, quantities and prices use tabular numerals, so figures do not shift as a step's seconds count up or a line changes.

## Layout

The page is one fixed column of three bands at full dynamic viewport height: a slim header with a hairline under it, a thread that scrolls with its scrollbar hidden, and the composer pinned at the bottom. The thread holds a centered column of 56rem, and its content is anchored to the bottom, so a new conversation starts next to the composer and grows upward.

Inside the column the customer's bubble aligns right at 85% of the width, 70% from 640px up. Answers align left. Reading widths are capped for prose, not for the column. Turns sit `turn-gap` apart; an answer starts `answer-gap` under its bubble. That is the page's rhythm: wide between turns, tight inside one.

The gutter is 1rem and rises to 2rem at 768px; the header uses the same gutter, so its text starts on the column's edge until the column centers. The floating elements sit `edge-mobile` from the right edge, and `edge-desktop` from 1024px. The dock rides 12px above the composer, measured live, so a multi-line message pushes it up. When cards exist, the thread reserves 4.5rem at its end so the last line clears the dock.

From 1024px the card is a floating panel above the dock, and it overlays the conversation without moving it. The composer is absolute over the bottom of the thread, which scrolls under it and reserves its height, measured live. Under 1024px it is a bottom sheet instead: full width, top corners rounded, up to 82% of the viewport, over a scrim and with a grab handle. Coarse pointers raise tools, tabs, New chat, small round buttons and trace rows to `touch-target`, and the copy button is always visible where there is no hover.

### Named Rules

**The Shared Edges Rule.** The text, the bubble and the input share the same left and right edges, always. Opening a card moves neither: it floats over them, by the author's decision, and on narrower desktops it may cover the right of the column. Platform moves the thread.

## Elevation & Depth

A hybrid: the thread is flat, and depth is tonal, from paper to white to warm tint. Shadows are soft and appear only on what stands off the thread, each one at the strength of its role. Dark mode swaps all three shadows to black at higher opacity.

### Shadow Vocabulary

- **Card** (`box-shadow: 0 1px 4px rgb(37 39 59 / .06)`): resting touchable pieces on the thread, the starters and the jump-to-latest button.
- **Composer** (`box-shadow: 0 4px 6px -1px rgb(37 39 59 / .08), 0 2px 4px -2px rgb(37 39 59 / .06)`): the input pill at rest. Dark mode swaps it for black at .32 and .24. On focus it is replaced by a 3px cacao tint at 12% and a 40% cacao border.
- **Float** (`box-shadow: 0 12px 32px rgb(37 39 59 / .14)`): what hovers over the conversation: dock bubbles, the card, the peek.

### Named Rules

**The Flat Thread Rule.** The customer's bubble, the answer and the trace have no shadow. A trace is a hairline outline on paper, so proof reads as part of the page, not as an object on it.

## Shapes

Soft shapes throughout, in four sizes that grow with the object: `sm` for rows, tools and small squares; `md` for the trace, notes and the peek; `lg` for bubbles, starters and cards; `xl` for the composer. Buttons that hold only an icon, pills, tabs and badges are full circles or stadiums. Borders are always 1px hairlines of Clay. Icons are inline line drawings on a 24px grid, stroke 2 with round caps and joins, with no icon font.

### Named Rules

**The Speaker's Corner Rule.** The customer's bubble is fully round except for its top right corner, cut to `tail` on the speaker's side. The three-dot wait marks the agent's side the same way, at bottom left, and disappears when the answer arrives.

## Components

### Buttons

Quiet by default: only send is filled.

- **Shape:** full circles for icons (2.75rem, small 2rem), a stadium for New chat, small rounded rectangles for tools.
- **Primary:** send, a cacao circle with a cream arrow, in Disabled Sand until there is something to send.
- **Ghost:** attach, record, close and New chat, in Bark on no fill. Under the pointer they take `surface-hover` and turn Night.
- **Tool:** the small row under an answer: Show trace, Try again, copy.
- **Hover / Focus:** background and color in 150ms. Keyboard focus is a 2px Burnt Sienna outline, 2px offset. Round buttons press to 0.95 and starters to 0.98.

### Chips

- **Starters:** white stadiums with a hairline and the Card shadow, wrapping under the greeting. They send on click.
- **Source pills:** Bark mono on `surface-hover`, one per datasheet cited, under the answer and inside a trace step.
- **Status pills:** Bark on `surface-active` when neutral; amber or leaf text on its own tint for warning and success.

### Cards / Containers

The floating context card holds the cart and the billing details. It has tabs when both exist.

- **Corner Style:** `lg`, top corners only as a sheet.
- **Background:** white with a Clay hairline.
- **Shadow Strategy:** Float.
- **Head:** a round icon on a 12% cacao tint, the title with its status pill, a one-line summary, and the close button. A hairline separates it from the body.
- **Internal Padding:** 1rem at the sides; rows split by hairlines. The quantity is a small `surface-active` square.
- **Motion:** it scales from the dock bubble that opened it (340ms, responsive ease). As a sheet it slides up and drags to close.

### Dock and Peek

Round white bubbles at bottom right, one per card, with a cacao count badge. They appear only once there is something to show. When the card is closed and something changes, the bubble pulses and a small peek slides out to its left with the title, status and summary, for 2.6 seconds, or 5.2 when the status itself moved.

### Inputs / Fields

- **Style:** the composer is a white pill with a hairline, holding attach, the text, record and send. The field itself has no border or outline. A staged photo shows as a chip above the line, and the text grows up to 9rem.
- **Focus:** the Composer shadow gives way to its cacao ring.
- **Recording:** the text is replaced by a pulsing red dot, the word Recording and a tabular timer.
- **Error / Disabled:** problems appear as `destructive-text` above the pill.

### Navigation

There is none beyond the slim header: the name, a tagline that hides under 1024px, and New chat. A round jump-to-latest button appears over the composer when the visitor scrolls up.

### Message Turn

The customer's bubble takes a time stamp beneath it. Inside the bubble, translucent paper notes labeled Heard and Seen in the photo show what the page understood, and wipe open from the left when they arrive. The answer below is bare prose, then source pills, then one meta line: time, seconds, tokens, the trace toggle, and copy. A failed turn replaces the prose with a line in `destructive-text`.

### Agent Trace

The signature component, and the page's proof.

- **While working:** three dots and a shimmering "The agent is working" sit above an open trace. Steps land live, each with a spinner and a seconds count.
- **Row:** line icon, a Bark type label (Judge, Searcher, REPL, Plan), the title, the time, then a chevron when it has details. Children nest behind a hairline. Three or more plan moves group into one row.
- **Finishing:** the spinner gives way to a leaf check that draws itself in 260ms, then fades after 700ms. A replayed turn shows no checks.
- **Failure:** a failed step shows "failed" in `destructive-text` and pins itself and its parents open inside the trace.

**The Folded Proof Rule.** The trace is open while the turn runs and folds when it ends, staying folded. The toggle carries the count ("Show trace · 9 steps"), so the proof is one click away and the conversation stays readable.

**The Honest Cut Rule.** A step the stream never closed is muted "cut off", in Bark at medium weight, never red and never "failed". The page stopped seeing it, which does not mean it failed.

**The Three Ways Out Rule.** On desktop the card closes with Esc, its close button or its dock bubble, and clicking the thread leaves it open, so the visitor can read and scroll beside it. As a sheet it also closes on the scrim and by dragging down.

### Motion

Two easings carry everything: responsive for things that answer the visitor (bubbles, card, chevrons), and emphasized for things that report news (trace rows, notes, the check, the flash on a changed value). Arrivals take 420ms, state changes 150ms, drawers 160ms. Under reduced motion everything collapses to 1ms and the shimmer's mask is removed.

## Do's and Don'ts

### Do:

- **Do** put cream on cacao, and cacao letters on customer cream.
- **Do** use the `-text` form for any colored letter or icon.
- **Do** keep answers as bare prose capped at 70ch.
- **Do** keep the thread and the composer on the same edges in every state.
- **Do** show what the page understood inside the customer's own bubble.
- **Do** use tabular numerals for times, quantities and prices.
- **Do** give every control 2.75rem on a coarse pointer.
- **Do** take any new value from these tokens, in both modes.

### Don't:

- **Don't** put an answer in a bubble: the only agent-side bubble is the three-dot wait.
- **Don't** put a shadow on the customer's bubble, the answer or the trace.
- **Don't** put mono on anything a person is told.
- **Don't** set any text under 11px.
- **Don't** mark a cut step as failed, or color it red.
- **Don't** unfold the trace after a turn on its own.
- **Don't** close the desktop card on an outside click.
- **Don't** show a step, a percentage or a progress bar that the stream did not send.
- **Don't** take an orange primary or a white customer bubble from platform's `DESIGN.md`: its stylesheet moved on and so did this page.
- **Don't** use cool greys for borders, grounds or text.
